import hmac
import json
import os
import time
from pathlib import Path
from queue import Empty
import streamlit as st
from dotenv import load_dotenv
from planner.exports import content_markdown, download_markdown, make_pdf, safe_markdown, STATUS_LABELS
from planner.jobs import JobManager
from planner.security import validate_upload
from planner.sample import sample_result

load_dotenv(Path(__file__).with_name(".env"))
st.set_page_config(page_title="SEO Content Planner", layout="wide", initial_sidebar_state="auto")


def setting(name):
    value = os.getenv(name, "")
    if not value:
        try:
            if hasattr(st, "secrets") and name in st.secrets:
                value = st.secrets[name]
            elif hasattr(st, "secrets"):
                value = st.secrets.get(name, "")
        except Exception:
            pass
    if isinstance(value, str):
        return value.strip().strip('"').strip("'")
    return value


def styles():
    st.markdown("""<style>
    .block-container {max-width:1200px;padding-top:2.4rem;padding-bottom:4rem;}
    [data-testid="stSidebar"] {border-right:1px solid rgba(148,163,184,.13);}
    h1 {font-size:2.5rem!important;letter-spacing:-.06rem;font-weight:650!important;}
    h2 {letter-spacing:-.025rem;}
    .eyebrow {color:#A5B4FC;font-size:.75rem;letter-spacing:.16rem;font-weight:650;margin-bottom:.7rem;}
    .lede {color:#9AA8BC;font-size:1.05rem;max-width:700px;line-height:1.7;margin-bottom:1.7rem;}
    .step {border-top:2px solid #334155;padding:1rem 0;color:#9AA8BC;font-size:.9rem;}
    .step strong {color:#E6EAF2;display:block;margin-bottom:.3rem;font-size:1rem;}
    [data-testid="stMetricValue"] {font-size:1.4rem;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px;}
    .stButton > button, .stDownloadButton > button {border-radius:8px;}
    a {text-underline-offset:3px;}
    [data-testid="stAppDeployButton"] {display:none;}
    </style>""", unsafe_allow_html=True)


@st.cache_resource
def job_manager():
    import threading
    def _warmup():
        try:
            from planner.engine import embedding_model
            embedding_model()
        except Exception:
            pass
    threading.Thread(target=_warmup, daemon=True).start()
    return JobManager()


def require_access():
    code = setting("APP_ACCESS_CODE")
    if code and not st.session_state.get("access_granted"):
        st.title("SEO Content Planner")
        st.write("Enter your workspace access code to continue.")
        with st.form("access"):
            entered = st.text_input("Access code", type="password")
            submitted = st.form_submit_button("Continue", type="primary")
        if submitted:
            if hmac.compare_digest(entered, code):
                st.session_state.access_granted = True
                st.rerun()
            st.error("The access code is incorrect.")
        st.stop()


def active_providers():
    gemini_key = setting("GEMINI_API_KEY")
    groq_key = setting("GROQ_API_KEY")
    cerebras_key = setting("CEREBRAS_API_KEY")
    providers = []
    if gemini_key:
        providers.append({"label": "Google Gemini (gemini-flash-lite)", "id": "gemini", "key": gemini_key})
    if groq_key:
        providers.append({"label": "Groq (gpt-oss-20b) ", "id": "groq", "key": groq_key})
    if cerebras_key:
        providers.append({"label": "Cerebras (gpt-oss-120b)", "id": "cerebras", "key": cerebras_key})
    return providers


