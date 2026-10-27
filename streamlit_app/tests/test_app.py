from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_initial_ui_and_example(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("APP_ACCESS_CODE", raising=False)
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert any(s.label == "Output language" for s in app.selectbox)
    assert not any(t.label == "API key" for t in app.text_input)
    next(b for b in app.button if b.label == "View an example").click().run()
    assert not app.exception
    assert len(app.tabs) == 3
    assert any("Example preview" in x.value for x in app.info)


def test_form_mode_and_article_controls():
    app = AppTest.from_file(APP).run(timeout=30)
    next(r for r in app.radio if r.label == "Create").set_value("Complete article").run()
    assert any(x.label == "Target length" for x in app.number_input)
    next(r for r in app.radio if r.label == "Input method").set_value("Use detailed fields").run()
    assert any(x.label == "Topic" for x in app.text_area)
    assert any(x.label == "Target audience" for x in app.text_area)
    assert not app.exception
