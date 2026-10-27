import json
import sys
from pathlib import Path

# Add current folder to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_styler import AcademicPDF

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebook" / "seo-planner.ipynb"

# Rich Roman Urdu explanations mapped to cell index or stage
CELL_EXPLANATIONS = {
    0: ("Title & Project Header", 
        "Yeh markdown cell notebook ka main academic title aur project overview define karta hai. "
        "Is mein bataya gaya hai ke yeh project multi-agent architecture par mubni hai jismein CrewAI aur Groq/Gemini models "
        "SEO content planning aur fact-grounded writing ke liye use hotay hain."),
    
    1: ("Section 1: Package Installation Header",
        "Yeh markdown header Environment Setup aur zaroori Python dependencies ki installation ko introduce karta hai."),
    
    2: ("Package Installation Command (%pip install)",
        "Code Explanation: Yeh cell notebook ke liye zaroori libraries install karta hai:\n"
        "- crewai: Multi-agent orchestration ke liye framework.\n"
        "- pydantic: Data validation aur structured schemas ke liye.\n"
        "- sentence-transformers: Hugging Face ke multilingual embeddings ke liye.\n"
        "- duckduckgo-search: Live internet search se authentic references nikalne ke liye.\n"
        "- beautifulsoup4: Web pages scrape karke boilerplate clean karne ke liye.\n"
        "- pypdf, openpyxl, python-pptx: PDF, Excel aur PowerPoint files parse karne ke liye.\n"
        "Roman Urdu Logic: %pip install se notebook virtual environment mein tamam packages bina system clash ke install ho jatay hain."),
    
    3: ("Section 1.1: Imports & Diagnostics Header",
        "Yeh markdown cell imports aur diagnostic setup ko describe karta hai."),
    
    4: ("Library Imports & Environment Setup",
        "Code Explanation:\n"
        "- asyncio: Python ka asynchronous execution module jo agents ko non-blocking banata hai.\n"
        "- pydantic (BaseModel, Field, ConfigDict): Data validation ke contracts banata hai.\n"
        "- os.environ settings: CrewAI telemetry aur tokenizer parallelism ko disable karta hai taake background crashes na hon.\n"
        "Roman Urdu Logic: Tamam required modules ko memory mein load kiya jata hai aur telemetry disable karke execution speed barhai jati hai."),
    
    5: ("Section 2: Model Configuration Header",
        "Yeh markdown cell model settings aur API parameters ko introduce karta hai."),
    
    6: ("Model Selection & Safety Parameters",
        "Code Explanation:\n"
        "- MODEL_ID = 'groq/openai/gpt-oss-20b': Default LLM provider Groq par model set karta hai.\n"
        "- SETTINGS dictionary: target_sources=2 (kam az kam 2 authentic sources), max_fetches=3 (maximum 3 URLs scrape hon), "
        "top_k=5 (top 5 evidence chunks select hon), max_instruction_chars=6000 (prompt injection se bachne ke liye char limit).\n"
        "Roman Urdu Logic: Yeh project ke hyper-parameters hain jo web search aur token consumption ko control mein rakhte hain."),

    7: ("Section 3: Type Contracts Header",
        "Yeh cell shared Pydantic data schemas ko introduce karta hai."),

    8: ("StrictModel Base Contract",
        "Code Explanation:\n"
        "- class StrictModel(BaseModel): model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)\n"
        "Roman Urdu Logic: NLP mein LLMs aksar extra fields invent kar dete hain (schema hallucination). 'extra=forbid' "
        "enforce karta hai ke agar model koi aisi field return kare jo schema mein nahi hai, to Pydantic foran reject kare. "
        "'str_strip_whitespace=True' strings ke aage peechay ke faltu spaces saaf karta hai."),

    9: ("Section 3.1: Persistence Utilities Header",
        "JSON file handling aur persistence utilities ka markdown cell."),

    10: ("save_json & load_json Utilities",
        "Code Explanation:\n"
        "- save_json(path, value): Pydantic models ya dictionaries ko utf-8 format mein JSON file mein save karta hai.\n"
        "Roman Urdu Logic: Multi-agent execution ke doran har agent ki output (Audience, SEO, Brief, Review) folder mein "
        "as a checkpoint save hoti hai taake session crash hone par dobara shuru se na chalana paray."),

    11: ("Section 3.2: Verbatim Evidence Quote Validation Header",
        "Factual grounding aur citation validation ka header cell."),

    12: ("validate_quotes & Substring Grounding",
        "Code Explanation:\n"
        "- chunks = {e['chunk_id']: e['text']}: Retrieved evidence chunks ka lookup map.\n"
        "- for quote in quotes: if quote.quote not in chunks[quote.chunk_id]: raise ValueError(...)\n"
        "Roman Urdu Logic: Yeh NLP ka critical hallucination check hai! Agar koi agent claim karta hai ke 'main ne yeh baat "
        "source chunk-1 se li hai', to yeh function verify karta hai ke kya wo exact jumla waqayi us chunk ke andar mojood hai ya agent ne apne paas se ghalat quote banayi hai."),

    13: ("Section 4: Structural JSON Sanitization Header",
        "Raw LLM response repair utilities ka header."),

    14: ("repair_missing_delimiters & Text Sanitizer",
        "Code Explanation:\n"
        "- LLMs jab JSON generate karte hain to kabhi kabhi quotes `\"` band karna bhool jatay hain ya trailing commas chhor dete hain.\n"
        "- Yeh function stack algorithm use karta hai jo open brackets `{[` ko trace karta hai aur missing closing brackets `]}` "
        "auto-append karke JSON ko syntactically valid banata hai.\n"
        "Roman Urdu Logic: Is function ki wajah se agar model ka JSON thora sa toot bhi jaye to pipeline crash nahi hoti balke self-heal ho jati hai."),

    15: ("Section 4.1: Resilient Response Deserialization Header",
        "Robust JSON parser ka header."),

    16: ("safe_parse_json & Schema Normalization",
        "Code Explanation:\n"
        "- safe_parse_json(raw_text, schema): Markdown code fences (```json ... ```) ko strip karta hai, regex se clean karta hai, "
        "aur `schema.model_validate_json()` se Pydantic object banata hai.\n"
        "Roman Urdu Logic: Model chahe plain text mein JSON wrap kare ya markdown backticks mein, yeh function cleanly extract kar leta hai."),

    17: ("Section 4.1: Shared Agent Engine Header",
        "CrewAI custom agent runner ka header."),

    18: ("run_agent Execution Engine (Core NLP Runner)",
        "Code Explanation:\n"
        "- async def run_agent(name, role, rules, schema, context, folder, validate=None):\n"
        "- JSONTransport: LLM call karta hai response_format={'type': 'json_object'} ke sath.\n"
        "- Agent & Crew setup: CrewAI Agent banata hai jismein rules, context, aur expected schema pass hotay hain.\n"
        "- Retry loop (attempts 1 to 4): Agar model output schema violate kare to feedback string ke sath retry karta hai.\n"
        "Roman Urdu Logic: Yeh pure project ka core runner hai! Har agent (SEO, Research, Writer) isi function ke zariye "
        "chalta hai aur self-correction mechanism provide karta hai."),

    19: ("Section 5: Request Preparation Header",
        "User input validation aur sanitization ka header."),

    20: ("clean_url & prepare_request (SSRF Protection)",
        "Code Explanation:\n"
        "- clean_url(url): Validate karta hai ke URL 'http://' ya 'https://' se shuru ho, private IP addresses (localhost, 127.0.0.1, 192.168.x) "
        "ko block karta hai (Server-Side Request Forgery - SSRF prevention).\n"
        "- prepare_request: User ke topic, instructions, language, target word count ko validate karta hai.\n"
        "Roman Urdu Logic: User security layer: taake koi malicious user server ki internal files ya local network ko hack na kar sake."),

    21: ("Section 5.1: Document Ingestion Header",
        "Local files parsing ka header cell."),

    22: ("read_document Multi-Format Parser",
        "Code Explanation:\n"
        "- Text/Markdown: read_text(encoding='utf-8-sig').\n"
        "- PDF: pypdf.PdfReader se pages extract karta hai (max 80 pages).\n"
        "- Excel: openpyxl se rows aur columns ko table format mein string banata hai.\n"
        "- PPTX: pptx.Presentation se slide shapes ke text frames read karta hai.\n"
        "Roman Urdu Logic: User chahe research ke liye PDF upload kare ya Excel sheet ya slides, yeh function unhein clean textual chunks mein convert karta hai."),

    23: ("Section 5.2: User Documents Packaging Header",
        "Documents budget verification ka header."),

    24: ("load_user_documents Budget Enforcement",
        "Code Explanation:\n"
        "- User ke uploaded files ka total text 60,000 characters se exceed nahi hona chahiye taake context window overflow na ho.\n"
        "Roman Urdu Logic: Token overflow prevention taake model slow na ho aur API error na de."),

    25: ("Section 5.3: Web Candidate Discovery Header",
        "DuckDuckGo search agent ka header."),

    26: ("discover_sources (DuckDuckGo Live Search)",
        "Code Explanation:\n"
        "- DDGS().text(request['topic'], max_results=5): Live internet search karta hai.\n"
        "- Resultant URLs aur snippets ko candidate list mein pack karta hai.\n"
        "Roman Urdu Logic: Topic ke mutabiq internet se taza tareen maloomat aur references dhoondta hai."),

    27: ("Section 5.4: Web Page Retrieval Header",
        "Web scraper aur HTML sanitizer ka header."),

    28: ("fetch_source (BeautifulSoup Scraper)",
        "Code Explanation:\n"
        "- requests.get(url, timeout=5): Webpage download karta hai.\n"
        "- BeautifulSoup: HTML parser. Script, style, nav, footer, ads ko remove karta hai aur sirf main article body ka text extract karta hai (max 15,000 chars).\n"
        "Roman Urdu Logic: Faltu advertisements aur navigation links ko nikal kar sirf kaam ka authentic content hasil karta hai."),

    29: ("Section 5.5: Source Selection Agent Header",
        "Source filtering agent ka header."),

    30: ("SourcePlan Schema & select_sources Agent",
        "Code Explanation:\n"
        "- class SourcePlan(StrictModel): candidate_ids: list[str], rationale: str\n"
        "- Agent LLM ko candidate URLs deta hai aur kehta hai ke sirf authoritative, relevant sources ko select kare.\n"
        "Roman Urdu Logic: Fake ya low-quality websites ko filter out karna taake content trustworthy ho."),

    31: ("Section 5.6: Deterministic Source Collector Header",
        "Sources deduplication ka header."),

    32: ("collect_sources Deduplication & ThreadPool",
        "Code Explanation:\n"
        "- ThreadPoolExecutor: 4 threads mein parallel web scraping karta hai taake wait time kam ho.\n"
        "- SHA-256 fingerprint: Duplicate pages ko detect karke discard karta hai.\n"
        "Roman Urdu Logic: Multi-threading se sources 3 guna taizi se fetch hoti hain."),

    33: ("Section 6: Embedding Model & Chunking Header",
        "Dense vector embeddings aur text splitting ka header."),

    34: ("get_embedding_model & Chunking Engine",
        "Code Explanation:\n"
        "- Multilingual E5 Small (`intfloat/multilingual-e5-small`) load karta hai.\n"
        "- chunk_sources: Scraped text ko 240 words ke sliding window chunks mein divide karta hai (12-word overlap ke sath).\n"
        "Roman Urdu Logic: Baray articles ko chotay passages mein katna taake dense search accurate ho sake."),

    35: ("Section 6.1: Dense Vector Encoding Header",
        "Vector space similarity search ka header."),

    36: ("encode_chunks & retrieve_evidence (Cosine Similarity)",
        "Code Explanation:\n"
        "- encode_chunks: chunks ko 384-dimensional dense vectors mein convert karta hai.\n"
        "- retrieve_evidence: Query vector aur passage vectors ka dot product (cosine similarity) calculate karta hai (`embeddings @ vector`).\n"
        "- Top 5 highest similarity score wale passages ko as evidence select karta hai.\n"
        "Roman Urdu Logic: Classic NLP Dense Retrieval (RAG)! User ke topic se sab se zyada match hone wale passages filter hotay hain."),

    37: ("Section 6.2: Research Context Packaging Header",
        "Evidence packaging ka header."),

    38: ("build_research_context & Limitations Assessor",
        "Code Explanation:\n"
        "- Selected evidence chunks, source URLs, aur limitations (e.g. 'Evidence from only 1 source') ko organize karta hai.\n"
        "Roman Urdu Logic: Transparency aur honest AI generation: model ko pata ho ke evidence ki limit kya hai."),

    39: ("Section 7: Topic Research Agent Header",
        "Fact researcher agent ka header."),

    40: ("ResearchFinding Schema & run_research Agent",
        "Code Explanation:\n"
        "- class ResearchFinding(StrictModel): finding, source_id, verbatim_quote, confidence\n"
        "- Agent extracted evidence chunks par research karta hai aur strictly factual points banata hai.\n"
        "Roman Urdu Logic: Hallucination-free research: baghair evidence ke koi fact allow nahi hota."),

    41: ("Section 8: Audience Analysis Agent Header",
        "Target reader empathy agent ka header."),

    42: ("AudienceReport Schema & run_audience Agent",
        "Code Explanation:\n"
        "- class AudienceReport(StrictModel): audience_description, reader_needs, assumptions\n"
        "- Agent reader persona formulate karta hai (unka knowledge level, unke sawalat, unki zaroorat).\n"
        "Roman Urdu Logic: Content reader-centric banta hai na ke generic AI bot jaisa."),

    43: ("Section 9: SEO & Keyword Strategy Agent Header",
        "Search engine optimization agent ka header."),

    44: ("SEOReport Schema & run_seo Agent",
        "Code Explanation:\n"
        "- class SEOReport(StrictModel): primary_keyword, secondary_keywords, long_tail_keywords, search_intent\n"
        "- Agent Google Search guidelines ke mutabiq keywords aur search intent formulate karta hai.\n"
        "Roman Urdu Logic: Organic reach aur rank hone ke liye zaroori SEO metadata taiyar karta hai."),

    45: ("Section 10: Content Structure Agent Header",
        "Article outline agent ka header."),

    46: ("OutlineSection & BriefReport Schemas",
        "Code Explanation:\n"
        "- class OutlineSection: h2, h3, coverage_notes, chunk_ids\n"
        "- class BriefReport: title, meta_description, outline, faqs, suggested_keywords\n"
        "Roman Urdu Logic: Pure article ka blue-print / structure taiyar karta hai."),

    47: ("Section 10.1: Outline Execution Header",
        "Structure agent runner ka header."),

    48: ("run_structure Execution Agent",
        "Code Explanation:\n"
        "- Research, Audience aur SEO reports ko combine karke logical flow wala complete outline banata hai.\n"
        "Roman Urdu Logic: Title, headings aur FAQs ko ek structured table of contents mein dhalta hai."),

    49: ("Section 10.1: Content Writer Agent Header",
        "Full article generation agent ka header."),

    50: ("ArticleReport Schema & write_article Engine",
        "Code Explanation:\n"
        "- class ArticleReport: title, meta_description, introduction, sections, faqs, output_language\n"
        "- Language Script Mandate: Authentic Urdu script (اردو رسم الخط) ya English enforce karta hai.\n"
        "- validate_and_heal: Sentence boundary trimmer `[.!?۔؟]` se target word count (e.g. 450 words) enforce karta hai.\n"
        "Roman Urdu Logic: Pura article likhta hai aur exact word limit aur zubaan ki pabandi karta hai."),

    51: ("Section 11: Reviewer Schemas Header",
        "Auditor data models ka header."),

    52: ("Reviewer Assessment Contracts",
        "Code Explanation:\n"
        "- class ReviewAssessmentSelection: status ('supported', 'unsupported'), reason, evidence_ids\n"
        "Roman Urdu Logic: Peer-review system jo draft ke har claim ko verify karta hai."),

    53: ("Section 11.1: Guardrails & Entailment Header",
        "Language & roman urdu checker ka header."),

    54: ("is_roman_urdu & Entailment Guardrails",
        "Code Explanation:\n"
        "- Regex check karta hai ke kya content Roman Urdu mein to nahi likha gaya jab ke authentic Urdu select thi.\n"
        "Roman Urdu Logic: Script mismatch catch karne ka automated tool."),

    55: ("Section 11.2: Evidence Catalog Header",
        "Evidence indexing ka header."),

    56: ("review_evidence_catalog Indexer",
        "Code Explanation:\n"
        "- Har chunk ko uniquely index karta hai taake reviewer foran cite kar sake.\n"
        "Roman Urdu Logic: Reference tracking lookup table."),

    57: ("Section 11.3: Review Validator Header",
        "Citation verification ka header."),

    58: ("resolve_review_evidence & Citation Resolution",
        "Code Explanation:\n"
        "- Reviewer ne jo citation IDs mention kiye hain unko actual source URL aur passage ke sath link karta hai.\n"
        "Roman Urdu Logic: Cross-referencing engine."),

    59: ("Section 11.4: Review Target Agent Header",
        "Scoped review execution ka header."),

    60: ("review_target Execution Function",
        "Code Explanation:\n"
        "- Research findings, SEO recommendations, outline aur article ko independently review karta hai aur issues list banata hai.\n"
        "Roman Urdu Logic: Har stage ka independent audit."),

    61: ("Section 12: Markdown Brief Formatting Header",
        "Output formatter ka header."),

    62: ("format_evidence_map & safe_markdown",
        "Code Explanation:\n"
        "- Tamam results ko clean Github-flavored Markdown mein render karta hai.\n"
        "Roman Urdu Logic: User ko parhne ke liye khoobsurat document banana."),

    63: ("Section 12.1: Pipeline Status Header",
        "Status assignment ka header."),

    64: ("has_issues & Pipeline Final Status",
        "Code Explanation:\n"
        "- Checks: 'automated_review_passed' (koi issue nahi mila), 'review_issues_found' (chhoti correction zaroori hai), 'blocked' (critical failure).\n"
        "Roman Urdu Logic: Production grade quality gate."),

    65: ("Section 12.2: Replay Engine Header",
        "Deterministic evaluation ka header."),

    66: ("prepare_evidence_replay (Reproducibility)",
        "Code Explanation:\n"
        "- Purane saved run ke evidence aur web sources ko freeze karke naye models ko compare karne ke liye use karta hai.\n"
        "Roman Urdu Logic: Apples-to-apples research comparison: bina dubara web search kiye same evidence par mukhtalif models test karna."),

    67: ("Section 12.3: Pipeline Orchestration - Ingestion Phase",
        "Master pipeline ka pehla hissa: Ingestion aur retrieval."),

    68: ("pipeline_collect_sources Execution",
        "Code Explanation:\n"
        "- Request parse karta hai, documents read karta hai, search karta hai, chunk karta hai, aur evidence retrieve karta hai.\n"
        "Roman Urdu Logic: Pipeline ka Data Ingestion phase."),

    69: ("Section 12.4: Pipeline Orchestration - Multi-Agent Drafting",
        "Master pipeline ka doosra hissa: Drafting."),

    70: ("pipeline_draft_reports Execution",
        "Code Explanation:\n"
        "- Research, Audience, SEO, aur Structure agents ko run karta hai.\n"
        "Roman Urdu Logic: Planning aur content architecture phase."),

    71: ("Section 12.5: Pipeline Orchestration - Review & Correction",
        "Master pipeline ka teesra hissa: Audit."),

    72: ("pipeline_review_and_correct Execution",
        "Code Explanation:\n"
        "- Draft ko audit karta hai aur required changes emit karta hai.\n"
        "Roman Urdu Logic: Quality assurance phase."),

    73: ("Section 12.6: Master Pipeline Orchestrator",
        "Pure workflow ka central driver."),

    74: ("execute_planner Master Function",
        "Code Explanation:\n"
        "- Ingestion -> Drafting -> Review ko sequential aur parallel steps mein execute karke final package return karta hai.\n"
        "Roman Urdu Logic: Pure system ka engine."),

    75: ("Section 12.7: Safe Pipeline Wrapper",
        "Error handling wrapper."),

    76: ("run_planner Top-Level Wrapper",
        "Code Explanation:\n"
        "- Try/except block ke sath `execute_planner` ko call karta hai taake agar koi API error aaye to clean error message mile.\n"
        "Roman Urdu Logic: Production safety wrapper."),

    77: ("Section 13: User Request Specification",
        "Testing prompt ka setup."),

    78: ("Sample Request Definition",
        "Code Explanation:\n"
        "- Topic: 'Machine Learning course for Pakistani university students', Language: 'English', Words: 600.\n"
        "Roman Urdu Logic: Test run ke input parameters."),

    79: ("Section 13.1: Pipeline Execution Trigger",
        "Notebook run trigger."),

    80: ("Pipeline Execution Trigger (await run_planner)",
        "Code Explanation:\n"
        "- `result = await run_planner(user_request=request)`\n"
        "Roman Urdu Logic: Master pipeline ko live execute karne ka command."),

    81: ("Section 13.2: Output Verification Header",
        "Result display ka header."),

    82: ("Displaying Generated Results & Audit Status",
        "Code Explanation:\n"
        "- Output ke word count, review status, outline, aur generated content ko display karta hai.\n"
        "Roman Urdu Logic: Notebook mein live output dekhna."),

    83: ("Section 13.3: Evidence Replay Verification",
        "Deterministic replay ka evaluation cell."),

    84: ("replay_review_on_run (Audit Replay)",
        "Code Explanation:\n"
        "- Checkpoint folder se run utha kar dobara review run karta hai to verify consistency.\n"
        "Roman Urdu Logic: Scientific verification: check karna ke audit repeat karne par same result deta hai ya nahi."),

    85: ("Section 14: Academic Scope & References",
        "Course conclusion aur limitations ka final markdown cell.")
}


