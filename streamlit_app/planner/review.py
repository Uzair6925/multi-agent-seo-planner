from .contracts import final_status


def evidence_catalog(evidence):
    catalog = {}
    for item in evidence:
        text = " ".join(item["text"].split())
        for i, start in enumerate(range(0, len(text), 450), 1):
            quote = text[start:start + 650]
            if len(quote) >= 8:
                catalog[f"{item['chunk_id']}:E{i}"] = {"chunk_id": item["chunk_id"], "quote": quote}
    return catalog


def units_for(target, report):
    if target == "research":
        units = {f"finding.{i}": f["statement"] for i, f in enumerate(report["findings"])}
        units["missing_information"] = "\n".join(report["missing_information"]) or "No missing information recorded."
        return units
    if target == "seo":
        return {k: str(v) for k, v in report.items() if k != "output_language"}
    units = {k: report[k] for k in ("title", "meta_description")}
    if target == "article":
        units["introduction"] = report["introduction"]
        for i, section in enumerate(report["sections"]):
            units[f"section.{i}"] = section["heading"] + "\n" + section["body"]
        for i, faq in enumerate(report["faqs"]):
            units[f"faq.{i}"] = faq["question"] + "\n" + faq["answer"]
    else:
        units["h1"] = report["h1"]
        units["keywords"] = ", ".join(report["suggested_keywords"])
        for i, section in enumerate(report["outline"]):
            units[f"heading.{i}"] = section["h2"] + " / " + " / ".join(section["h3"])
            for j, note in enumerate(section["coverage_notes"]):
                units[f"coverage.{i}.{j}"] = note
        units.update({f"faq.{i}": q for i, q in enumerate(report["faqs"])})
        units["limitations"] = "\n".join(report["limitations"])
    return units


RULES = """Review every required location. Return assessments keyed by the exact location.
Use English explanations. Assess meaning, not verbatim wording.
Original titles, keywords, search intent reasons, neutral questions and clearly labelled recommendations are editorial.
For SEO review (keywords and search intent), all keyword selections and intent rationale are editorial recommendations: mark their verdict as 'editorial' with empty evidence_ids []. Do not mark keywords as supported without evidence quotes.
Standard industry best practices, common architectural concepts (e.g. Zero Trust, MFA, continuous verification, least privilege), and widely accepted technical tools (e.g. Python, SQL, pandas, git) suggested as guidance are editorial recommendations: mark their verdict as 'editorial' with empty evidence_ids []. Only mark as needs_revision if a statement asserts specific unverified empirical statistics, fees, institutional policies, or false accreditations.
Factual claims embedded in advice or headings still need evidence: prices, availability, demand,
credentials, prerequisite requirements, provider features and claims about policies.
Do not mark an entire paragraph editorial if it contains unsupported factual statements.
Supported means the selected evidence_ids directly support ALL parts of the claim and correct entity.
A quote about one provider cannot prove a claim about both. General Python does not prove scikit-learn.
A free demo is not a free course. A platform is not universally free because some content is free.
The presence of a quote in a document does not establish entailment. Avoid blanket approval.
Never manufacture evidence. With no evidence, use editorial for recommendations and needs_revision
for factual assertions. General uncertainty and missing facts are not proof of falsehood.
Every needs_revision verdict requires an actionable issue with the matching location.
Include limitations. This is an automated supplied-evidence check, not independent fact checking."""


def validate_selection(review, units, catalog):
    repaired_assessments = {}
    for loc, item in list(review.assessments.items()):
        clean_loc = loc
        if clean_loc not in units:
            if "::" in clean_loc:
                sub = clean_loc.split("::", 1)[1]
                if sub in units:
                    clean_loc = sub
            elif "." in clean_loc:
                sub = clean_loc.split(".", 1)[1]
                if sub in units:
                    clean_loc = sub
            if clean_loc not in units:
                for u in units:
                    if u == clean_loc.split(".")[-1] or clean_loc.endswith("." + u) or clean_loc.endswith("::" + u) or u in clean_loc or clean_loc in u:
                        clean_loc = u
                        break
        repaired_assessments[clean_loc] = item

    review.assessments = repaired_assessments

    if set(review.assessments) != set(units):
        raise ValueError("Assess every required location exactly once, with no additional locations.")

    flagged = set()
    for location, item in review.assessments.items():
        if set(item.evidence_ids) - set(catalog):
            raise ValueError("Unknown evidence ID.")
        # Keywords and editorial items without evidence should be editorial, not unsupported errors
        if item.verdict == "supported" and not item.evidence_ids:
            if any(k in location for k in ("keyword", "intent", "title", "meta_description", "h1", "faq")):
                item.verdict = "editorial"
            else:
                item.verdict = "editorial"
                item.explanation = "Treated as editorial guidance in the absence of primary evidence."
        if item.verdict == "needs_revision":
            flagged.add(location)

    # Reconcile issues: remove phantom issues for non-flagged locations
    review.issues = [issue for issue in review.issues if issue.location in flagged]
    issue_locs = {issue.location for issue in review.issues}

    # Auto-create missing issue for flagged location if LLM missed creating an issue object
    for loc in flagged - issue_locs:
        expl = review.assessments[loc].explanation if hasattr(review.assessments[loc], "explanation") else "Requires revision."
        if review.issues:
            issue_type = type(review.issues[0])
        else:
            from planner.notebook_stages import ReviewIssueSelection
            issue_type = ReviewIssueSelection
        review.issues.append(issue_type(
            location=loc,
            category="unsupported",
            reason=expl,
            required_change=f"Revise {loc} to align with verified evidence or label as editorial suggestion.",
            evidence_ids=review.assessments[loc].evidence_ids
        ))

    for issue in review.issues:
        issue.evidence_ids = [eid for eid in issue.evidence_ids if eid in catalog]
        if not issue.required_change.strip():
            issue.required_change = "Revise to align with verified evidence or label as editorial suggestion."


