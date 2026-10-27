import re
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=2, max_length=300)
    audience: str = Field(default="General audience", max_length=500)
    instructions: str = Field(default="", max_length=4000)


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str
    body: str = Field(min_length=20)
    chunk_ids: list[str] = Field(default_factory=list)


class FAQ(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    answer: str
    chunk_ids: list[str] = Field(default_factory=list)


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    meta_description: str
    introduction: str
    sections: list[Section] = Field(min_length=2, max_length=8)
    faqs: list[FAQ] = Field(default_factory=list, min_length=0, max_length=8)
    output_language: Literal["English", "Urdu", "Roman Urdu"]


def count_words(text):
    return len(re.findall(r"\S+", text))


def article_text(article):
    parts = [article["introduction"]]
    parts += [s["heading"] + " " + s["body"] for s in article["sections"]]
    parts += [f["question"] + " " + f["answer"] for f in article.get("faqs", [])]
    return "\n\n".join(parts)


def validate_article(article, request, evidence):
    if article.output_language != request["output_language"]:
        raise ValueError("Use the selected output language.")
    if len(article.faqs) != request["faq_count"]:
        raise ValueError(f"Include exactly {request['faq_count']} FAQs.")
    known = {e["chunk_id"] for e in evidence}
    for item in [*article.sections, *article.faqs]:
        if set(item.chunk_ids) - known:
            raise ValueError("Only use provided chunk IDs, or no IDs for editorial advice.")
    words = count_words(article_text(article.model_dump()))
    target = request["target_words"]
    if not target * 0.8 <= words <= target * 1.2:
        raise ValueError(f"Article has {words} words. Use {target} words, within 20%, including FAQs.")


def final_status(reviews, required, evidence):
    for key in required:
        report = reviews.get(key, {})
        assessments = report.get("assessments", [])
        expected = report.get("checked_locations", [])
        locations = [a.get("location") for a in assessments]
        if not expected or set(expected) != set(locations) or len(locations) != len(set(locations)):
            return "review_incomplete"
        for item in assessments:
            if item.get("verdict") not in {"supported", "editorial", "needs_revision"}:
                return "review_incomplete"
            if item["verdict"] == "supported" and not item.get("citations"):
                return "review_incomplete"
    if not evidence:
        return "draft_without_sources"
    if any(r.get("issues") or any(a["verdict"] == "needs_revision" for a in r["assessments"])
           for r in reviews.values()):
        return "needs_revision"
    return "automated_review_passed"
