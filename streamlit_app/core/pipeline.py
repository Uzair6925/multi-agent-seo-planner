import asyncio
from typing import Callable
from crewai import LLM

from core.models import AudienceReport, ContentBrief, ResearchReport, ReviewSelection, SEOReport
from core.retrieval import chunk_text, discover_sources, fetch_web_page, search_evidence
from core.agents import (
    review_evidence_catalog, review_units, resolve_review_evidence,
    run_agent_stage, validate_quotes, validate_review_selection
)


async def execute_pipeline(
    topic: str,
    audience: str,
    language: str,
    instructions: str,
    source_urls: list[str],
    uploaded_docs: list[dict],
    use_web_search: bool,
    api_key: str,
    model_name: str = "groq/openai/gpt-oss-20b",
    status_callback: Callable = None,
) -> dict:
    def notify(msg: str):
        if status_callback:
            status_callback(msg)

    llm = LLM(
        model=model_name,
        api_key=api_key,
        temperature=0.2,
        reasoning_effort="low",
        max_tokens=4096,
        timeout=90,
    )

    request = {
        "topic": topic.strip(),
        "audience": audience.strip() or None,
        "output_language": language,
        "instructions": instructions.strip(),
        "source_urls": source_urls,
        "use_web_search": use_web_search,
    }

    notify("🔍 Step 1: Discovering and fetching reference sources...")
    candidates, _ = discover_sources(request)
    effective_request = dict(request)
    effective_request["instruction_documents"] = []
    sources = []

    # Process uploaded documents
    for doc in uploaded_docs:
        if doc.get("role") == "user_instructions":
            effective_request["instruction_documents"].append(doc)
        else:
            sources.append({
                "title": doc["title"],
                "url": None,
                "text": "\n".join(s["text"] for s in doc["sections"]),
                "source_type": "uploaded_document",
            })

    # Validate instruction budget
    inst_size = len(effective_request["instructions"]) + sum(
        len(s["text"]) for doc in effective_request["instruction_documents"] for s in doc["sections"]
    )
    if inst_size > 6000:
        raise ValueError(
            f"Instruction text exceeds 6,000 characters ({inst_size} chars). "
            "Please shorten it or switch document role to 'Reference Evidence'."
        )

    request = effective_request

    # Process web sources
    for item in candidates:
        if len(sources) >= 3:
            break
        try:
            content = fetch_web_page(item["url"])
            if len(content.split()) >= 40:
                sources.append({
                    "title": item["title"],
                    "url": item["url"],
                    "text": content,
                    "source_type": "web",
                })
        except Exception:
            continue

    if not sources:
        raise ValueError("Could not extract text from search candidates or supplied documents.")

    notify(f"🧠 Step 2: Indexing {len(sources)} sources into vector space...")
    all_chunks = []
    for s_idx, src in enumerate(sources, 1):
        chunks = chunk_text(src["text"])
        for c_idx, c_text in enumerate(chunks, 1):
            all_chunks.append({
                "chunk_id": f"S{s_idx}-C{c_idx}",
                "source_title": src["title"],
                "source_url": src.get("url"),
                "text": c_text,
            })

    query = f"{topic} {audience}".strip()
    evidence = search_evidence(query, all_chunks, top_k=4)
    research_context = {"sources": sources, "evidence": evidence}
    catalog = review_evidence_catalog(evidence)

    reports = {}

    # 1. Research Agent
    notify("🔬 Step 3.1: Running Research Agent (Verbatim Evidence Extraction)...")
    research_rules = (
        "Extract findings strictly grounded in the supplied evidence. "
        "Every finding statement MUST have 1-3 citations with verbatim quotes and chunk IDs from context. "
        "Do not invent claims."
    )
    def validate_research(report: ResearchReport):
        all_quotes = [q for f in report.findings for q in f.citations]
        validate_quotes(all_quotes, evidence)

    reports["research"] = await run_agent_stage(
        "research", "Evidence Research Analyst", research_rules, ResearchReport,
        {"request": request, "evidence": evidence}, llm, validate_research, status_callback=notify
    )
    await asyncio.sleep(2)

    # 2. Audience Agent
    notify("👥 Step 3.2: Running Audience Analysis Agent...")
    audience_rules = (
        "Analyze the target audience, knowledge level, search intent, and tone. "
        "Label any assumptions in limitations."
    )
    reports["audience"] = await run_agent_stage(
        "audience", "Audience and Persona Analyst", audience_rules, AudienceReport,
        {"request": request}, llm, status_callback=notify
    )
    await asyncio.sleep(2)

    # 3. SEO Agent
    notify("🎯 Step 3.3: Running SEO Strategy Agent...")
    seo_rules = (
        "Synthesize keyword tiers (primary, secondary, long_tail) and search intent matching the topic."
    )
    reports["seo"] = await run_agent_stage(
        "seo", "SEO Keyword and Intent Strategist", seo_rules, SEOReport,
        {"request": request, "audience": reports["audience"]}, llm, status_callback=notify
    )
    await asyncio.sleep(2)

    # 4. Structure Planner Agent
    notify("📝 Step 3.4: Running Content Structure Planner Agent...")
    structure_rules = (
        "Create a concise content brief. Include: title, meta_description, suggested_keywords, "
        "search_intent, h1, outline (2-5 H2 sections with coverage_notes and chunk_ids), faqs, limitations."
    )
    reports["brief"] = await run_agent_stage(
        "structure", "Content Structure Planner", structure_rules, ContentBrief,
        {"request": request, "audience": reports["audience"], "seo": reports["seo"],
         "research_report": reports["research"], "research_context": research_context},
        llm, status_callback=notify
    )
    await asyncio.sleep(2)

    # Review Phase
    notify("🛡️ Step 4: Running Evidence & Content Reviewer (Audit & Fallacy Check)...")
    reviews = {}
    for target in ("research", "seo", "brief"):
        units = review_units(target, reports[target])
        review_rules = (
            "Review the report against evidence. Output assessments object keyed by unit path. "
            "Explanations and issue reasons MUST be in ROMAN URDU (Latin script). "
            "Rules: Free Demo != Free Course. supported requires evidence IDs."
        )
        def val_review(r: ReviewSelection):
            validate_review_selection(r, units, catalog, evidence)

        selected = await run_agent_stage(
            f"review_{target}", "Evidence and Content Reviewer", review_rules, ReviewSelection,
            {"request": request, "target": target, "required_locations": list(units),
             "units": units, "report": reports[target], "evidence_catalog": catalog},
            llm, val_review, status_callback=notify
        )

        assessments = [
            {"location": loc, "verdict": a["verdict"], "explanation": a["explanation"],
             "citations": resolve_review_evidence(a["evidence_ids"], catalog, evidence)}
            for loc, a in selected["assessments"].items()
        ]
        issues = [
            {**{k: v for k, v in iss.items() if k != "evidence_ids"},
             "citations": resolve_review_evidence(iss["evidence_ids"], catalog, evidence)}
            for iss in selected["issues"]
        ]
        reviews[target] = {
            "checked_locations": list(selected["assessments"]),
            "assessments": assessments,
            "issues": issues,
            "limitations": selected["limitations"],
        }
        await asyncio.sleep(2)

    # Bounded Correction Phase
    has_issues = any(bool(r["issues"]) for r in reviews.values())
    status = "needs_revision" if has_issues else "passed_supplied_evidence_review"

    if has_issues and reviews.get("brief", {}).get("issues"):
        notify("🔄 Step 5: Bounded Revision - Updating Content Brief based on Reviewer Feedback...")
        feedback = [{"target": t, **iss} for t, r in reviews.items() for iss in r["issues"]]
        reports["brief"] = await run_agent_stage(
            "correct_structure", "Content Structure Planner", structure_rules, ContentBrief,
            {"request": request, "audience": reports["audience"], "seo": reports["seo"],
             "research_report": reports["research"], "research_context": research_context,
             "previous_draft": reports["brief"], "review_feedback": feedback},
            llm, status_callback=notify
        )

    notify("✅ Pipeline execution complete!")

    return {
        "status": status,
        "topic": topic,
        "audience": audience,
        "brief": reports["brief"],
        "reports": reports,
        "reviews": reviews,
        "evidence": evidence,
        "sources": sources,
    }
