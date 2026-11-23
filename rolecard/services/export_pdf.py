"""PDF export of a reviewed CV or cover letter: one column, extractable text.

Uses the built-in Helvetica (WinAnsi/cp1252: covers Spanish and English, accents, ñ, ü,
¿ and ¡), so no font file ships with the app. Any character outside it is replaced by
``?`` and listed, so the review page can warn before the user exports.
"""

from __future__ import annotations

import io
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from rolecard.i18n import translate

ENCODING = "cp1252"


def _fits(char: str) -> bool:
    try:
        char.encode(ENCODING)
    except UnicodeEncodeError:
        return False
    return char.isprintable() or char in "\n\t"


def clean(text: str) -> tuple[str, set[str]]:
    """NFC text with characters outside the font replaced by ``?`` (and the set of them)."""
    text = unicodedata.normalize("NFC", str(text or ""))
    missing = {c for c in text if not _fits(c)}
    return "".join("?" if c in missing else c for c in text), missing


def _sentence_texts(content: dict, ids: list[str]) -> list[str]:
    sentences = content["sentences"]
    return [sentences[i]["text"] for i in ids if sentences[i]["state"] != "deleted"]


def _entry_lines(content: dict, e: dict):
    title = e.get("role") or e.get("name") or ""
    yield "entry", title + (f" · {e['company']}" if e.get("company") else "")
    dates = " – ".join(v for v in (e.get("start"), e.get("end")) if v)
    yield "meta", " · ".join(v for v in (dates, e.get("location")) if v)
    for text in _sentence_texts(content, e.get("sentences") or []):
        yield "bullet", text


def _cv_lines(content: dict, lang: str):
    """(style, text) pairs of the CV, sections in the order the code built them."""
    h = content["header"]
    yield "name", h.get("name", "")
    if h.get("headline"):
        yield "meta", h["headline"]
    contact = [v for v in [h.get("email"), h.get("phone"), h.get("location"),
                           *(h.get("links") or [])] if v]
    if contact:
        yield "meta", " · ".join(contact)
    for block in content["blocks"]:
        kind = block["type"]
        yield "section", translate(lang, f"document.section.{kind}")
        if kind == "summary":
            yield "body", " ".join(_sentence_texts(content, block["sentences"]))
        elif kind in ("experience", "projects"):
            for e in block["entries"]:
                yield from _entry_lines(content, e)
        elif kind == "skills":
            yield "body", " · ".join(block["items"])
        else:
            fields = ("degree", "institution", "start", "end") if kind == "education" \
                else ("language", "level")
            for e in block["entries"]:
                yield "bullet", " · ".join(e[f] for f in fields if e.get(f))


def _letter_lines(content: dict):
    yield "body", content["greeting"]
    for block in content["blocks"]:
        yield "body", " ".join(_sentence_texts(content, block["sentences"]))
    yield "body", content["closing"]
    yield "body", content["signature"]


def lines(doc_kind: str, content: dict, lang: str) -> list[tuple[str, str]]:
    raw = _cv_lines(content, lang) if doc_kind == "cv" else _letter_lines(content)
    return [(style, text) for style, text in raw if text]


def substitutions(doc_kind: str, content: dict, lang: str) -> list[str]:
    """Characters the PDF cannot show (sorted), to warn on the review page."""
    found: set[str] = set()
    for _, text in lines(doc_kind, content, lang):
        found |= clean(text)[1]
    return sorted(found)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    def make(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base, **{"fontName": "Helvetica", "fontSize": 10.5,
                                                    "leading": 14, **kw})

    return {
        "name": make("name", fontName="Helvetica-Bold", fontSize=18, leading=22),
        "section": make("section", fontName="Helvetica-Bold", fontSize=12.5,
                        spaceBefore=10, spaceAfter=3),
        "entry": make("entry", fontName="Helvetica-Bold", spaceBefore=4),
        "meta": make("meta", textColor="#555555", fontSize=9.5),
        "body": make("body", spaceAfter=8),
        "bullet": make("bullet"),
    }


def render(doc_kind: str, content: dict, lang: str, title: str = "") -> bytes:
    """The PDF bytes of a CV (``cv``) or cover letter (``letter``)."""
    styles = _styles()
    story: list = []
    bullets: list = []

    def flush() -> None:
        if bullets:
            story.append(ListFlowable(list(bullets), bulletType="bullet", leftIndent=12))
            bullets.clear()

    for style, text in lines(doc_kind, content, lang):
        para = Paragraph(escape(clean(text)[0]), styles[style])
        if style == "bullet":
            bullets.append(ListItem(para))
            continue
        flush()
        story.append(para)
    flush()
    if not story:
        story.append(Spacer(1, 1))
    out = io.BytesIO()
    SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=18 * mm, title=clean(title)[0],
                      author="", subject="", creator="rolecard", invariant=1).build(story)
    return out.getvalue()