def build_pdf():
    pdf = AcademicPDF(
        doc_title="Part 2: Notebook Cell-by-Cell Explanation",
        subtitle="Complete Code & Line-by-Line Academic Guide (86 Cells)"
    )

    # Cover Page
    pdf.add_cover(
        title="Comprehensive Notebook Walkthrough\nseo-planner.ipynb (All 86 Cells)",
        subtitle="Complete Code Listings and Deep Roman Urdu Explanations\n8th Semester Natural Language Processing (NLP)",
        author="Uzair (NLP Student)",
        project_meta=[
            ("Course", "Natural Language Processing (NLP) - 8th Semester CS"),
            ("Notebook File", "project/notebook/seo-planner.ipynb"),
            ("Total Cells", "86 Cells (43 Code Cells + 43 Markdown Cells)"),
            ("Coverage", "Every single cell code snippet + Roman Urdu Line-by-Line Breakdown"),
            ("Document Scope", "Part 2: Complete Code & Conceptual Walkthrough for Viva / Evaluation")
        ]
    )

    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    print(f"Loaded {len(cells)} cells from notebook.")

    pdf.section_h1("Guide Overview & Structure")
    pdf.body_p(
        "Is document mein aapke academic notebook `seo-planner.ipynb` ke tamam 86 cells ko tarteeb se shamil kiya gaya hai. "
        "Har code cell ka actual executable code box mein show kiya gaya hai, aur uske theek neechay Roman Urdu mein "
        "aik aik line ki wazahat (explanation), NLP concepts, aur output behavior detail se samjhaya gaya hai. "
        "Yeh guide viva examination, project defense, aur code walkthrough ke liye complete resource hai."
    )
    pdf.ln(3)

    for idx, cell in enumerate(cells):
        ctype = cell.get("cell_type", "code")
        source = "".join(cell.get("source", "")).strip()
        meta = CELL_EXPLANATIONS.get(idx, (f"Cell {idx+1} Explanation", "Code logic and functional execution."))
        title, explanation = meta

        if ctype == "markdown":
            # Show markdown section
            pdf.section_h2(f"Cell {idx+1} [Markdown]: {title}")
            clean_md = "\n".join(l for l in source.splitlines() if not l.startswith("# "))
            if clean_md:
                pdf.body_p(f"Markdown Content:\n{clean_md[:300]}")
            pdf.callout("Cell Ka Maqsad (Purpose)", explanation, type="info")
        else:
            # Code cell
            pdf.section_h2(f"Cell {idx+1} [Code Cell]: {title}")
            # print code box
            pdf.code_box(source, max_lines=35)
            # print explanation
            pdf.callout("Detailed Code Explanation (Roman Urdu)", explanation, type="success")
            pdf.ln(2)

    out_path = Path("project/documentation_pdfs/02_Notebook_Cell_Wise_Explanation.pdf")
    pdf.output(str(out_path))
    print(f"Successfully generated PDF 2 at {out_path} ({pdf.page_no()} pages)")

if __name__ == "__main__":
    build_pdf()
