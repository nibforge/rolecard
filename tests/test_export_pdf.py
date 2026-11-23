import io
from copy import deepcopy

from pypdf import PdfReader

from rolecard.services import export_pdf
from rolecard.services.tailoring import build_cv, build_letter
from tests.helpers import PROFILE
from tests.test_documents import CV, LETTER, OFFER

SPANISH = "¿Diseñé la API de pagos? ¡Sí! Pingüino, acción, “comillas” – 25 %."


def text_of(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def cv_content():
    profile = deepcopy(PROFILE)
    profile["basics"]["name"] = "Begoña Núñez"
    content = build_cv(profile, CV)
    content["sentences"]["s2"]["text"] = SPANISH
    return content


def test_reportlab_builds_an_empty_pdf():
    pdf = export_pdf.render("letter", {"greeting": "", "blocks": [], "closing": "",
                                       "signature": "", "sentences": {}}, "es")
    assert pdf.startswith(b"%PDF") and len(PdfReader(io.BytesIO(pdf)).pages) == 1


def test_cv_pdf_has_extractable_spanish_text_in_order():
    text = text_of(export_pdf.render("cv", cv_content(), "es", "CV"))
    assert "Begoña Núñez" in text
    for part in ("¿Diseñé la API de pagos?", "¡Sí!", "Pingüino", "acción", "“comillas”"):
        assert part in text
    positions = [text.index(t) for t in ("Resumen", "Experiencia", "Habilidades")]
    assert positions == sorted(positions)


def test_deleted_sentences_are_left_out():
    content = cv_content()
    content["sentences"]["s2"]["state"] = "deleted"
    assert "Pingüino" not in text_of(export_pdf.render("cv", content, "en"))


def test_characters_outside_the_font_are_replaced_and_listed():
    content = cv_content()
    content["sentences"]["s1"]["text"] = "Łódź 🚀 team."
    assert export_pdf.substitutions("cv", content, "en") == ["Ł", "ź", "🚀"]
    text = text_of(export_pdf.render("cv", content, "en"))
    assert "?ód? ? team." in text


def test_markup_in_sentences_is_text():
    content = cv_content()
    content["sentences"]["s1"]["text"] = "<b>bold</b> & <font color=red>x</font>"
    text = text_of(export_pdf.render("cv", content, "en"))
    assert "<b>bold</b> & <font color=red>x</font>" in text


def test_letter_pdf_with_greeting_and_signature():
    content = build_letter(PROFILE, LETTER, "es", OFFER)
    content["sentences"]["s2"]["text"] = SPANISH
    text = text_of(export_pdf.render("letter", content, "es"))
    assert content["greeting"] in text and "¡Sí!" in text
    assert PROFILE["basics"]["name"] in text
