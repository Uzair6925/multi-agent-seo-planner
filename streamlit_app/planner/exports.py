import re
from pathlib import Path

STATUS_LABELS = {
    "automated_review_passed": "Automated review passed",
    "needs_revision": "Draft needs attention",
    "draft_without_sources": "Draft without retrieved sources",
    "review_incomplete": "Review incomplete",
}


def safe_markdown(text):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]*\)", r"\1", text)


def refs(ids):
    return "\n\nSources: " + ", ".join(dict.fromkeys(ids)) if ids else ""


def content_markdown(result):
    article, brief = result.get("article"), result["brief"]
    if article:
        parts = ["# " + article["title"], article["introduction"]]
        for section in article["sections"]:
            parts.extend(["## " + section["heading"], section["body"] + refs(section["chunk_ids"])])
        if article.get("faqs"):
            parts.append("## Frequently asked questions" if article["output_language"] != "Urdu" else "## عام سوالات")
            for faq in article["faqs"]:
                parts.extend(["### " + faq["question"], faq["answer"] + refs(faq["chunk_ids"])])
    else:
        parts = ["# " + brief["title"], brief["meta_description"], "## Main heading", brief["h1"]]
        for section in brief["outline"]:
            parts.append("## " + section["h2"])
            parts.extend("### " + heading for heading in section["h3"])
            parts.extend("- " + note for note in section["coverage_notes"])
            if section["chunk_ids"]:
                parts.append(refs(section["chunk_ids"]).strip())
        if brief.get("faqs"):
            parts.append("## Frequently asked questions")
            parts.extend("- " + q for q in brief["faqs"])
    return safe_markdown("\n\n".join(parts))


def download_markdown(result):
    report = result.get("article") or result["brief"]
    parts = [content_markdown(result), "---", "## SEO details",
             "Meta description: " + report["meta_description"],
             "Suggested keywords: " + ", ".join(result["brief"]["suggested_keywords"]),
             "## Review and limitations", STATUS_LABELS[result["status"]],
             "Automated review checks supplied evidence; it is not independent fact checking."]
    parts.extend("- " + n for n in dict.fromkeys(result["notices"] + result["brief"]["limitations"]))
    for target, review in result["review"].items():
        parts.extend(f"- {target}: {issue['required_change']}" for issue in review.get("issues", []))
    parts.append("## References")
    if not result["sources"]:
        parts.append("No external references were retrieved.")
    for sid, source in result["sources"].items():
        title = source.get("title", "Reference")
        parts.append(f"- {sid}: {title}" + (f" — {source['url']}" if source.get("url") else " (uploaded document)"))
    return safe_markdown("\n\n".join(parts))


def make_pdf(result):
    from fpdf import FPDF
    fonts = Path(__file__).resolve().parents[1] / "assets" / "fonts"

    class Document(FPDF):
        def footer(self):
            self.set_y(-14)
            self.set_font("Noto", size=8)
            self.set_text_color(110, 120, 135)
            self.cell(0, 6, f"SEO Content Planner  |  {self.page_no()}", align="C")

    pdf = Document()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, margin=22)
    pdf.add_font("Noto", fname=str(fonts / "NotoSans-Regular.ttf"))
    pdf.add_font("Noto", style="B", fname=str(fonts / "NotoSans-Bold.ttf"))
    pdf.add_font("Arabic", fname=str(fonts / "NotoNaskhArabic-Regular.ttf"))
    pdf.set_fallback_fonts(["Arabic"], exact_match=False)
    try:
        pdf.set_text_shaping(True)
    except Exception:
        pass
    pdf.add_page()
    pdf.set_title((result.get("article") or result["brief"])["title"])
    for line in download_markdown(result).splitlines():
        if not line.strip():
            pdf.ln(2)
            continue
        if line.strip() == "---":
            pdf.ln(4)
            continue
        heading = len(line) - len(line.lstrip("#")) if line.startswith("#") else 0
        text = line.lstrip("# ") if heading else line
        text = text.replace("**", "").replace("`", "")
        text = re.sub(r"[\u2010-\u2014]", "-", text)
        arabic = bool(re.search(r"[\u0600-\u06ff]", text))
        size = {1: 21, 2: 14, 3: 11}.get(heading, 10)
        pdf.set_font("Arabic" if arabic else "Noto", style="B" if heading and not arabic else "", size=size)
        pdf.set_text_color(*( (35, 52, 82) if heading else (40, 45, 55)))
        if heading:
            if pdf.will_page_break(24):
                pdf.add_page()
            pdf.ln(3)
        pdf.multi_cell(0, size * 0.55, text=text, align="R" if arabic else "L",
                       new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR" if len(text.split()) == 1 else "WORD")
    return bytes(pdf.output())
