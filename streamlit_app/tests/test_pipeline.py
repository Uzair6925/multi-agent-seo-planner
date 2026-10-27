import socket
from types import SimpleNamespace
from threading import Event
import pytest
from planner.contracts import Article, validate_article, final_status
from planner.security import public_url, validate_upload, redact
from planner.review import validate_selection, units_for
from planner.engine import load_core, build_request, validate_quotes
from planner.exports import download_markdown, make_pdf
from planner.sample import sample_result


def run_immediate(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Test coroutine unexpectedly performed I/O")


@pytest.mark.parametrize("ip", ["127.0.0.1", "172.17.0.1", "192.168.1.1", "169.254.169.254", "::1"])
def test_private_urls_blocked(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (ip, 443))])
    with pytest.raises(ValueError):
        public_url("https://example.com")


def test_upload_limits_and_format():
    with pytest.raises(ValueError):
        validate_upload("bad.pdf", b"not a PDF")
    with pytest.raises(ValueError):
        validate_upload("app.py", b"print(1)")
    assert validate_upload("notes.txt", b"hello") == ".txt"


def test_missing_article_review_never_passes():
    complete = {"checked_locations": ["title"], "assessments": [
        {"location": "title", "verdict": "editorial", "citations": []}], "issues": []}
    assert final_status({"brief": complete}, ["brief", "article"], [{}]) == "review_incomplete"
    assert final_status({"brief": complete}, ["brief"], []) == "draft_without_sources"


def test_flagged_assessment_cannot_pass_without_issue():
    review = {"checked_locations": ["title"], "assessments": [
        {"location": "title", "verdict": "needs_revision", "citations": []}], "issues": []}
    assert final_status({"brief": review}, ["brief"], [{}]) == "needs_revision"


def test_quote_cannot_be_reassigned():
    quote = SimpleNamespace(chunk_id="C1", quote="Exact sentence here.")
    with pytest.raises(ValueError):
        validate_quotes([quote], [{"chunk_id": "C2", "text": "Exact sentence here."}])
    assert quote.chunk_id == "C1"


def test_review_coverage_and_unknown_evidence():
    core = load_core(None)
    review = core.ReviewSelection(assessments={"x": {"verdict": "supported", "explanation": "yes", "evidence_ids": ["missing"]}}, limitations=["Automated"])
    with pytest.raises(ValueError):
        validate_selection(review, {"x": "claim"}, {})
    with pytest.raises(ValueError):
        validate_selection(review, {"x": "claim", "y": "another"}, {})


def test_prompt_keeps_selected_controls(tmp_path):
    async def runner(*args, **kwargs):
        return {"topic": "Gardening", "audience": "Beginners", "instructions": "Keep it simple"}
    core = load_core(runner)
    payload = {"mode": "prompt", "prompt": "Help beginners garden", "language": "Roman Urdu",
               "output_type": "article", "use_web_search": False, "source_urls": [],
               "target_words": 300, "faq_count": 2, "files": []}
    result = run_immediate(build_request(payload, core, tmp_path))
    assert result["output_type"] == "article"
    assert result["use_web_search"] is False
    assert result["output_language"] == "Roman Urdu"
    assert "Keep it simple" in result["instructions"]


def test_article_faq_count_and_citation_validation():
    article = Article(title="Title", meta_description="Description", introduction="An introduction",
                      sections=[{"heading": "First", "body": "word " * 120, "chunk_ids": []},
                                {"heading": "Second", "body": "word " * 120, "chunk_ids": []}],
                      faqs=[{"question": "Why?", "answer": "Because."}, {"question": "How?", "answer": "Carefully."}],
                      output_language="English")
    request = {"target_words": 300, "faq_count": 2, "output_language": "English"}
    validate_article(article, request, [])
    article.sections[0].chunk_ids = ["invented"]
    with pytest.raises(ValueError):
        validate_article(article, request, [])
    article.sections[0].chunk_ids = []
    request["faq_count"] = 3
    with pytest.raises(ValueError):
        validate_article(article, request, [])


def test_exports_have_review_disclosure():
    result = sample_result()
    text = download_markdown(result)
    assert "Draft without retrieved sources" in text
    assert "not independent fact checking" in text
    assert make_pdf(result).startswith(b"%PDF")


def test_api_key_redaction():
    assert "gsk_" not in redact("Failed gsk_secretvalue")


def test_no_shared_core_state():
    first, second = load_core(None), load_core(None)
    first.SETTINGS["top_k"] = 99
    assert second.SETTINGS["top_k"] == 5
