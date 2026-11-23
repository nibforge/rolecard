"""Tiny i18n: flat JSON catalogues per language, chosen per request.

Templates call ``t('key')``; Python code calls ``translate(lang, 'key')``. Every visible
string lives in ``rolecard/locales/<lang>.json``; both files must have the same keys.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

from flask import Flask, g, has_request_context, request

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED = ("en", "es")
DEFAULT = "en"

log = logging.getLogger(__name__)


@cache
def catalogue(lang: str) -> dict[str, str]:
    """The key → text mapping for ``lang`` (loaded once)."""
    path = LOCALES_DIR / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def pick_language(accept_language, forced: str = "") -> str:
    """``forced`` (from config) wins; otherwise the best Accept-Language match."""
    if forced in SUPPORTED:
        return forced
    if accept_language is None:
        return DEFAULT
    return accept_language.best_match(SUPPORTED, default=DEFAULT) or DEFAULT


def translate(lang: str, key: str, **params: object) -> str:
    """Text for ``key`` in ``lang`` (English, then the key itself, as fallbacks)."""
    text = catalogue(lang).get(key)
    if text is None:
        log.warning("missing i18n key %r for %s", key, lang)
        text = catalogue(DEFAULT).get(key, key)
    return text.format(**params) if params else text


def current_language() -> str:
    if has_request_context() and "lang" in g:
        return g.lang
    return DEFAULT


def t(key: str | list | tuple, **params: object) -> str:
    """Translate into the current request's language. ``key`` may also be ``[key,
    params]`` (a flashed message that carries its values, e.g. ``AIError.message_key``)."""
    if isinstance(key, list | tuple):
        key, params = key[0], {**key[1], **params}
    return translate(current_language(), key, **params)


def number(value: int) -> str:
    """Thousands separated the local way: 1,042 in English, 1.042 in Spanish."""
    text = f"{value:,}"
    return text.replace(",", ".") if current_language() == "es" else text


def short_date(value) -> str:
    """Day and abbreviated month in the current language: 24 Nov, 24 nov. A datetime is
    shown in local time; one without a zone is UTC (what the app stores)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone()
    return t("date.short", day=value.day, month=t(f"date.month.{value.month}"))


def init_i18n(app: Flask) -> None:
    @app.before_request
    def _set_language() -> None:
        forced = str(app.config.get("ROLECARD", {}).get("ui", {}).get("language", ""))
        g.lang = pick_language(request.accept_languages, forced)

    @app.after_request
    def _vary(response):
        response.vary.add("Accept-Language")
        return response

    app.jinja_env.globals["t"] = t
    app.jinja_env.globals["current_language"] = current_language
    app.jinja_env.filters["num"] = number
    app.jinja_env.filters["shortdate"] = short_date
