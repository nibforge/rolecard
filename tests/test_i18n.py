import json
import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import g
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from rolecard import i18n

PKG = Path(__file__).resolve().parent.parent / "rolecard"
TEMPLATES = sorted((PKG / "templates").rglob("*.html"))
VISIBLE_ATTRS = {"title", "alt", "placeholder", "aria-label", "aria-description", "value", "label"}
JINJA = re.compile(r"{{.*?}}|{%.*?%}|{#.*?#}", re.S)


def _accept(header):
    return parse_accept_header(header, LanguageAccept)


@pytest.mark.parametrize(
    "header, expected",
    [
        ("es-ES,es;q=0.9", "es"),
        ("es", "es"),
        ("fr-FR, es;q=0.5", "es"),
        ("en-GB,en;q=0.9,es;q=0.8", "en"),
        ("de-DE", "en"),
        ("", "en"),
    ],
)
def test_pick_language_from_accept_language(header, expected):
    assert i18n.pick_language(_accept(header)) == expected


def test_configured_language_wins():
    assert i18n.pick_language(_accept("es"), forced="en") == "en"
    assert i18n.pick_language(None) == "en"


def test_pages_follow_accept_language(client):
    es = client.get("/", headers={"Accept-Language": "es-ES"}).get_data(as_text=True)
    en = client.get("/").get_data(as_text=True)
    assert '<html lang="es">' in es and "Panel" in es
    assert '<html lang="en">' in en and "Dashboard" in en


def test_error_pages_are_translated(client):
    body = client.get("/missing", headers={"Accept-Language": "es"}).get_data(as_text=True)
    assert "Página no encontrada" in body


def test_translate_params_and_fallbacks():
    assert i18n.translate("es", "app.name") == "rolecard"
    assert i18n.translate("es", "no.such.key") == "no.such.key"


def test_catalogues_have_the_same_keys():
    en, es = i18n.catalogue("en"), i18n.catalogue("es")
    assert set(en) == set(es)
    assert all(isinstance(v, str) and v.strip() for v in [*en.values(), *es.values()])


def test_catalogue_files_are_valid_json():
    for lang in i18n.SUPPORTED:
        json.loads((PKG / "locales" / f"{lang}.json").read_text(encoding="utf-8"))


class _LiteralFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        for name, value in attrs:
            if name in VISIBLE_ATTRS and value and re.search(r"[^\W\d_]", value):
                self.found.append(f"{tag}[{name}]={value!r}")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and re.search(r"[^\W\d_]", data):
            self.found.append(data.strip())


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_templates_have_no_literal_text(template):
    source = JINJA.sub("", template.read_text(encoding="utf-8"))
    finder = _LiteralFinder()
    finder.feed(source)
    assert finder.found == []


def test_literal_text_guard_catches_text():
    finder = _LiteralFinder()
    finder.feed(JINJA.sub("", '<p>Hello {{ t("x") }}</p><input placeholder="Name">'))
    assert finder.found == ["Hello", "input[placeholder]='Name'"]


def test_every_key_used_in_templates_exists():
    used = set()
    for template in TEMPLATES:
        source = template.read_text(encoding="utf-8")
        used |= set(re.findall(r"""\bt\(\s*['"]([\w.]*\w)['"]\s*\)""", source))
    assert used, "templates should use t()"
    assert used - set(i18n.catalogue("en")) == set()


@pytest.mark.parametrize("lang", i18n.SUPPORTED)
def test_required_word_reason_is_translated(lang):
    # Summaries saved by earlier versions name the required-word filter "required".
    text = i18n.translate(lang, "search.reason.required", count=2, word="python")
    assert text != "search.reason.required" and "2" in text and "python" in text


@pytest.mark.parametrize(("lang", "expected"), [("en", "24 Nov"), ("es", "24 nov")])
def test_short_date_follows_the_language(app, lang, expected):
    with app.test_request_context():
        g.lang = lang
        assert i18n.short_date(date(2026, 11, 24)) == expected


def test_short_date_takes_a_naive_datetime_as_utc(app, monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    with app.test_request_context():
        g.lang = "en"
        late = datetime(2026, 11, 24, 23, 30)
        assert i18n.short_date(late) == i18n.short_date(late.replace(tzinfo=UTC))