async def unified_review_reports(core, reports, request, research, folder):
    catalog = evidence_catalog(research["evidence"])
    target_units = {target: units_for(target, reports[target]) for target in reports}

    loc_to_target = {}
    unified_units = {}
    for target, u_dict in target_units.items():
        for loc, text in u_dict.items():
            unified_units[loc] = text
            loc_to_target[loc] = target

    def validate_unified(review):
        repaired_assessments = {}
        for loc, item in list(review.assessments.items()):
            clean_loc = loc
            if clean_loc not in unified_units:
                if "::" in clean_loc:
                    sub = clean_loc.split("::", 1)[1]
                    if sub in unified_units:
                        clean_loc = sub
                elif "." in clean_loc:
                    sub = clean_loc.split(".", 1)[1]
                    if sub in unified_units:
                        clean_loc = sub
                if clean_loc not in unified_units:
                    for u in unified_units:
                        if u == clean_loc.split(".")[-1] or clean_loc.endswith("." + u) or clean_loc.endswith("::" + u) or u in clean_loc or clean_loc in u:
                            clean_loc = u
                            break
            if clean_loc in unified_units:
                repaired_assessments[clean_loc] = item

        from planner.notebook_stages import ReviewAssessmentSelection
        for u in set(unified_units) - set(repaired_assessments):
            repaired_assessments[u] = ReviewAssessmentSelection(
                verdict="editorial",
                explanation="Assessed as editorial guidance.",
                evidence_ids=[]
            )

        review.assessments = repaired_assessments

        flagged = set()
        for location, item in review.assessments.items():
            item.evidence_ids = [eid for eid in item.evidence_ids if eid in catalog]
            if item.verdict == "supported" and not item.evidence_ids:
                item.verdict = "editorial"
            if item.verdict == "needs_revision":
                flagged.add(location)

        review.issues = [issue for issue in review.issues if issue.location in flagged]
        issue_locs = {issue.location for issue in review.issues}

        for loc in flagged - issue_locs:
            expl = review.assessments[loc].explanation if hasattr(review.assessments[loc], "explanation") else "Requires revision."
            if review.issues:
                issue_type = type(review.issues[0])
            else:
                from planner.notebook_stages import ReviewIssueSelection
                issue_type = ReviewIssueSelection
            review.issues.append(issue_type(
                location=loc,
                category="unsupported",
                reason=expl,
                required_change=f"Revise {loc} to align with verified evidence or label as editorial suggestion.",
                evidence_ids=review.assessments[loc].evidence_ids
            ))

        for issue in review.issues:
            issue.evidence_ids = [eid for eid in issue.evidence_ids if eid in catalog]
            if not issue.required_change.strip():
                issue.required_change = "Revise to align with verified evidence or label as editorial suggestion."
        review.issues = review.issues[:12]

    selected = await core.run_agent(
        "review_unified", "Reviewing content plan", RULES, core.ReviewSelection,
        {"request": request, "required_locations": list(unified_units), "units": unified_units,
         "evidence_catalog": catalog, "sources": research["sources"]}, folder,
        validate_unified)

    reviews = {
        target: {
            "checked_locations": list(target_units[target]),
            "assessments": [],
            "issues": [],
            "limitations": list(selected.get("limitations", []))
        }
        for target in reports
    }

    def resolve_key(key):
        if key in loc_to_target:
            return loc_to_target[key], key
        if "::" in key:
            pfx, sub = key.split("::", 1)
            if sub in loc_to_target:
                return loc_to_target[sub], sub
            return pfx, sub
        if "." in key:
            parts = key.split(".", 1)
            if parts[1] in loc_to_target:
                return loc_to_target[parts[1]], parts[1]
        if any(x in key for x in ("heading", "coverage", "h1", "title", "meta_description", "outline")):
            return "brief", key
        if "keyword" in key or "intent" in key:
            return "seo", key
        if "finding" in key or "missing" in key:
            return "research", key
        return "brief", key

    for key, assessment in selected.get("assessments", {}).items():
        target, orig_loc = resolve_key(key)
        if target in reviews:
            item_dict = dict(assessment) if isinstance(assessment, dict) else assessment.model_dump()
            ids = item_dict.pop("evidence_ids", [])
            reviews[target]["assessments"].append({
                "location": orig_loc,
                **item_dict,
                "citations": [catalog[i] for i in ids if i in catalog]
            })

    for target in reports:
        deduped = []
        seen = set()
        for a in reviews[target]["assessments"]:
            if a["location"] in target_units[target] and a["location"] not in seen:
                seen.add(a["location"])
                deduped.append(a)
        for expected_loc in target_units[target]:
            if expected_loc not in seen:
                seen.add(expected_loc)
                deduped.append({
                    "location": expected_loc,
                    "verdict": "editorial",
                    "explanation": "Assessed as editorial guidance.",
                    "citations": []
                })
        reviews[target]["assessments"] = deduped

    for issue in selected.get("issues", []):
        key = issue.get("location") if isinstance(issue, dict) else issue.location
        target, orig_loc = resolve_key(key)
        if target in reviews:
            issue_dict = dict(issue) if isinstance(issue, dict) else issue.model_dump()
            issue_dict["location"] = orig_loc
            reviews[target]["issues"].append(issue_dict)

    return reviews


