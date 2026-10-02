"""PDF export with fpdf2: save_pdf()."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.schemas import Comic

_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}


def _latin1(text: str) -> str:
    """Core PDF fonts only support latin-1; normalise common punctuation and drop the rest."""
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class _ComicPDF(FPDF):
    def __init__(self, title: str, font_path: Path | None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.comic_title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(20, 18, 20)
        if font_path and Path(font_path).exists():
            self.add_font("Body", "", str(font_path))
            self.add_font("Body", "B", str(font_path))
            self.add_font("Body", "I", str(font_path))
            self.body_font, self._clean = "Body", (lambda t: t)
        else:
            self.body_font, self._clean = "Helvetica", _latin1

    def t(self, text: str) -> str:
        return self._clean(text or "")

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self.body_font, "I", 8)
        self.set_text_color(130)
        self.cell(0, 8, self.t(f"{self.comic_title}  -  page {self.page_no()}"), align="C")

    def para(self, text: str, size: float = 11, style: str = "", h: float = 6) -> None:
        self.set_font(self.body_font, style, size)
        self.multi_cell(0, h, self.t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def save_pdf(comic: Comic, exports_dir: Path, font_path: Path | None = None) -> Path:
    """Render the comic to a multi-page PDF and return its path."""
    pdf = _ComicPDF(comic.title, font_path)

    # Cover page
    pdf.add_page()
    pdf.ln(60)
    pdf.set_text_color(20)
    pdf.para(comic.title, size=28, style="B", h=12)
    pdf.ln(6)
    r = comic.request
    pdf.set_text_color(90)
    pdf.para(f"Starring {r.character_name}", size=14)
    pdf.para(f"{r.tone.value.title()} - {r.art_style.value.title()} - {r.setting.value.title()}", size=12)
    pdf.ln(10)
    pdf.para(r.story_prompt, size=11, style="I")

    # One panel per page
    img_w = pdf.w - pdf.l_margin - pdf.r_margin
    for p in comic.panels:
        pdf.add_page()
        pdf.set_text_color(20)
        pdf.para(f"Panel {p.panel_number}: {p.title}", size=16, style="B", h=9)
        pdf.ln(2)
        if p.image_path and Path(p.image_path).exists():
            pdf.image(p.image_path, x=pdf.l_margin, w=img_w, h=min(img_w, 150), keep_aspect_ratio=True)
            pdf.ln(4)
        pdf.set_text_color(80)
        pdf.para(p.scene_description, size=10, style="I")
        pdf.ln(2)
        pdf.set_text_color(20)
        if p.caption:
            pdf.para(p.caption, size=10, style="B")
        if p.narration:
            pdf.para(p.narration)
        for d in p.dialogue:
            pdf.para(f"{d.speaker}: \"{d.line}\"", style="B")

    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = exports_dir / f"comic_{comic.id[:8]}_{stamp}.pdf"
    pdf.output(str(out))
    return out