def sidebar():
    with st.sidebar:
        st.markdown("### Content workspace")
        st.caption("Research. Plan. Write.")
        st.divider()
        providers = active_providers()
        active_provider_id, active_key = "none", ""
        if len(providers) > 1:
            names = [p["label"] for p in providers]
            choice = st.selectbox("AI Model Provider", names, index=0)
            chosen = next(p for p in providers if p["label"] == choice)
            active_provider_id = chosen["id"]
            active_key = chosen["key"]
        elif len(providers) == 1:
            active_provider_id = providers[0]["id"]
            active_key = providers[0]["key"]
            st.caption(f"Provider: {providers[0]['label']}")
        else:
            st.caption("Add GEMINI_API_KEY or GROQ_API_KEY in .env")
        st.caption("💡 Tip: If a model is busy or not responding, select a different provider. You can also cancel generation anytime.")
        language = st.selectbox("Output language", ["English", "Urdu", "Roman Urdu"], key="language")
        output = st.radio("Create", ["SEO outline", "Complete article"], key="output_choice")
        words = 600
        if output == "Complete article":
            words = st.number_input(
                "Target length",
                min_value=200,
                max_value=3000,
                value=600,
                step=50,
                key="target_length",
                help="Enter any word count      ."
            )
            st.caption(f"Targeting approximately {words} words, including FAQs. Type or use +/-.")
        faq_choice = st.selectbox(
            "FAQ section",
            ["Auto (Recommended)", "None", "2 FAQs", "3 FAQs", "4 FAQs", "5 FAQs"],
            index=0,
            key="faq_choice",
        )
        faq_map = {
            "Auto (Recommended)": 3,
            "None": 0,
            "2 FAQs": 2,
            "3 FAQs": 3,
            "4 FAQs": 4,
            "5 FAQs": 5,
        }
        faqs = faq_map[faq_choice]
        st.caption("Common reader questions answered for search engine visibility. Auto creates 3 relevant FAQs.")
        web = st.toggle("Find web sources", value=True)
        st.caption("Use your references, discover sources online, or generate a clearly labelled unsourced draft.")
        st.divider()
        st.caption("Documents and instructions are processed by this service and its AI provider. Upload only material you are allowed to share.")
        st.caption("AI suggestions need human review. Keyword recommendations do not include measured search-volume or ranking data.")
        return language, "article" if output == "Complete article" else "brief", words, faqs, web, active_provider_id, active_key


def input_panel(options):
    language, output, words, faqs, web, provider, key = options
    busy = st.session_state.get("job") is not None
    mode = st.radio("Input method", ["Write a prompt", "Use detailed fields"], horizontal=True, disabled=busy)
    uploads = []
    with st.expander("Reference material · optional", expanded=False):
        urls = st.text_area("Reference URLs", placeholder="https://example.com/guide\nOne URL per line", disabled=busy)
        files = st.file_uploader("Upload documents", type=["pdf", "txt", "md", "csv", "xlsx", "pptx"],
                                 accept_multiple_files=True, disabled=busy)
        st.caption("Up to 5 files, 10 MB each and 20 MB total. Scanned PDFs need readable text. Files are temporary.")
        for index, file in enumerate(files):
            role = st.selectbox(f"Use {file.name} as", ["Reference material", "Instructions"], key=f"role_{index}", disabled=busy)
            uploads.append({"name": file.name, "data": file.getvalue(),
                            "role": "user_reference" if role == "Reference material" else "user_instructions"})
    # State values initialization
    for k in ("topic_field", "audience_field", "instructions_field", "prompt_field"):
        if k not in st.session_state:
            st.session_state[k] = ""

    def on_field_enter():
        t = st.session_state.get("topic_field", "").strip()
        a = st.session_state.get("audience_field", "").strip()
        i = st.session_state.get("instructions_field", "").strip()
        if t and a and i:
            st.session_state.auto_generate = True

    auto_trigger = st.session_state.pop("auto_generate", False)

    if mode == "Write a prompt":
        prompt = st.text_area(
            "What would you like to create?",
            key="prompt_field",
            height=160,
            max_chars=4000,
            placeholder="Create a practical guide to responsible AI use for university students. Cover reference checking, privacy and university rules.",
            disabled=busy
        )
        st.caption("Describe the topic, audience and any requirements. Your selected output settings take priority.")
        topic = audience = instructions = ""
    else:
        left, right = st.columns(2)
        topic = left.text_area(
            "Topic",
            key="topic_field",
            height=85,
            max_chars=300,
            placeholder="e.g. AI in healthcare",
            disabled=busy,
            on_change=on_field_enter
        )

        audience = right.text_area(
            "Target audience",
            key="audience_field",
            height=85,
            max_chars=500,
            placeholder="e.g. HEalth technology developers and AI reseachers",
            disabled=busy,
            on_change=on_field_enter
        )

        instructions = st.text_area(
            "Additional instructions",
            key="instructions_field",
            height=120,
            max_chars=3000,
            placeholder="e.g. Focus more on the practical applications",
            disabled=busy,
            on_change=on_field_enter
        )
        st.caption("Press Ctrl+Enter (or tab out) on each field to apply. When all fields are filled, generation will start.")
        prompt = ""

    submit = st.button("Generate content", type="primary", disabled=busy, use_container_width=True) or auto_trigger
    if not submit:
        return
    if not key or provider == "none":
        st.error("Content generation is not available yet. The app owner needs to configure GEMINI_API_KEY or GROQ_API_KEY.")
        return
    try:
        if not (prompt.strip() if mode == "Write a prompt" else topic.strip()):
            raise ValueError("Enter a prompt or topic to get started.")
        if len(uploads) > 5 or sum(len(u["data"]) for u in uploads) > 20 * 1024 * 1024:
            raise ValueError("Upload at most five files, totalling 20 MB.")
        for upload in uploads:
            validate_upload(upload["name"], upload["data"])
        source_urls = [u.strip() for u in urls.splitlines() if u.strip()]
        if len(source_urls) > 5:
            raise ValueError("Add at most five reference URLs.")
        if time.monotonic() - st.session_state.get("last_submit", 0) < 5:
            raise ValueError("Please wait a moment before generating another result.")
        payload = {"mode": "prompt" if mode == "Write a prompt" else "fields", "prompt": prompt,
                   "topic": topic, "audience": audience, "instructions": instructions, "language": language,
                   "output_type": output, "target_words": words, "faq_count": faqs,
                   "use_web_search": web, "source_urls": source_urls, "provider": provider}
        st.session_state.job = job_manager().submit(payload, uploads, key)
        st.session_state.last_submit = time.monotonic()
        st.session_state.events = []
        st.session_state.pop("result", None)
        st.session_state.pop("pdf", None)
        st.session_state.pop("job_error", None)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))


