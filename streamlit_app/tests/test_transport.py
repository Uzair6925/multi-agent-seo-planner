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
