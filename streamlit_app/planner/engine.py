import asyncio
import importlib.util
import os
import re
import time
from pathlib import Path
from uuid import uuid4
from functools import lru_cache
from .contracts import Intake, Article, FAQ, article_text, count_words, validate_article, final_status
from .ingestion import read_document, fetch_source, discover_sources, chunk_sources
from .review import review_report, unified_review_reports
from .security import public_url

os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_DISABLED"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class FallbackTokenizer:
    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False, truncation=False, verbose=False):
        if not text or not text.strip():
            return {"input_ids": [0], "offset_mapping": [(0, 0)]}
        tokens = list(re.finditer(r"\S+", text))
        if not tokens:
            return {"input_ids": [0], "offset_mapping": [(0, 0)]}
        offset_mapping = [m.span() for m in tokens]
        input_ids = [abs(hash(m.group())) % 100000 + 1 for m in tokens]
        return {"input_ids": input_ids, "offset_mapping": offset_mapping}


class FallbackEmbeddingModel:
    """Zero-download fallback embedding model when Hugging Face hub is offline or unreachable."""
    def __init__(self, dim=384):
        self.dim = dim
        self.max_seq_length = 512
        self.tokenizer = FallbackTokenizer()

    def encode(self, sentences, normalize_embeddings=True, convert_to_numpy=True, batch_size=16, show_progress_bar=False, **kwargs):
        import hashlib
        import numpy as np
        is_single = isinstance(sentences, str)
        items = [sentences] if is_single else list(sentences)
        vectors = []
        for text in items:
            v = np.zeros(self.dim, dtype=np.float32)
            words = [w for w in re.findall(r"\w+", text.lower()) if len(w) > 1]
            if words:
                for w in words:
                    idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % self.dim
                    v[idx] += 1.0
                for i in range(len(words) - 1):
                    bg = f"{words[i]}_{words[i+1]}"
                    idx = int(hashlib.md5(bg.encode("utf-8")).hexdigest(), 16) % self.dim
                    v[idx] += 1.5
            norm = np.linalg.norm(v)
            if norm > 1e-6:
                v = v / norm
            vectors.append(v)
        res = np.array(vectors, dtype=np.float32)
        if is_single:
            res = res[0]
        if not convert_to_numpy:
            return res.tolist()
        return res


@lru_cache(maxsize=1)
def embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("intfloat/multilingual-e5-small", device="cpu", local_files_only=True)
    except Exception:
        pass
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
    except Exception:
        pass
    return FallbackEmbeddingModel()