@st.fragment(run_every=1)
def progress_panel():
    job = st.session_state.get("job")
    if job is None:
        return
    while True:
        try:
            st.session_state.events.append(job.events.get_nowait())
        except Empty:
            break
    events = st.session_state.events
    label = events[-1][1] if events else "Preparing your content workspace"
    with st.status(label, expanded=True, state="running"):
        st.write("Your request is running. Keep this page open; navigating away does not immediately cancel a provider request.")
        st.caption(f"Elapsed: {int(time.monotonic() - job.started)} seconds")
        for _, message in events[-4:]:
            st.write(message)
        if st.button("Cancel generation", key="cancel_job", disabled=job.cancel.is_set()):
            job.cancel.set()
            st.session_state.job = None
            st.session_state.events = []
            st.session_state.job_error = "Generation was cancelled. You can select another provider and try again."
            st.rerun()
    if job.future.done():
        try:
            st.session_state.result = job.future.result()
        except Exception as exc:
            if type(exc).__name__ == "ProviderFailure" or isinstance(exc, ValueError):
                st.session_state.job_error = str(exc)
            else:
                st.session_state.job_error = "We could not complete this request. Please try again or contact the app owner."
        st.session_state.job = None
        st.rerun()


def show_results(result):
    st.divider()
    if result.get("is_sample"):
        c_info, c_action = st.columns([4, 1.2])
        c_info.info("Example preview — no API request, live search or evidence review was performed.")
        if c_action.button("Close example", use_container_width=True):
            st.session_state.pop("result", None)
            st.session_state.pop("pdf", None)
            st.rerun()
    else:
        label = STATUS_LABELS[result["status"]]
        c_info, c_action = st.columns([4, 1.2])
        with c_info:
            if result["status"] == "automated_review_passed":
                st.success(label + ". Check the content before publishing.")
            else:
                st.warning(label + ". Read the Sources & review tab before using this draft.")
        with c_action:
            if st.button("Back to editor", use_container_width=True):
                st.session_state.pop("result", None)
                st.session_state.pop("pdf", None)
                st.rerun()
    request = result["request"]
    st.caption(f"{request['topic']} · {request['audience']} · {request['output_language']}")
    cols = st.columns(3)
    cols[0].metric("Output", "Article" if result.get("article") else "SEO outline")
    cols[1].metric("Sources retrieved", len(result["sources"]))
    cols[2].metric("Words" if result.get("article") else "Outline sections",
                   result["word_count"] if result.get("article") else len(result["brief"]["outline"]))
    content, seo, sources = st.tabs(["Your content", "SEO & audience", "Sources & review"])
    with content:
        if request["output_language"] == "Urdu":
            st.markdown('<style>[data-testid="stTabs"] [data-testid="stMarkdownContainer"] p {unicode-bidi:plaintext;}</style>', unsafe_allow_html=True)
        st.markdown(content_markdown(result))
    with seo:
        report = result.get("article") or result["brief"]
        st.subheader("Search preview")
        st.markdown("**" + safe_markdown(report["title"]) + "**")
        st.write(report["meta_description"])
        st.caption("An editorial preview, not a live search-engine result.")
        st.subheader("Keyword strategy")
        st.write("Primary keyword: " + result["seo"]["primary_keyword"])
        st.write("Secondary: " + ", ".join(result["seo"]["secondary_keywords"]))
        st.write("Long-tail: " + ", ".join(result["seo"]["long_tail_keywords"]))
        st.write("Search intent: " + result["seo"]["search_intent"])
        st.write(result["seo"]["intent_reason"])
        st.subheader("Audience")
        st.write(result["audience"]["audience_description"])
        for need in result["audience"]["reader_needs"]:
            st.write("- " + need)
        with st.expander("Audience assumptions"):
            for assumption in result["audience"]["assumptions"]:
                st.write(assumption)
    with sources:
        st.caption("Automated review checks supplied evidence. It does not independently verify the sources or guarantee accuracy.")
        for sid, source in result["sources"].items():
            with st.expander(f"{sid} · {source['title']}"):
                if source.get("url"):
                    st.link_button("Open source", source["url"])
                else:
                    st.caption("Uploaded reference document")
                for item in result["evidence"]:
                    if item["source_id"] == sid:
                        st.caption(item["chunk_id"] + " · " + item["location"])
                        st.text(item["text"])
        if not result["sources"]:
            st.info("No external sources were retrieved. Treat this as an unsourced draft.")
        for target, review in result["review"].items():
            with st.expander(target.capitalize() + " review", expanded=bool(review["issues"])):
                for issue in review["issues"]:
                    st.warning(issue["required_change"])
                st.dataframe([{ "Location": a["location"], "Assessment": a["verdict"],
                                "Explanation": a["explanation"]} for a in review["assessments"]],
                               hide_index=True, use_container_width=True)
        st.subheader("Limitations")
        for note in dict.fromkeys(result["notices"] + result["brief"]["limitations"]):
            st.write("- " + note)
    st.subheader("Take your work with you")
    one, two, three = st.columns(3)
    if "pdf" not in st.session_state:
        if one.button("Prepare PDF", use_container_width=True):
            try:
                st.session_state.pdf = make_pdf(result)
                st.rerun()
            except Exception:
                st.error("PDF export is temporarily unavailable. You can still download Markdown.")
    else:
        one.download_button("Download PDF", st.session_state.pdf, "seo-content.pdf", "application/pdf", use_container_width=True)
    two.download_button("Download Markdown", download_markdown(result), "seo-content.md", "text/markdown", use_container_width=True)
    three.download_button("Download JSON", json.dumps(result, ensure_ascii=False, indent=2), "seo-content.json", "application/json", use_container_width=True)


styles()
require_access()
job_manager()
options = sidebar()
st.markdown('<div class="eyebrow">AI-POWERED SEO CONTENT PLANNER</div>', unsafe_allow_html=True)
st.title("A clear plan. Content with purpose.")
st.markdown('<div class="lede">Turn a topic, a brief or your reference material into a structured SEO outline or a complete article.</div>', unsafe_allow_html=True)
input_panel(options)
if st.session_state.get("job"):
    progress_panel()
if st.session_state.get("job_error"):
    st.error(st.session_state.job_error)
if st.session_state.get("result"):
    show_results(st.session_state.result)
elif not st.session_state.get("job"):
    st.write("")
    for column, number, title, detail in zip(st.columns(3), ["01", "02", "03"],
            ["Start with your idea", "Give it direction", "Make it yours"],
            ["Write naturally or use the detailed form.", "Add an audience, references and requirements.", "Review the result and export your content."]):
        column.markdown(f'<div class="step">{number}<strong>{title}</strong>{detail}</div>', unsafe_allow_html=True)
    if st.button("View an example"):
        st.session_state.result = sample_result()
        st.session_state.pop("pdf", None)
        st.rerun()
