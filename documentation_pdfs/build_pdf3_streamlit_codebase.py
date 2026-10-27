import sys
from pathlib import Path

# Add current folder to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_styler import AcademicPDF

APP_DIR = Path(__file__).resolve().parents[1] / "streamlit_app"

FILES_TO_EXPLAIN = [
    ("app.py", "Streamlit Frontend User Interface & Job Manager",
     "app.py pure application ka web user interface (UI) control karta hai. Iska kaam user se input lena, "
     "AI Model Provider (Gemini, Groq, Cerebras) select karwana, asynchronous background thread mein generation start karna, "
     "real-time progress updates dikhana, aur aane wale result ko Markdown, JSON, aur PDF mein export karwana hai.\n\n"
     "Key Functions & Logic:\n"
     "- `setting(name)`: Secrets lookup karta hai pehle `os.getenv` se phir `st.secrets` se taake Streamlit Cloud par credentials seamlessly milen.\n"
     "- `active_providers()`: Check karta hai ke konsi API keys (.env ya secrets mein) mojood hain aur unhi models ko dropdown mein show karta hai.\n"
     "- `job_manager()`: Background threading mechanism (`threading.Thread`) use karta hai taake LLM calls ke doran Streamlit UI freeze na ho.\n"
     "- `options = sidebar()`: Topic, audience, target words, language (English/Urdu/Roman Urdu), aur output choice (Outline ya Complete Article) ke widgets render karta hai.\n"
     "- `show_results(result)`: Outline, FAQ, SEO metadata, Audit issues, aur Download buttons (PDF, Markdown, JSON) display karta hai."),

    ("planner/contracts.py", "Pydantic v2 Data Models & Validation Contracts",
     "contracts.py pure project ki data integrity ka zamin hai. Is file mein har stage ke inputs aur outputs ke strict "
     "Pydantic v2 data models define kiye gaye hain. LLMs structured output return karte hain jo inhi models ke mutabiq validate hoti hai.\n\n"
     "Key Classes & Logic:\n"
     "- `StrictModel`: Base model jismein `extra='forbid'` laga hai taake LLM apni taraf se koi extra field invent na kar sake.\n"
     "- `Intake`: User request ka schema (topic, audience, instructions, target_words, output_language).\n"
     "- `Article`: Complete article ka schema (title, meta_description, introduction, sections, faqs, output_language).\n"
     "- `Section`: Article ke har section ka schema (heading, body, chunk_ids).\n"
     "- `FAQ`: Question, answer, aur associated chunk_ids.\n"
     "- `count_words(text)`: Multilingual word counting function jo spaces ke mutabiq words count karta hai.\n"
     "- `article_text(article)`: Article ke tamam hisson (intro, sections, faqs) ko ek string mein jodta hai taake word count aur audit check ho sake."),

    ("planner/engine.py", "Master Pipeline Coordinator & Resilient Embeddings",
     "engine.py pipeline ka central brain hai jo tamam stages ko coordinate karta hai. Is file mein resilient zero-download "
     "embeddings, concurrency (`asyncio.gather`), Urdu script validation, aur exact word count trimming implement kiye gaye hain.\n\n"
     "Key Components & Logic:\n"
     "- `FallbackTokenizer` & `FallbackEmbeddingModel`: Streamlit Cloud par jab Hugging Face offline ho ya block ho, "
     "to yeh model deterministic MD5 n-gram hashing ke zariye 0 MB RAM aur 0.001 second mein unit-norm embedding vectors banata hai.\n"
     "- `write_article`: Writer stage ko execute karta hai. Iske andar `validate_and_heal` function sentence boundary splitter `[.!?۔؟]` "
     "aur word-level trimming ke zariye target words (e.g. 450 words) ko strictly enforce karta hai.\n"
     "- `generate(payload, ...)`: Master async function jo Ingestion, Web Search, Dense Retrieval, Audience, SEO, Outline, "
     "Writer, aur Review ko sequentially aur parallelly run karta hai.\n"
     "- Concurrency optimization: `unified_review_reports` aur `write_article` ko `asyncio.gather` se parallel chalata hai jis se 15-20 seconds ki bachat hoti hai."),

    ("planner/transport.py", "LLM Transport, CrewAI Integration & Rate Limiter",
     "transport.py external AI model providers (Groq, Cerebras, Google Gemini) ke sath actual network communication ko handle karta hai. "
     "Is file mein rate limiting, token budgeting, self-healing JSON repair, aur CrewAI execution engine mojood hai.\n\n"
     "Key Components & Logic:\n"
     "- `safe_parse_json`: Agar model ka return kiya hua JSON markdown backticks mein ho ya syntax thora sa toot gaya ho (missing brackets), "
     "to yeh stack algorithm se brackets balance karke cleanly parse karta hai.\n"
     "- `retry_policy`: HTTP 429 (Rate Limit) ya 500/503 errors par exponential backoff karta hai aur 'retry-after' header ko respect karta hai.\n"
     "- `JSONTransport(BaseLLM)`: CrewAI ka custom LLM class jo enforce karta hai `response_format={'type': 'json_object'}`.\n"
     "- `STAGE_TOKENS`: Har stage ke liye optimized completion token limits (Intake: 400, SEO: 600, Research: 800, Structure: 1200, Writer: 1800) "
     "taake Groq 6,000 TPM limit cross na ho aur Cerebras par latency kam ho."),

    ("planner/notebook_stages.py", "Agent Prompts & Domain-Agnostic Stage Runners",
     "notebook_stages.py har agent stage ke tailored system prompts, rules, aur execution wrappers define karta hai. "
     "Yeh file notebook ke stages ka production-isolated version hai.\n\n"
     "Key Functions & Logic:\n"
     "- `select_sources`: Source selection agent ka prompt jo trustworthy domains ko filter karta hai.\n"
     "- `encode_chunks`: Chunks ke dense vectors banata hai.\n"
     "- `retrieve_evidence`: Domain-agnostic query vector aur passage vectors ka dot product (cosine similarity) nikalta hai aur Top-5 evidence choose karta hai.\n"
     "- `run_research`: Factual researcher jo chunk IDs ke sath findings extract karta hai.\n"
     "- `run_audience`: Reader needs aur foundational assumptions banata hai.\n"
     "- `run_seo`: Primary, secondary, long-tail keywords aur search intent formulate karta hai.\n"
     "- `run_structure`: H2/H3 outline banata hai with authentic Urdu script mandate (`اردو رسم الخط`)."),

    ("planner/ingestion.py", "Multi-Format Parsing, DuckDuckGo Search & Scraping",
     "ingestion.py raw data ko clean, token-bounded factual passages mein convert karta hai. "
     "Is file mein multi-format file readers aur web discovery tools shamil hain.\n\n"
     "Key Functions & Logic:\n"
     "- `read_document(file_path)`: PDF (pypdf), Excel (openpyxl), PowerPoint (python-pptx), aur Text/Markdown files ko parse karta hai (max 60,000 chars).\n"
     "- `fetch_source(url)`: Requests aur BeautifulSoup se live webpage download karta hai aur navbars/footers/scripts nikal kar clean article text banata hai.\n"
     "- `discover_sources(request)`: DuckDuckGo Search API se live web queries run karke top reference URLs dhoondta hai.\n"
     "- `chunk_sources(sources, model)`: Text ko 240-word sliding window chunks mein kaat kar unique Chunk IDs (`SRC1-C1`, `SRC1-C2`) assign karta hai."),

    ("planner/review.py", "Quality Audit, Claim Extraction & Hallucination Check",
     "review.py pure system ka quality control inspector hai. Iska kaam writer aur planning stages ke claims ko "
     "evidence ke samnay rakh kar check karna hai.\n\n"
     "Key Functions & Logic:\n"
     "- `units_for(target, report)`: Draft ke har jumlay ya section ko verifiable atomic units mein divide karta hai.\n"
     "- `evidence_catalog(evidence)`: Tamam retrieved chunks ka lookup index banata hai.\n"
     "- `review_report`: LLM Auditor ko har claim aur evidence chunks deta hai. Model classify karta hai ke claim 'supported' hai ya 'unsupported'.\n"
     "- `unified_review_reports`: Research, SEO, aur Outline ko ek single combined pass mein audit karta hai taake extra API calls aur time bach sake."),

    ("planner/exports.py", "Publishing Engine: Markdown & Typeset Vector PDF",
     "exports.py final generated output ko user ke download karne ke liye format karta hai. Is file mein Markdown generation "
     "aur FPDF2 vector PDF creation with Urdu HarfBuzz font shaping implement ki gayi hai.\n\n"
     "Key Functions & Logic:\n"
     "- `content_markdown(result)`: Title, Intro, Sections, aur FAQs ko clean Github Flavored Markdown mein convert karta hai.\n"
     "- `download_markdown(result)`: Content ke sath SEO metadata, Review limitations, aur Reference URLs append karta hai.\n"
     "- `make_pdf(result)`: FPDF2 document create karta hai, Noto Sans aur Noto Naskh Arabic fonts load karta hai, "
     "`pdf.set_text_shaping(True)` se authentic Urdu nastaliq/naskh ligatures jorta hai, aur running header/footer ke sath styled PDF byte stream return karta hai."),

    ("planner/security.py", "Cybersecurity Guardrails & SSRF Prevention",
     "security.py system ki application-level security enforce karta hai. Iska kaam prompt injection, "
     "Server-Side Request Forgery (SSRF), aur API key leakage ko rokna hai.\n\n"
     "Key Functions & Logic:\n"
     "- `clean_url(url)` & `public_url(url)`: Validate karta hai ke URLs valid web links hon aur private LAN IPs (127.0.0.1, 10.x.x.x, 192.168.x.x) "
     "ko block karta hai taake koi attacker local server access na kar sake.\n"
     "- `validate_upload(name, data)`: File extensions (.pdf, .xlsx, .pptx, .txt) aur unke magic bytes verify karta hai taake executable malware upload na ho sake.\n"
     "- `redact(text, key)`: Logs aur error messages mein se Groq, Gemini, ya Cerebras ki secret API keys ko mask (`***`) karta hai taake credentials leak na hon."),

    ("planner/sample.py", "Zero-Cost Demo Data Loader",
     "sample.py demonstration aur fast testing ke liye banaya gaya hai. "
     "Jab kisi user ke paas API key na ho ya developer ko UI test karni ho, to yeh pre-calculated sample package return karta hai.\n\n"
     "Key Logic:\n"
     "- `sample_result()`: Aik realistic Machine Learning SEO plan return karta hai jismein Outline, Audience, SEO Keywords, "
     "Review Status, aur References pehle se structured hotay hain. Is par click karne se 0 API calls lagti hain aur 0.1 second mein dashboard populate ho jata hai.")
]


