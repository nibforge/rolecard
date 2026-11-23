"""Normalising untrusted offers with the limits of a hand-pasted one (R5)."""

from rolecard.services.jobs import MAX_FIELD, MAX_TEXT
from rolecard.sources.base import RawOffer
from rolecard.sources.normalize import clean, html_to_text, normalize

LONG = "Python and SQL work for an invented company, described at enough length to pass. "


def raw(**kw):
    base = dict(source="remotive", external_id="1", url="https://remotive.com/x",
                title="Dev", company="Acme Fict", location="Remote", description=LONG)
    base.update(kw)
    return RawOffer(**base)


def test_html_to_text_drops_tags_scripts_and_attributes():
    text = html_to_text('<p onclick="x()">Hello <b>you</b></p><script>alert(1)</script>'
                        '<style>p{}</style><ul><li>One</li><li>Two &amp; three</li></ul>')
    assert text == "Hello you\n\n- One\n\n- Two & three"
    assert "alert" not in text and "onclick" not in text


def test_clean_repairs_mojibake_control_and_length():
    assert clean("TÃ©cnico\x00 de‮  sistemas", 100) == "Técnico de sistemas"
    assert len(clean("x" * 1000, MAX_FIELD)) == MAX_FIELD


def test_normalize_builds_text_with_header():
    offer = normalize(raw(title="<b>Dev</b>", description="<p>" + LONG + "</p>"))
    assert offer.title == "Dev"
    assert offer.text.startswith("Dev — Acme Fict — Remote\n\nPython and SQL")


def test_too_short_is_rejected():
    assert normalize(raw(description="tiny")) is None


def test_long_text_is_truncated_and_bad_url_dropped():
    offer = normalize(raw(description=LONG * 2000, url="javascript:alert(1)"))
    assert len(offer.text) == MAX_TEXT and offer.url == ""
    assert normalize(raw(url="https://x.test/" + "a" * 3000)).url == ""


def test_title_with_markup_becomes_inert_text():
    offer = normalize(raw(title="Backend <img src=x onerror=alert(1)> Engineer"))
    assert "<" not in offer.title and "onerror" not in offer.title
