from planner.review import units_for

sample_research = {
    "findings": [{"statement": "Zero Trust verifies every request.", "citations": []}],
    "missing_information": [],
    "limitations": [],
    "output_language": "English"
}
sample_seo = {
    "primary_keyword": "zero trust smb",
    "secondary_keywords": ["mfa guide"],
    "search_intent": "informational",
    "output_language": "English"
}
sample_brief = {
    "title": "Zero Trust Guide",
    "meta_description": "A guide for SMBs",
    "h1": "Zero Trust Guide",
    "suggested_keywords": ["zero trust"],
    "outline": [{"h2": "What is Zero Trust", "h3": ["Basics"], "coverage_notes": ["Explain continuous verification"]}],
    "faqs": ["What is MFA?"],
    "limitations": []
}

u_res = units_for("research", sample_research)
u_seo = units_for("seo", sample_seo)
u_brief = units_for("brief", sample_brief)

print("Research units:", list(u_res.keys()))
print("SEO units:", list(u_seo.keys()))
print("Brief units:", list(u_brief.keys()))

all_keys = list(u_res.keys()) + list(u_seo.keys()) + list(u_brief.keys())
print("Total keys:", len(all_keys), "Unique keys:", len(set(all_keys)))
assert len(all_keys) == len(set(all_keys)), "Duplicate keys found!"
print("Zero collisions! All keys are 100% unique!")
