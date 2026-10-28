import os
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_DISABLED"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from types import SimpleNamespace
from threading import Event
from unittest.mock import Mock
import asyncio
from pydantic import BaseModel
from planner.transport import JSONTransport, StageRunner, retry_policy


def fake_completion(text):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text))],
                           usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 20}))


def test_real_crewai_with_mocked_provider(tmp_path):
    class Ready(BaseModel):
        status: str
    runner = StageRunner("gsk_test_not_real", lambda *args: None, Event())
    runner.client.chat.completions.create = Mock(return_value=fake_completion('{"status":"ready"}'))
    result = asyncio.run(runner("test", "Readiness checker", "Return status ready.", Ready, {}, tmp_path))
    assert result == {"status": "ready"}
    assert runner.client.chat.completions.create.call_count == 1
    runner.close()


def test_rate_limits_and_timeout():
    class Error(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"retry-after": "4"})
    assert retry_policy(Error("tokens per minute"), 1) == (True, 4.0)
    assert retry_policy(Error("tokens per day"), 1)[0] is False
    assert retry_policy(TimeoutError("timed out"), 1)[0] is True


def test_transport_never_makes_hidden_second_request():
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=fake_completion('{}')))))
    transport = JSONTransport(client, "openai/gpt-oss-20b", 500)
    assert transport.call("Return JSON").startswith("Final Answer:")
    try:
        transport.call("Again")
    except RuntimeError:
        pass
    else:
        raise AssertionError("A second provider call was allowed")
    assert client.chat.completions.create.call_count == 1


def test_safe_parse_json_sanitizes_excess_lists_and_extra_fields():
    from planner.transport import safe_parse_json
    from planner.notebook_stages import AudienceReport

    raw_excessive_json = """
    {
        "audience_description": "Healthcare executives and clinical IT administrators",
        "audience_basis": "inferred from clinical prompt",
        "assumptions": ["A1", "A2", "A3", "A4", "A5", "A6", "A7"],
        "reader_needs": ["Need 1", "Need 2", "Need 3", "Need 4", "Need 5", "Need 6", "Need 7"],
        "reader_questions": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"],
        "tone": "Professional and analytical",
        "output_language": "English",
        "unexpected_hallucinated_field": "This should be ignored safely"
    }
    """
    parsed = safe_parse_json(raw_excessive_json, AudienceReport)
    assert parsed.audience_basis == "inferred"
    assert len(parsed.assumptions) <= 6
    assert len(parsed.reader_needs) <= 6
    assert len(parsed.reader_questions) <= 6
    assert parsed.audience_description.startswith("Healthcare")


def test_stage_fallback_recovers_audience_failure(tmp_path):
    from planner.notebook_stages import AudienceReport
    runner = StageRunner("gsk_test_not_real", lambda *args: None, Event())
    # Mock completion to return invalid broken text
    runner.client.chat.completions.create = Mock(return_value=fake_completion("NOT_JSON_AT_ALL"))
    context = {"request": {"topic": "Edge AI in Healthcare", "audience": "", "output_language": "English"}}
    result = asyncio.run(runner("audience", "Audience Analyst", "Rules", AudienceReport, context, tmp_path))
    assert result["audience_basis"] == "inferred"
    assert "Healthcare" in result["audience_description"]
    assert len(result["reader_needs"]) >= 1
    runner.close()


def test_safe_parse_json_sanitizes_review_selection_list_and_flaws():
    from planner.transport import safe_parse_json
    from planner.notebook_stages import ReviewSelection

    raw_review_json = """
    {
        "assessments": [
            {
                "location": "heading.0",
                "verdict": "accurate",
                "explanation": "",
                "evidence_ids": ["c1:E1", "c1:E2", "c1:E3", "c1:E4"]
            },
            {
                "location": "heading.1",
                "verdict": "editorial",
                "explanation": "Standard structure",
                "evidence_ids": []
            }
        ],
        "issues": [
            {
                "location": "heading.0",
                "category": "not_supported_custom",
                "reason": "missing quote",
                "required_change": "align with quote",
                "evidence_ids": ["c1:E1"]
            }
        ],
        "limitations": []
    }
    """
    parsed = safe_parse_json(raw_review_json, ReviewSelection)
    assert isinstance(parsed.assessments, dict)
    assert "heading.0" in parsed.assessments
    assert parsed.assessments["heading.0"].verdict == "supported"
    assert len(parsed.assessments["heading.0"].evidence_ids) <= 3
    assert len(parsed.limitations) >= 1
    assert parsed.issues[0].category == "unsupported"


def test_stage_fallback_recovers_review_unified_failure(tmp_path):
    from planner.notebook_stages import ReviewSelection
    runner = StageRunner("gsk_test_not_real", lambda *args: None, Event())
    runner.client.chat.completions.create = Mock(return_value=fake_completion("INVALID_CONTENT_NOT_JSON"))
    context = {"required_locations": ["title", "heading.0", "faq.0"]}
    result = asyncio.run(runner("review_unified", "Reviewing content plan", "Rules", ReviewSelection, context, tmp_path))
    assert "assessments" in result
    assert "title" in result["assessments"]
    assert "heading.0" in result["assessments"]
    assert result["assessments"]["title"]["verdict"] == "editorial"
    runner.close()