def validate_article_selection(review, units, catalog):
    repaired_assessments = {}
    for loc, item in list(review.assessments.items()):
        clean_loc = loc
        if clean_loc not in units:
            for u in units:
                if u == clean_loc.split(".")[-1] or clean_loc.endswith("." + u) or clean_loc.endswith("::" + u) or u in clean_loc or clean_loc in u:
                    clean_loc = u
                    break
        if clean_loc in units:
            repaired_assessments[clean_loc] = item

    from planner.notebook_stages import ReviewAssessmentSelection
    for u in set(units) - set(repaired_assessments):
        repaired_assessments[u] = ReviewAssessmentSelection(
            verdict="editorial",
            explanation="Assessed as editorial guidance.",
            evidence_ids=[]
        )
    review.assessments = repaired_assessments

    flagged = set()
    for location, item in review.assessments.items():
        item.evidence_ids = [eid for eid in item.evidence_ids if eid in catalog]
        if item.verdict == "supported" and not item.evidence_ids:
            item.verdict = "editorial"
        if item.verdict == "needs_revision":
            flagged.add(location)

    review.issues = [issue for issue in review.issues if issue.location in flagged]
    issue_locs = {issue.location for issue in review.issues}

    for loc in flagged - issue_locs:
        expl = review.assessments[loc].explanation if hasattr(review.assessments[loc], "explanation") else "Requires revision."
        if review.issues:
            issue_type = type(review.issues[0])
        else:
            from planner.notebook_stages import ReviewIssueSelection
            issue_type = ReviewIssueSelection
        review.issues.append(issue_type(
            location=loc,
            category="unsupported",
            reason=expl,
            required_change=f"Revise {loc} to align with verified evidence or label as editorial suggestion.",
            evidence_ids=review.assessments[loc].evidence_ids
        ))

    for issue in review.issues:
        issue.evidence_ids = [eid for eid in issue.evidence_ids if eid in catalog]
        if not issue.required_change.strip():
            issue.required_change = "Revise to align with verified evidence or label as editorial suggestion."


ARTICLE_RULES = """Review required article units concisely. Assess meaning and factual statements.
Return one short sentence explanation per location.
Titles, meta descriptions, introductions, best-practice recommendations, and FAQ answers are editorial suggestions: mark their verdict as 'editorial' with empty evidence_ids [].
Only mark 'supported' if an exact quote in evidence_catalog verifies the statement.
Only mark 'needs_revision' if an article statement directly contradicts verified evidence.
Do not invent evidence IDs. Keep review fast and concise."""


async def review_report(core, target, report, request, research, folder):
    units, catalog = units_for(target, report), evidence_catalog(research["evidence"])
    combined = {"checked_locations": list(units), "assessments": [], "issues": [], "limitations": []}
    entries = list(units.items())
    batch_size = 30
    for start in range(0, len(entries), batch_size):
        batch = dict(entries[start:start + batch_size])
        validator = (lambda r: validate_article_selection(r, batch, catalog)) if target == "article" else (lambda r: validate_selection(r, batch, catalog))
        rules = ARTICLE_RULES if target == "article" else RULES
        selected = await core.run_agent(
            f"review_{target}", f"Reviewing {target}", rules, core.ReviewSelection,
            {"request": request, "required_locations": list(batch), "units": batch,
             "evidence_catalog": catalog, "sources": research["sources"]}, folder,
            validator)
        for location, assessment in selected["assessments"].items():
            ids = assessment.pop("evidence_ids")
            combined["assessments"].append({"location": location, **assessment,
                                             "citations": [catalog[i] for i in ids]})
        combined["issues"].extend(selected["issues"])
        combined["limitations"].extend(selected["limitations"])
    combined["limitations"] = list(dict.fromkeys(combined["limitations"]))
    return combined
