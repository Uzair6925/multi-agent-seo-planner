from threading import Event
from planner import engine
from planner.sample import sample_result
from test_pipeline import run_immediate


def test_source_free_article_gets_separate_review(monkeypatch, tmp_path):
    from planner import transport
    stages = []

    class FakeRunner:
        def __init__(self, *args):
            self.calls = []

        def check_cancel(self):
            pass

        def close(self):
            pass

        async def __call__(self, name, role, rules, schema, context, folder, validate=None):
            stages.append(name)
            sample = sample_result()
            if name == "intake":
                value = {"topic": "Study planning", "audience": "Students", "instructions": "Simple guidance"}
            elif name == "audience":
                value = {**sample["audience"], "audience_basis": "user_provided", "tone": "Clear",
                         "reader_questions": ["How do I begin?"], "output_language": "English"}
            elif name == "seo":
                value = {**sample["seo"], "long_tail_keywords": ["weekly study routine", "study plan for students"],
                         "output_language": "English"}
            elif name == "structure":
                value = sample["brief"]
            elif name == "writer":
                value = {"title": "Study planning", "meta_description": "A practical plan.",
                         "introduction": "Build a flexible plan.",
                         "sections": [{"heading": "Start small", "body": "Choose realistic study tasks. " * 30, "chunk_ids": []},
                                      {"heading": "Review weekly", "body": "Review your weekly plan. " * 30, "chunk_ids": []}],
                         "faqs": [{"question": "How?", "answer": "Start small."}, {"question": "When?", "answer": "Choose a suitable time."}],
                         "output_language": "English"}
            elif name.startswith("review_"):
                value = {"assessments": {loc: {"verdict": "editorial", "explanation": "A suggestion.", "evidence_ids": []}
                                          for loc in context["required_locations"]},
                         "issues": [], "limitations": ["No source evidence."]}
            else:
                raise AssertionError(name)
            report = schema.model_validate(value)
            if validate:
                validate(report)
            return report.model_dump()

    monkeypatch.setattr(transport, "StageRunner", FakeRunner)
    monkeypatch.setattr(engine, "discover_sources", lambda request: ([], ["Search unavailable"]))
    payload = {"mode": "prompt", "prompt": "Study advice for students", "source_urls": [], "language": "English",
               "output_type": "article", "target_words": 300, "faq_count": 2, "use_web_search": True, "files": []}
    result = run_immediate(engine.generate(payload, "unused", tmp_path, lambda *args: None, Event()))
    assert result["status"] == "draft_without_sources"
    assert result["sources"] == {}
    assert result["evidence"] == []
    assert "writer" in stages and "review_article" in stages
    assert len(result["article"]["faqs"]) == 2
    assert "article" in result["review"]