def build_pdf():
    pdf = AcademicPDF(
        doc_title="Part 3: Streamlit Application Codebase & Architecture",
        subtitle="Complete Code & Line-by-Line Roman Urdu Guide for Every File"
    )

    # Cover Page
    pdf.add_cover(
        title="Streamlit Web Application Codebase\nComplete Architecture & File Walkthrough",
        subtitle="Deep Dive into All Python Files in project/streamlit_app\n8th Semester Natural Language Processing (NLP)",
        author="Uzair (NLP Student)",
        project_meta=[
            ("Course", "Natural Language Processing (NLP) - 8th Semester CS"),
            ("Application Directory", "project/streamlit_app/"),
            ("Files Covered", "app.py, contracts.py, engine.py, transport.py, ingestion.py, etc."),
            ("Coverage", "Role of file, Architectural responsibility, Code structure & Line-by-Line Roman Urdu Breakdown"),
            ("Document Scope", "Part 3: Production Codebase Technical Report & Viva Defense")
        ]
    )

    pdf.section_h1("Codebase Architecture Overview")
    pdf.body_p(
        "Streamlit application ka codebase modular clean-architecture design follow karta hai. "
        "Presentation layer (`app.py`), Data contracts (`contracts.py`), Pipeline engine (`engine.py`), "
        "LLM Transport (`transport.py`), Data ingestion (`ingestion.py`), Quality Audit (`review.py`), "
        "Publishing exports (`exports.py`), aur Security guardrails (`security.py`) bilkul decoupled hain. "
        "Neechay har file ka mukammal role, key code patterns, aur Roman Urdu mein tafseeli wazahat pesh ki gayi hai."
    )
    pdf.ln(3)

    for fname, title, explanation in FILES_TO_EXPLAIN:
        fpath = APP_DIR / fname
        pdf.section_h1(f"File: {fname}")
        pdf.section_h2(f"Module Role: {title}")
        
        # Read file code snippet
        code_content = ""
        if fpath.exists():
            code_content = fpath.read_text(encoding="utf-8", errors="replace")
        
        pdf.callout(f"Architectural Role & Work of {fname}", explanation, type="info")
        pdf.ln(1)
        
        pdf.section_h3(f"Representative Code Listing ({fname}):")
        if code_content:
            pdf.code_box(code_content, max_lines=42)
        else:
            pdf.body_p(f"File located at: {fpath}")
        pdf.ln(3)

    out_path = Path("project/documentation_pdfs/03_Streamlit_App_Code_And_Architecture.pdf")
    pdf.output(str(out_path))
    print(f"Successfully generated PDF 3 at {out_path} ({pdf.page_no()} pages)")

if __name__ == "__main__":
    build_pdf()
