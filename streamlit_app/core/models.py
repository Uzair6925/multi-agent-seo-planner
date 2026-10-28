import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class EvidenceQuote(StrictModel):
    chunk_id: str = Field(min_length=1)
    quote: str = Field(min_length=8)


class ResearchFinding(StrictModel):
    statement: str = Field(min_length=1)
    citations: list[EvidenceQuote] = Field(min_length=1, max_length=3)


class ResearchReport(StrictModel):
    findings: list[ResearchFinding] = Field(min_length=1, max_length=6)
    missing_information: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    output_language: str = Field(min_length=1)


class AudienceReport(StrictModel):
    target_persona: str = Field(min_length=1)
    knowledge_level: Literal["Beginner", "Intermediate", "Advanced"]
    search_intent_context: str = Field(min_length=1)
    content_tone: str = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    output_language: str = Field(min_length=1)


class SEOReport(StrictModel):
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: list[str] = Field(min_length=1, max_length=8)
    long_tail_keywords: list[str] = Field(min_length=1, max_length=8)
    search_intent: Literal["informational", "commercial", "transactional", "navigational"]
    intent_reason: str = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    output_language: str = Field(min_length=1)


class OutlineSection(StrictModel):
    h2: str = Field(min_length=1)
    h3: list[str] = Field(default_factory=list, max_length=4)
    coverage_notes: list[str] = Field(min_length=1, max_length=3)
    chunk_ids: list[str] = Field(default_factory=list, max_length=4)


class ContentBrief(StrictModel):
    title: str = Field(min_length=1)
    meta_description: str = Field(min_length=1)
    suggested_keywords: list[str] = Field(min_length=1, max_length=10)
    search_intent: Literal["informational", "commercial", "transactional", "navigational"]
    h1: str = Field(min_length=1)
    outline: list[OutlineSection] = Field(min_length=2, max_length=5)
    faqs: list[str] = Field(min_length=1, max_length=6)
    limitations: list[str] = Field(min_length=1)
    output_language: str = Field(min_length=1)


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
