import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse
import numpy as np
import requests
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


Language = Literal["English", "Urdu", "Roman Urdu"]
Intent = Literal["informational", "commercial", "transactional", "navigational"]


class EvidenceQuote(StrictModel):
    chunk_id: str
    quote: str = Field(min_length=8, max_length=700)


class StageError(RuntimeError):
    pass


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def normalized(text):
    return " ".join(text.split())


def load_user_documents(request):
    effective = dict(request)
    effective["instruction_documents"] = []
    sources, notices, seen = [], [], set()
    for item in request["files"]:
        identity = str(Path(item["path"]).resolve())
        if identity in seen:
            continue
        seen.add(identity)
        document = read_document(identity)
        notices.extend(document["notices"])
        if item["role"] == "user_instructions":
            effective["instruction_documents"].append(document)
        else:
            sources.append({
                **document, "url": None, "file_path": identity,
                "source_role": "user_reference", "source_type": "document",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
    instruction_size = len(effective["instructions"]) + sum(
        len(section["text"])
        for doc in effective["instruction_documents"] for section in doc["sections"]
    )
    if instruction_size > SETTINGS["max_instruction_chars"]:
        raise ValueError("Instruction text exceeds 6000 characters; shorten it or use a reference file.")
    return effective, sources, notices


class SourcePlan(StrictModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=12)
    rationale: str = Field(min_length=1)


async def select_sources(request, candidates, folder):
    if not candidates:
        return {"candidate_ids": [], "rationale": "No web candidates; use reference files."}

    target = SETTINGS.get("target_sources", 2)
    if len(candidates) <= target:
        return {
            "candidate_ids": [item["candidate_id"] for item in candidates],
            "rationale": "Top candidates automatically selected by search relevance.",
        }

    def validate(plan):
        known = {item["candidate_id"] for item in candidates}
        if len(set(plan.candidate_ids)) != len(plan.candidate_ids):
            raise ValueError("Candidate IDs must be unique.")
        if set(plan.candidate_ids) - known:
            raise ValueError("Select only supplied candidate IDs.")

    try:
        return await run_agent(
            "source", "Source Selection Analyst",
            "Rank relevant candidates for the user's topic. Prefer primary sources "
            "and a useful spread of publishers. User URLs receive priority. "
            "Titles and snippets are unverified discovery metadata, never evidence. "
            "Return candidate IDs in fetch order, at most twelve. Do not invent URLs.",
            SourcePlan, {"request": request, "candidates": candidates[:4]}, folder, validate,
        )
    except Exception as exc:
        if type(exc).__name__ == "ProviderFailure":
            raise
        print(f"[source] Notice: Using deterministic candidate ranking fallback ({str(exc)[:100]}).")
        return {
            "candidate_ids": [item["candidate_id"] for item in candidates[:target]],
            "rationale": "Deterministic ranking fallback based on search engine relevance order.",
        }


def collect_sources(candidates, plan, document_sources):
    lookup = {item["candidate_id"]: item for item in candidates}
    provided = [item["candidate_id"] for item in candidates if item["provided"]]
    order = list(dict.fromkeys(provided + plan["candidate_ids"] + list(lookup)))
    sources, errors = list(document_sources), []
    seen_urls, seen_text = set(), set()
    web_count = 0
    target_count = SETTINGS["target_sources"]

    urls_to_fetch = [lookup[cid]["url"] for cid in order[:SETTINGS["max_fetches"]] if cid in lookup]
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if urls_to_fetch:
        with ThreadPoolExecutor(max_workers=min(len(urls_to_fetch), 4)) as executor:
            future_to_url = {executor.submit(fetch_source, u): u for u in urls_to_fetch}
            for future in as_completed(future_to_url):
                if web_count >= target_count:
                    break
                url = future_to_url[future]
                try:
                    source = future.result()
                    fingerprint = hashlib.sha256(source["sections"][0]["text"].encode("utf-8")).hexdigest()
                    if source["url"] in seen_urls or fingerprint in seen_text:
                        continue
                    sources.append(source)
                    seen_urls.add(source["url"])
                    seen_text.add(fingerprint)
                    web_count += 1
                except (requests.RequestException, ValueError) as exc:
                    errors.append({"url": url, "reason": str(exc)})
    for i, source in enumerate(sources, 1):
        source["source_id"] = f"S{i}"
    return {
        "sources": sources, "errors": errors,
        "web_target_met": web_count >= SETTINGS["target_sources"],
    }


def encode_chunks(chunks):
    return get_embedding_model().encode(
        ["passage: " + item["text"] for item in chunks],
        normalize_embeddings=True, convert_to_numpy=True,
        batch_size=16, show_progress_bar=False,
    )


def retrieve_evidence(request, chunks, embeddings):
    if not chunks or len(chunks) != len(embeddings):
        raise ValueError("Chunks and embedding rows must align.")
    model = get_embedding_model()
    # Dynamic domain-agnostic retrieval query (zero hardcoded ML/Python bias)
    q_parts = [f"query: {request['topic']}."]
    if request.get("audience"):
        q_parts.append(f"Target audience: {request['audience']}.")
    if request.get("instructions"):
        q_parts.append(f"Focus areas: {request['instructions']}.")
    q_parts.append("Core concepts, foundational facts, implementation, and recommendations.")
    query = " ".join(q_parts)
    if request.get("audience"):
        query += f" Audience: {request['audience']}"
    if len(model.tokenizer(query)["input_ids"]) > model.max_seq_length:
        query = "query: " + request["topic"][:120]
    vector = model.encode(query, normalize_embeddings=True, convert_to_numpy=True)
    scores = embeddings @ vector
    ranked = list(np.argsort(-scores))
    chosen, seen = [], set()
    for i in ranked:
        if chunks[i]["source_id"] not in seen:
            chosen.append(i)
            seen.add(chunks[i]["source_id"])
        if len(chosen) == SETTINGS["top_k"]:
            break
    chosen += [i for i in ranked if i not in chosen][:SETTINGS["top_k"] - len(chosen)]
    return [{**chunks[i], "similarity": float(scores[i])} for i in chosen]


def build_research_context(request, evidence, sources):
    used = {item["source_id"] for item in evidence}
    references = {
        source["source_id"]: {
            key: source.get(key) for key in (
                "title", "url", "file_path", "source_role", "source_type", "retrieved_at"
            )
        }
        for source in sources if source["source_id"] in used
    }
    limitations = ["Supplied evidence has not been independently fact-checked."]
    if len(references) == 1:
        limitations.append("Evidence comes from only one source.")
    domains = {
        urlparse(item["url"]).hostname for item in references.values() if item.get("url")
    }
    if len(domains) == 1:
        limitations.append("All retrieved web evidence comes from one domain.")
    for source in sources:
        if source["source_id"] in used:
            limitations.extend(source.get("notices", []))
    return {
        "request": request, "sources": references, "evidence": evidence,
        "limitations": list(dict.fromkeys(limitations)),
    }


class ResearchFinding(StrictModel):
    statement: str = Field(min_length=1)
    citations: list[EvidenceQuote] = Field(min_length=1, max_length=3)


class ResearchReport(StrictModel):
    findings: list[ResearchFinding] = Field(max_length=3)
    missing_information: list[str]
    limitations: list[str]
    output_language: Language


async def run_research(request, research, folder, draft=None, issues=None):
    def validate(report):
        validate_language(report, request)
        for finding in report.findings:
            if len(finding.statement.split()) >= 40:
                raise ValueError("Keep each finding under 40 words.")
            validate_quotes(finding.citations, research["evidence"])

    return await run_agent(
        "research", "Content Research Analyst",
        "Produce up to three findings relevant to the request, each under 40 words. "
        "Each findings item must contain exactly statement and citations; no other keys. "
        "Put all limitations in the report-level limitations array, never inside a finding "
        "or citation. Put missing information in the report-level missing_information array. "
        "Use only supplied chunks. Attach short verbatim quotes covering the claims. "
        "CRITICAL: Copy a single short contiguous sentence (under 25 words) from the chunk. "
        "NEVER join sentences with ellipses (...) or skip words. If citing two points, use separate citation objects in the citations array. "
        "Attribute advertising in each statement itself, using wording such as "
        "'The provider advertises' or 'The provider describes its course as'. "
        "Explicitly name external providers when reporting their offers or advertising.",
        ResearchReport,
        {"request": request, "research_context": research, **correction_context(draft, issues)},
        folder, validate,
    )


class AudienceReport(StrictModel):
    audience_description: str = Field(min_length=1)
    audience_basis: Literal["user_provided", "inferred"]
    assumptions: list[str] = Field(default_factory=list, max_length=6)
    reader_needs: list[str] = Field(min_length=1, max_length=6)
    reader_questions: list[str] = Field(min_length=1, max_length=6)
    tone: str = Field(min_length=1)
    output_language: Language


async def run_audience(request, folder):
    basis = "user_provided" if request["audience"] else "inferred"

    def validate(report):
        validate_language(report, request)
        if report.audience_basis != basis:
            report.audience_basis = basis

    return await run_agent(
        "audience", "Audience Analyst",
        "Analyze intended readers using only the request. Preserve the supplied "
        "audience; otherwise infer a broad audience. Label uncertain characteristics "
        "as assumptions, using tentative wording. Suggest 2 to 4 reader needs and 2 to 4 questions as "
        "editorial hypotheses, not surveyed behavior. Keep assumptions under 4 items. Do not invent demographics. "
        "Include all schema fields and a useful tone. Use the requested output language.",
        AudienceReport, {"request": request, "expected_basis": basis}, folder, validate,
    )


class SEOReport(StrictModel):
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: list[str] = Field(min_length=2, max_length=5)
    long_tail_keywords: list[str] = Field(min_length=2, max_length=5)
    search_intent: Intent
    intent_reason: str = Field(min_length=1)
    output_language: Language


async def run_seo(request, audience, folder, draft=None, issues=None):
    def validate(report):
        validate_language(report, request)

    seo_lang = " If output_language is Urdu, write all keywords and explanations in Urdu script (اردو رسم الخط). If Roman Urdu, use Latin alphabet."
    return await run_agent(
        "seo", "SEO Strategist",
        "Generate SEO recommendations grounded in the topic and audience. "
        "Distinguish between informational, commercial, transactional, and navigational intent. "
        "Provide clear primary, secondary, and long-tail keywords. Use the requested language." + seo_lang,
        SEOReport,
        {"request": request, "audience_report": audience, **correction_context(draft, issues)},
        folder, validate,
    )


class OutlineSection(StrictModel):
    h2: str = Field(min_length=1)
    h3: list[str] = Field(max_length=3)
    coverage_notes: list[str] = Field(min_length=1, max_length=3)
    chunk_ids: list[str]


class ContentBrief(StrictModel):
    title: str = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    suggested_keywords: list[str] = Field(min_length=1, max_length=8)
    search_intent: Intent
    h1: str = Field(min_length=1)
    outline: list[OutlineSection] = Field(min_length=2, max_length=5)
    faqs: list[str] = Field(default_factory=list, min_length=0, max_length=5)
    limitations: list[str] = Field(min_length=1)
    output_language: Language


async def run_structure(request, audience, seo, findings, research, folder,
                        draft=None, issues=None):
    def validate(report):
        validate_language(report, request)
        if report.search_intent != seo.get("search_intent"):
            report.search_intent = seo.get("search_intent", report.search_intent)
        known = {item["chunk_id"] for item in research["evidence"]}
        for section in report.outline:
            section.chunk_ids = [cid for cid in section.chunk_ids if cid in known]
        target_faqs = request.get("faq_count", len(report.faqs))
        if target_faqs == 0:
            report.faqs = []
        elif len(report.faqs) > target_faqs:
            report.faqs = report.faqs[:target_faqs]
        elif len(report.faqs) < target_faqs:
            reader_qs = audience.get("reader_questions", []) if isinstance(audience, dict) else []
            for q in reader_qs:
                if q not in report.faqs and len(report.faqs) < target_faqs:
                    report.faqs.append(q)
            fallback_qs = [
                f"How can beginners get started with {request['topic']}?",
                f"What are key prerequisites for {request['topic']}?",
                f"Where can I find verified resources for {request['topic']}?",
                f"What are common pitfalls to avoid in {request['topic']}?"
            ]
            for fq in fallback_qs:
                if fq not in report.faqs and len(report.faqs) < target_faqs:
                    report.faqs.append(fq)

    lang_rule = ""
    if request.get("output_language") == "Urdu":
        lang_rule = "LANGUAGE SCRIPT MANDATE: You MUST write title, meta_description, h1, outline headings, and faqs in authentic Urdu script (اردو رسم الخط جیسے 'مصنوعی ذہانت'). Do NOT write in Roman Urdu.\n"
    elif request.get("output_language") == "Roman Urdu":
        lang_rule = "LANGUAGE SCRIPT MANDATE: Write title, meta_description, h1, outline headings, and faqs in Roman Urdu (Latin alphabet).\n"

    rules = (
        lang_rule +
        "Create a concise content brief, not an article. Keep the user's topic as the "
        "subject; a general topic is not an advertisement for a retrieved provider.\n"
        "REQUIRED KEYS CONTRACT: Your response MUST contain all 9 keys:\n"
        "1. title, 2. meta_description, 3. suggested_keywords, 4. search_intent, "
        "5. h1, 6. outline, 7. faqs, 8. limitations, 9. output_language.\n"
        "If requested faq_count is 0, faqs must be an empty list []. Otherwise provide exactly faq_count questions.\n"
        "Use 2-5 H2 sections and optional H3s. Coverage notes are actionable writer instructions.\n"
        "FORMAT: In outline sections, chunk_ids must be a standard JSON array property e.g. \"chunk_ids\": [] or \"chunk_ids\": [\"S1-C1\"]. Never write \"chunk_ids[]\".\n"
        "CRITICAL RULES FOR FACTUAL INTEGRITY & ATTRIBUTION:\n"
        "1. PROVIDER ATTRIBUTION & COURSE ELIGIBILITY: If citing specific course attributes "
        "(e.g. 8-week duration, live interactive format, certificate of completion, or prerequisite claims "
        "such as 'no prior coding or technical experience required'), you MUST explicitly attribute the "
        "specific provider by name (e.g. 'Reference Pakistan AI Online Academy\'s beginner course which states "
        "no prior coding experience is required') and attach the corresponding chunk_id (e.g. S2-C9). "
        "Do NOT state specific course durations or provider rules as universal facts without attribution.\n"
        "2. RECOMMENDATIONS VS ADVERTISED FEATURES: Present general project suggestions, portfolio advice, and self-study "
        "prerequisite tips as editorial recommendations (e.g., 'Recommendation: review basic algebra and Python variables', "
        "'Suggested project: customer churn or healthcare analysis'). Leave chunk_ids as an empty list [] for general "
        "editorial recommendations. Attach chunk_ids for all evidence-backed factual claims, including general factual claims.\n"
        "3. META DESCRIPTION CONTRACT: The title, H1, and meta_description describe YOUR newly authored guide "
        "(e.g. 'A practical roadmap for Pakistani university students to learn ML fundamentals, master prerequisites, "
        "and build portfolio projects'). Do NOT claim in meta_description that external courses were specially "
        "'designed for university students' unless directly evidenced. Keep meta_description focused on the guide\'s own scope.\n"
        "4. REPORTING MISSING EVIDENCE: If specific details requested by the user are not found in the evidence "
        "(e.g. local salary figures, university accreditations), record them in the limitations array. "
        "Do NOT invent unsupported empirical claims.\n"
        "5. LANGUAGE: Use the requested language throughout."
    )

    return await run_agent(
        "structure", "Content Structure Planner", rules, ContentBrief,
        {"request": request, "audience": audience, "seo": seo, "research_report": findings,
         "research_context": research, **correction_context(draft, issues)},
        folder, validate,
    )


class ReviewAssessmentSelection(StrictModel):
    verdict: Literal["supported", "editorial", "needs_revision"]
    explanation: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=3)


class ReviewIssueSelection(StrictModel):
    location: str
    problematic_text: str = Field(default="")
    category: Literal[
        "unsupported", "attribution", "request_mismatch",
        "assumption", "language"
    ]
    reason: str = Field(min_length=1)
    required_change: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=3)


class ReviewSelection(StrictModel):
    assessments: dict[str, ReviewAssessmentSelection]
    issues: list[ReviewIssueSelection] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(min_length=1)
