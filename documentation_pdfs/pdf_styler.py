import re
from pathlib import Path
from fpdf import FPDF

FONTS_DIR = Path(__file__).resolve().parents[1] / "streamlit_app" / "assets" / "fonts"
CONSOLAS_PATH = "C:/Windows/Fonts/consola.ttf"

class AcademicPDF(FPDF):
    def __init__(self, doc_title="AI-Powered SEO Content Planner", subtitle=""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title = doc_title
        self.doc_subtitle = subtitle
        self.set_margins(18, 20, 18)
        self.set_auto_page_break(auto=True, margin=20)
        self._setup_fonts()
        self.alias_nb_pages()

    def _setup_fonts(self):
        # Register Noto Sans
        if (FONTS_DIR / "NotoSans-Regular.ttf").exists():
            self.add_font("Noto", fname=str(FONTS_DIR / "NotoSans-Regular.ttf"))
            self.add_font("Noto", style="B", fname=str(FONTS_DIR / "NotoSans-Bold.ttf"))
        # Register Arabic for Urdu words if needed
        if (FONTS_DIR / "NotoNaskhArabic-Regular.ttf").exists():
            self.add_font("Arabic", fname=str(FONTS_DIR / "NotoNaskhArabic-Regular.ttf"))
            try:
                self.set_fallback_fonts(["Arabic"], exact_match=False)
            except Exception:
                pass
        # Register Consolas for code blocks
        if Path(CONSOLAS_PATH).exists():
            self.add_font("CodeFont", fname=CONSOLAS_PATH)
        else:
            self.add_font("CodeFont", fname=str(FONTS_DIR / "NotoSans-Regular.ttf"))

    def header(self):
        if self.page_no() == 1:
            return  # No running header on cover/title page
        self.set_font("Noto", size=8)
        self.set_text_color(110, 125, 145)
        self.cell(0, 7, f"NLP 8th Sem  |  {self.doc_title}", align="L")
        self.set_y(self.get_y() + 8)
        self.set_draw_color(220, 226, 235)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 210 - 18, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Noto", size=8)
        self.set_text_color(120, 135, 155)
        self.set_draw_color(225, 230, 240)
        self.set_line_width(0.3)
        self.line(18, 297 - 15, 210 - 18, 297 - 15)
        page_str = f"Page {self.page_no()} of {{nb}}"
        self.cell(0, 8, f"Department of Computer Science - NLP Project  |  {page_str}", align="C")

    def add_cover(self, title, subtitle, author="Uzair", project_meta=None):
        self.add_page()
        # Top banner background
        self.set_fill_color(24, 43, 73)  # Deep Navy Blue
        self.rect(0, 0, 210, 85, style="F")

        self.set_y(20)
        self.set_font("Noto", style="B", size=22)
        self.set_text_color(255, 255, 255)
        self.multi_cell(210 - 36, 9.5, title, align="C")

        self.ln(3)
        self.set_font("Noto", size=11.5)
        self.set_text_color(180, 205, 240)
        self.multi_cell(210 - 36, 6.5, subtitle, align="C")

        self.set_y(98)
        self.set_text_color(30, 45, 65)
        self.set_font("Noto", style="B", size=13)
        self.cell(210 - 36, 8, "Course & Project Details", new_x="LMARGIN", new_y="NEXT")
        
        self.set_draw_color(40, 90, 180)
        self.set_line_width(0.8)
        self.line(18, self.get_y(), 80, self.get_y())
        self.ln(4)

        meta_items = project_meta or [
            ("Course", "Natural Language Processing (NLP) - 8th Semester"),
            ("Project Name", "AI-Powered SEO Content Planner Using Multi-Agent LLMs"),
            ("Frameworks", "CrewAI, Streamlit, Pydantic v2, SentenceTransformers, FPDF2"),
            ("LLM Providers", "Google Gemini, Groq (gpt-oss-20b), Cerebras (qwen-3.8-27b)"),
            ("Document Type", "Comprehensive Academic & Codebase Technical Guide"),
            ("Language Mode", "Detailed Roman Urdu & English Academic Walkthrough")
        ]

        for label, val in meta_items:
            x = 18
            y = self.get_y()
            self.set_font("Noto", style="B", size=9.5)
            self.set_text_color(40, 55, 75)
            self.set_xy(x, y)
            self.cell(48, 6.5, f"{label}:")
            self.set_xy(x + 48, y)
            self.set_font("Noto", size=9.5)
            self.set_text_color(60, 75, 95)
            self.multi_cell(210 - 36 - 48, 6.5, val)
            self.ln(1)

        self.ln(6)
        self.callout("Guide Ka Maqsad (Purpose)", 
            "Yeh document NLP 8th Semester project ki mukammal samajh, multi-agent LLM pipeline, "
            "codebase architecture, aur un tamam challenges ke practical solutions ko Roman Urdu aur English mein "
            "detail se explain karne ke liye tayyar kiya gaya hai. Is se project viva, evaluation aur presentation "
            "ke har sawal ka mukammal jawaz milta hai.", type="info")

        self.ln(4)

    def section_h1(self, title):
        if self.get_y() > 235:
            self.add_page()
        else:
            self.ln(5)
        self.set_fill_color(238, 244, 252)
        self.set_draw_color(35, 75, 145)
        self.set_line_width(0.6)
        y = self.get_y()
        self.rect(18, y, 210 - 36, 10, style="F")
        self.rect(18, y, 3, 10, style="DF")
        self.set_xy(24, y + 1)
        self.set_font("Noto", style="B", size=12)
        self.set_text_color(22, 45, 90)
        self.cell(210 - 45, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + 12)

    def section_h2(self, title):
        if self.get_y() > 245:
            self.add_page()
        else:
            self.ln(4)
        self.set_font("Noto", style="B", size=10.5)
        self.set_text_color(30, 65, 125)
        self.cell(210 - 36, 6.5, f">>  {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 215, 235)
        self.set_line_width(0.4)
        self.line(18, self.get_y(), 210 - 18, self.get_y())
        self.ln(2.5)

    def section_h3(self, title):
        if self.get_y() > 250:
            self.add_page()
        else:
            self.ln(2)
        self.set_font("Noto", style="B", size=9.5)
        self.set_text_color(45, 60, 85)
        self.cell(210 - 36, 5.5, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_p(self, text):
        self.set_font("Noto", size=9.2)
        self.set_text_color(35, 45, 60)
        self.multi_cell(210 - 36, 5.2, text)
        self.ln(2)

    def bullet(self, bold_prefix, text):
        x = 18
        y = self.get_y()
        if y > 265:
            self.add_page()
            y = self.get_y()
        self.set_xy(x, y)
        self.set_font("Noto", style="B", size=9.2)
        self.set_text_color(30, 45, 70)
        self.cell(5, 5.2, "-")
        prefix_str = f"{bold_prefix} " if bold_prefix else ""
        full_text = f"{prefix_str}{text}"
        self.set_font("Noto", size=9.2)
        self.set_text_color(40, 50, 65)
        self.multi_cell(210 - 36 - 5, 5.2, full_text)
        self.ln(1)

    def callout(self, title, text, type="info"):
        if self.get_y() > 235:
            self.add_page()
        colors = {
            "info": ((240, 246, 255), (35, 85, 175)),
            "success": ((240, 253, 244), (22, 101, 52)),
            "warning": ((255, 251, 235), (180, 83, 9)),
            "danger": ((254, 242, 242), (185, 28, 28))
        }
        bg, border = colors.get(type, colors["info"])
        
        y = self.get_y()
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_line_width(0.8)
        
        # Draw background with padding
        self.set_xy(23, y + 2)
        self.set_font("Noto", style="B", size=9.2)
        self.set_text_color(*border)
        self.cell(210 - 46, 5, title, new_x="LMARGIN", new_y="NEXT")
        
        self.set_xy(23, self.get_y() + 1)
        self.set_font("Noto", size=8.8)
        self.set_text_color(45, 55, 70)
        self.multi_cell(210 - 46, 4.8, text)
        
        y_end = self.get_y() + 3
        h = y_end - y
        self.rect(18, y, 210 - 36, h, style="F")
        self.rect(18, y, 2.5, h, style="DF")
        
        # Redraw text on top of rect
        self.set_xy(23, y + 2)
        self.set_font("Noto", style="B", size=9.2)
        self.set_text_color(*border)
        self.cell(210 - 46, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_xy(23, self.get_y() + 1)
        self.set_font("Noto", size=8.8)
        self.set_text_color(45, 55, 70)
        self.multi_cell(210 - 46, 4.8, text)
        self.set_y(y_end + 2)

    def code_box(self, code_text, max_lines=45):
        lines = code_text.splitlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines] + [f"# ... [Truncated: {len(code_text.splitlines()) - max_lines} more lines in full code file]"]
        
        box_h = len(lines) * 3.8 + 4
        if self.get_y() + min(box_h, 40) > 270:
            self.add_page()

        y = self.get_y()
        self.set_fill_color(245, 247, 250)
        self.set_draw_color(215, 222, 232)
        self.set_line_width(0.3)
        self.rect(18, y, 210 - 36, box_h, style="FD")

        self.set_xy(21, y + 2)
        self.set_font("CodeFont", size=7.5)
        self.set_text_color(35, 45, 60)
        for line in lines:
            l = line.replace("\t", "    ")
            self.cell(210 - 42, 3.8, l[:100], new_x="LMARGIN", new_y="NEXT")
            self.set_x(21)
        self.set_y(y + box_h + 3)
