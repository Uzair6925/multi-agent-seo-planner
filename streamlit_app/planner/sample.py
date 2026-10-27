import json
from pathlib import Path


def sample_result():
    sample_file = Path(__file__).resolve().parents[1] / "sample_data" / "sample_run.json"
    if sample_file.exists():
        try:
            data = json.loads(sample_file.read_text(encoding="utf-8"))
            # Transform into the contract format expected by show_results
            sources_dict = {}
            for s in data.get("sources", []):
                sources_dict[s["source_id"]] = {
                    "title": s.get("title", "Reference"),
                    "url": s.get("url")
                }
            evidence_list = []
            for e in data.get("evidence", []):
                chunk_id = e.get("chunk_id", "")
                src_id = chunk_id.split("-")[0] if "-" in chunk_id else "S1"
                evidence_list.append({
                    "source_id": src_id,
                    "chunk_id": chunk_id,
                    "location": e.get("location", "Webpage"),
                    "text": e.get("text", "")
                })

            review_dict = {}
            for target, r in data.get("review", {}).items():
                assessments = []
                for a in r.get("assessments", []):
                    assessments.append({
                        "location": a.get("location", ""),
                        "verdict": a.get("verdict", "editorial"),
                        "explanation": a.get("explanation", ""),
                        "citations": a.get("citations", [])
                    })
                review_dict[target] = {
                    "issues": r.get("issues", []),
                    "assessments": assessments,
                    "limitations": r.get("limitations", [])
                }

            brief = dict(data.get("brief", {}))
            if "faqs" in brief:
                brief["faqs"] = brief["faqs"][:2]
            if "outline" in brief:
                brief["outline"] = [{**s, "chunk_ids": []} for s in brief["outline"]]

            return {
                "status": "draft_without_sources",
                "is_sample": True,
                "article": None,
                "brief": brief,
                "audience": {
                    "audience_description": data.get("audience", "Pakistani University Students starting ML"),
                    "reader_needs": [
                        "Practical step-by-step guidance",
                        "Clear math and Python prerequisite roadmap",
                        "Portfolio project recommendations"
                    ],
                    "assumptions": [
                        "Students have basic computer literacy but little AI experience."
                    ]
                },
                "seo": data.get("seo", {
                    "primary_keyword": "Machine Learning course for beginners",
                    "secondary_keywords": ["Python for Machine Learning", "Fundamental math for AI"],
                    "long_tail_keywords": ["career paths in AI Pakistan", "Project-based ML learning"],
                    "search_intent": "informational",
                    "intent_reason": "Students are seeking actionable foundational knowledge."
                }),
                "review": review_dict,
                "sources": sources_dict,
                "evidence": evidence_list,
                "notices": ["Verified Sample Run from Multi-Agent NLP Engine."],
                "request": {
                    "topic": data.get("topic", "Machine Learning course for beginners"),
                    "audience": data.get("audience", "University students in Pakistan"),
                    "output_type": "brief",
                    "output_language": "English"
                },
                "seconds": 0,
                "word_count": None,
                "calls": []
            }
        except Exception:
            pass

    # Fallback minimal sample
    return {
        "status": "draft_without_sources", "article": None,
        "brief": {
            "title": "A Practical Roadmap for Pakistani University Students to Learn Machine Learning",
            "meta_description": "A step-by-step guide for Pakistani university students starting their AI journey.",
            "h1": "Getting Started with Machine Learning: A Beginner's Guide",
            "suggested_keywords": ["Machine Learning course for beginners", "Python for Machine Learning"],
            "search_intent": "informational", "output_language": "English",
            "outline": [
                {"h2": "Foundational Skills: Math and Python Basics", "h3": ["Linear Algebra", "Python Basics"],
                 "coverage_notes": ["Explain foundational concepts."], "chunk_ids": []}
            ],
            "faqs": ["What math is needed?", "Is Python required?"],
            "limitations": ["Preview content. This is not a live generated result."]
        },
        "audience": {
            "audience_description": "University students in Pakistan starting AI",
            "reader_needs": ["Foundational knowledge"],
            "assumptions": ["Basic computer literacy"]
        },
        "seo": {
            "primary_keyword": "Machine Learning course for beginners",
            "secondary_keywords": ["Python for Machine Learning"],
            "long_tail_keywords": ["ML roadmap Pakistan"],
            "search_intent": "informational",
            "intent_reason": "Readers want guidance."
        },
        "review": {}, "sources": {}, "evidence": [],
        "notices": ["Preview content."],
        "request": {
            "topic": "Machine Learning course for beginners",
            "audience": "University students in Pakistan",
            "output_type": "brief",
            "output_language": "English"
        },
        "seconds": 0, "word_count": None, "calls": [], "is_sample": True
    }