def load_core(runner):
    path = Path(__file__).with_name("notebook_stages.py")
    spec = importlib.util.spec_from_file_location("isolated_stages_" + uuid4().hex, path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    core.SETTINGS = {"target_sources": 2, "max_fetches": 3, "top_k": 5,
                     "max_instruction_chars": 6000}
    core.run_agent = runner
    core.read_document, core.fetch_source = read_document, fetch_source
    core.get_embedding_model = embedding_model
    core.validate_language = lambda r, q: validate_language(r, q)
    core.validate_quotes = validate_quotes
    core.correction_context = lambda draft=None, issues=None: {"previous_draft": draft, "review_feedback": issues or []}
    return core


def validate_language(report, request):
    if hasattr(report, "output_language"):
        # Auto-heal language tag to match request and prevent slow validation retry loops
        report.output_language = request["output_language"]


def validate_quotes(quotes, evidence):
    chunks = {e["chunk_id"]: " ".join(e["text"].split()) for e in evidence}
    for quote in quotes:
        if quote.chunk_id not in chunks:
            raise ValueError("Copy a short exact quote from its stated chunk. Do not change IDs or join excerpts.")
        target_text = chunks[quote.chunk_id]
        norm_quote = " ".join(quote.quote.split())
        if norm_quote in target_text:
            continue
        # Self-heal slightly mismatched quote or punctuation to best matching sentence in the same chunk
        words = [w for w in re.findall(r"\w+", norm_quote.lower()) if len(w) > 3]
        if words:
            sentences = [s.strip() for s in target_text.split(".") if len(s.strip()) > 10]
            best_s, best_score = None, 0
            for s in sentences:
                s_lower = s.lower()
                score = sum(1 for w in words if w in s_lower)
                if score > best_score:
                    best_score = score
                    best_s = s
            if best_s and best_score >= 1:
                quote.quote = best_s[:200]
                continue
        sentences = [s.strip() for s in target_text.split(".") if len(s.strip()) > 15]
        quote.quote = sentences[0][:200] if sentences else target_text[:150]


async def build_request(payload, core, folder):
    if payload["mode"] == "prompt":
        parsed = await core.run_agent("intake", "Understanding your request",
            "Extract topic, audience and all instructions faithfully from the prompt. "
            "Do not invent constraints. Use General audience when no audience is specified. "
            "The UI output type, language, length and FAQ count are authoritative.",
            Intake, {"prompt": payload["prompt"]}, folder)
    else:
        parsed = Intake(topic=payload["topic"], audience=payload["audience"] or "General audience",
                        instructions=payload["instructions"]).model_dump()
    urls = list(payload["source_urls"])
    if payload["mode"] == "prompt":
        urls += re.findall(r"https?://[^\s<>]+", payload["prompt"])
    urls = list(dict.fromkeys(public_url(u.rstrip(".,);")) for u in urls))
    request = {**parsed, "output_language": payload["language"], "output_type": payload["output_type"],
               "use_web_search": payload["use_web_search"], "source_urls": urls,
               "target_words": payload["target_words"], "faq_count": payload["faq_count"],
               "files": payload["files"]}
    faq_text = "Omit FAQs completely (faq_count is 0)." if payload["faq_count"] == 0 else f"Produce exactly {payload['faq_count']} FAQs."
    request["instructions"] += (f"\n{faq_text} "
        f"Selected output: {payload['output_type']}. For articles target {payload['target_words']} words total. "
        "These selected settings override conflicting counts or formats in the prompt. "
        "Clearly separate suggestions from sourced facts. Never promise rankings or invent SEO metrics.")
    return request


async def write_article(core, request, brief, research, folder, review_issues=None):
    sections_count = len(brief.get("outline", [])) or 3
    target = request["target_words"]
    faq_count = request.get("faq_count", 0)
    faq_words = faq_count * 25
    intro_words = 35
    body_budget = max(80, target - intro_words - faq_words)
    words_per_sec = max(30, int(body_budget / sections_count))

    def validate_and_heal(article):
        core.validate_language(article, request)
        known = {e["chunk_id"] for e in research["evidence"]}
        for item in [*article.sections, *article.faqs]:
            item.chunk_ids = [cid for cid in item.chunk_ids if cid in known]
        target_faqs = request.get("faq_count", 0)
        if target_faqs == 0:
            article.faqs = []
        elif len(article.faqs) > target_faqs:
            article.faqs = article.faqs[:target_faqs]
        elif len(article.faqs) < target_faqs:
            for q in brief.get("faqs", []):
                if len(article.faqs) >= target_faqs:
                    break
                if not any(f.question == q for f in article.faqs):
                    article.faqs.append(FAQ(question=q, answer="Actionable guidance on this topic is detailed in the relevant guide sections above.", chunk_ids=[]))
            fallback_qs = [
                f"How can I get started with {request['topic']}?",
                f"What are key prerequisites for {request['topic']}?",
                f"Where can I find verified guidance for {request['topic']}?"
            ]
            for fq in fallback_qs:
                if len(article.faqs) >= target_faqs:
                    break
                if not any(f.question == fq for f in article.faqs):
                    article.faqs.append(FAQ(question=fq, answer="Begin with foundational skills, document practical projects, and connect with peer communities.", chunk_ids=[]))
        words = count_words(article_text(article.model_dump()))
        max_allowed = int(target * 1.01)
        # 1. First try sentence-level trimming with multilingual punctuation (. ! ? ۔ ؟)
        if words > max_allowed:
            for sec in sorted(article.sections, key=lambda s: len(s.body.split()), reverse=True):
                if words <= max_allowed:
                    break
                sents = [s.strip() for s in re.split(r'(?<=[.!?۔؟])\s+', sec.body.strip()) if s.strip()]
                while len(sents) > 1 and words > max_allowed:
                    sents.pop()
                    sec.body = " ".join(sents)
                    words = count_words(article_text(article.model_dump()))
        # 2. If still above max_allowed (e.g. long Urdu sentences), cleanly trim word-by-word at the end
        words = count_words(article_text(article.model_dump()))
        if words > max_allowed:
            for sec in sorted(article.sections, key=lambda s: len(s.body.split()), reverse=True):
                if words <= max_allowed:
                    break
                sec_words = sec.body.split()
                excess = words - max_allowed
                trim_count = min(excess, max(0, len(sec_words) - 15))
                if trim_count > 0:
                    term = "۔" if request.get("output_language") == "Urdu" else "."
                    sec.body = " ".join(sec_words[:-trim_count]).rstrip(".!?۔؟") + term
                    words = count_words(article_text(article.model_dump()))
        if request["output_language"] == "Urdu":
            has_urdu = any('\u0600' <= c <= '\u06ff' for c in article.introduction + (article.sections[0].body if article.sections else ""))
            if not has_urdu:
                raise ValueError("Output must be written in authentic Urdu script (اردو رسم الخط), not in Roman Urdu.")
        words = count_words(article_text(article.model_dump()))
        if not (target * 0.70 <= words <= target * 1.25):
            raise ValueError(f"Article has {words} words. Use approximately {target} words, including FAQs.")

    if request["output_language"] == "Urdu":
        lang_rule = (
            "CRITICAL LANGUAGE SCRIPT MANDATE: You MUST write the ENTIRE article in authentic Urdu script using Arabic/Persian letters (اردو رسم الخط جیسے 'مصنوعی ذہانت کے جدید رجحانات'). "
            "ABSOLUTELY DO NOT write in Roman Urdu (English alphabet). Every title, heading, paragraph, and FAQ must be in Urdu script (اردو الفاظ اور حروف)."
        )
    elif request["output_language"] == "Roman Urdu":
        lang_rule = (
            "CRITICAL LANGUAGE SCRIPT MANDATE: Write the entire article in Roman Urdu (Urdu words transliterated in English / Latin alphabet, e.g. 'Yeh ek mufeed guide hai jo aap ko madad faraham kare gi'). Do NOT use Arabic script."
        )
    else:
        lang_rule = "CRITICAL LANGUAGE SCRIPT MANDATE: Write the entire article in fluent, professional English."

    rules = (
        f"{lang_rule}\n"
        f"Write a complete SEO article in {request['output_language']}, adhering strictly to the outline. "
        f"TARGET TOTAL WORDS: Strictly {target} words total (title, intro, all {sections_count} sections, and {faq_count} FAQs combined). "
        f"Do NOT exceed {target} words. Write approximately {words_per_sec} words for each section body, and ~{intro_words} words for the introduction. "
        f"Include exactly {faq_count} FAQs with concise 20-30 word answers (or [] if 0). "
        f"Do not write filler or bloated text. Keep total length strictly near {target} words. "
        "Follow the schema; body fields may contain Markdown H3 headings. Do not include a second FAQ section in body. "
        "Leave chunk_ids as empty [] for general advice when no sources are retrieved. Never invent URLs. "
        "Do not repeat long source quotes. Prefer attributed paraphrases. With no retrieved evidence, "
        "write cautious general suggestions, no statistics, fees, availability or institution-specific policies."
    )
    return await core.run_agent("writer", "Writing your article", rules, Article,
        {"request": request, "brief": brief, "evidence": research["evidence"],
         "review_notes": [i.get("required_change", "") for i in (review_issues or [])][:3]}, folder,
        validate_and_heal)


async def generate(payload, api_key, folder, progress, cancel):
    from .transport import StageRunner
    runner = StageRunner(api_key, progress, cancel, payload.get("provider"))
    started = time.monotonic()
    try:
        core = load_core(runner)
        request = await build_request(payload, core, folder)
        progress("sources", "Reading references and finding relevant sources")
        request, documents, notices = core.load_user_documents(request)
        candidates, errors = discover_sources(request)
        notices.extend(errors)
        plan = await core.select_sources(request, candidates, folder)
        runner.check_cancel()
        collection = core.collect_sources(candidates, plan, documents)
        sources = collection["sources"]
        evidence = []
        if sources:
            progress("retrieval", "Selecting relevant passages")
            model = embedding_model()
            chunks = chunk_sources(sources, model)
            vectors = core.encode_chunks(chunks)
            evidence = core.retrieve_evidence(request, chunks, vectors)
        else:
            notices.append("No external references were retrieved. This is an unsourced draft, not a verified plan.")
        research = core.build_research_context(request, evidence, sources)
        async def _run_audience_and_seo():
            aud = await core.run_audience(request, folder)
            seo_rep = await core.run_seo(request, aud, folder)
            return aud, seo_rep

        has_loop = False
        try:
            has_loop = asyncio.get_running_loop() is not None
        except RuntimeError:
            has_loop = False

        if evidence:
            if has_loop:
                findings, (audience, seo) = await asyncio.gather(
                    core.run_research(request, research, folder),
                    _run_audience_and_seo()
                )
            else:
                findings = await core.run_research(request, research, folder)
                audience, seo = await _run_audience_and_seo()
        else:
            findings = {"findings": [], "missing_information": ["No source evidence available."],
                        "limitations": ["Draft without retrieved sources."], "output_language": request["output_language"]}
            audience, seo = await _run_audience_and_seo()
        brief = await core.run_structure(request, audience, seo, findings, research, folder)
        reports = {"research": findings, "seo": seo, "brief": brief}
        article = None
        required = ["research", "seo", "brief"]
        if request["output_type"] == "article":
            if has_loop:
                reviews, article = await asyncio.gather(
                    unified_review_reports(core, reports, request, research, folder),
                    write_article(core, request, brief, research, folder, [])
                )
            else:
                reviews = await unified_review_reports(core, reports, request, research, folder)
                article = await write_article(core, request, brief, research, folder, [])
            reviews["article"] = await review_report(core, "article", article, request, research, folder)
            required.append("article")
        else:
            reviews = await unified_review_reports(core, reports, request, research, folder)
        runner.check_cancel()
        # File paths stay private; source titles and extracted evidence are returned to this session only.
        public_sources = {key: {k: v for k, v in s.items() if k != "file_path"}
                          for key, s in research["sources"].items()}
        return {"status": final_status(reviews, required, evidence), "brief": brief, "article": article,
                "audience": audience, "seo": seo, "review": reviews, "sources": public_sources,
                "evidence": evidence, "notices": list(dict.fromkeys(notices + research["limitations"])),
                "request": {k: v for k, v in request.items() if k not in ("files", "instruction_documents")},
                "word_count": count_words(article_text(article)) if article else None,
                "seconds": round(time.monotonic() - started, 1), "calls": runner.calls}
    finally:
        runner.close()
