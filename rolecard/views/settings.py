"""Settings page: AI provider, endpoint, model, key and the connection test; the job
sources; the interface language and theme."""

from __future__ import annotations

from copy import deepcopy

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from rolecard import config as cfg
from rolecard import sources
from rolecard.ai import AIError, api_key, find_claude, is_cloud, resolve
from rolecard.ai.openai_compat import valid_base_url
from rolecard.views import current_provider

bp = Blueprint("settings", __name__, url_prefix="/settings")

MAX_TEXT = 500


def _bad_secret(value: str) -> bool:
    """A key is one printable token: no spaces, line breaks or control characters (they
    would break the request header or the query and only come from a bad paste)."""
    return len(value) > MAX_TEXT or any(c.isspace() or not c.isprintable() for c in value)


def _settings() -> dict:
    return current_app.config["ROLECARD"]


def _context(form: dict | None = None, errors: dict | None = None, test=None) -> dict:
    settings = _settings()
    ai = settings["ai"]
    _key, key_source = api_key(settings)
    return {
        "form": form or {k: ai[k] for k in ("provider", "base_url", "model", "timeout")},
        "errors": errors or {},
        "providers": cfg.PROVIDERS,
        "claude_found": bool(find_claude()),
        "active_provider": (active := resolve(settings)),
        "cloud": is_cloud(settings, active),
        "key_source": key_source,
        "test": test,
        "sources": _sources_context(settings),
        "ui": {"language": "", "theme": "system", **settings.get("ui", {})},
        "languages": cfg.LANGUAGES,
        "themes": cfg.THEMES,
    }


def _sources_context(settings: dict) -> dict:
    """Sources for the form: state and key ORIGIN only, never a key's value."""
    return {
        "list": sources.status(settings),
        "origins": {k: sources.key_origin(settings, k) for k in sources.ENV_KEYS},
        "env": sources.ENV_KEYS,
        "country": sources.source_settings(settings)["adzuna_country"],
        "countries": cfg.ADZUNA_COUNTRIES,
    }


@bp.get("")
def edit():
    return render_template("settings.html", **_context())


def _validate(form) -> tuple[dict, dict]:
    values = {
        "provider": form.get("provider", ""),
        "base_url": form.get("base_url", "").strip(),
        "model": form.get("model", "").strip(),
        "timeout": form.get("timeout", "").strip(),
    }
    errors = {}
    if values["provider"] not in cfg.PROVIDERS:
        errors["provider"] = "settings.error.provider"
    if values["base_url"] and (not valid_base_url(values["base_url"])
                               or len(values["base_url"]) > MAX_TEXT):
        errors["base_url"] = "settings.error.base_url"
    if len(values["model"]) > MAX_TEXT:
        errors["model"] = "settings.error.too_long"
    if _bad_secret(form.get("api_key", "").strip()):
        errors["api_key"] = "settings.error.secret"
    try:
        timeout = int(values["timeout"])
        if not 1 <= timeout <= 3600:
            raise ValueError
        values["timeout"] = timeout
    except ValueError:
        errors["timeout"] = "settings.error.timeout"
    return values, errors


@bp.post("")
def save():
    values, errors = _validate(request.form)
    if errors:
        return render_template("settings.html", **_context(values, errors)), 400
    new = deepcopy(_settings())
    new["ai"].update(values)
    typed_key = request.form.get("api_key", "").strip()
    if request.form.get("clear_key"):
        new["ai"]["api_key"] = ""
    elif typed_key:
        new["ai"]["api_key"] = typed_key
    cfg.save_config(current_app.config["DATA_DIR"], new)
    current_app.config["ROLECARD"] = new
    flash("settings.saved", "exito")
    return redirect(url_for("settings.edit"))


@bp.post("/test")
def test():
    try:
        provider = current_provider(strict=True)
        if provider is None:
            result = {"ok": False, "key": "settings.test.none"}
        else:
            provider.check()
            result = {"ok": True, "key": "settings.test.ok", "provider": provider.name}
    except AIError as exc:
        current_app.logger.info("connection test failed: %s", exc.code)
        result = {"ok": False, "key": exc.message_key}
    if request.headers.get("HX-Request"):
        return render_template("_test_result.html", test=result)
    return render_template("settings.html", **_context(test=result))


@bp.post("/sources")
def save_sources():
    form = request.form
    country = form.get("adzuna_country", "")
    typed = {k: form.get(k, "").strip() for k in sources.ENV_KEYS}
    if country not in cfg.ADZUNA_COUNTRIES or any(map(_bad_secret, typed.values())):
        errors = {"sources": "settings.error.sources"}
        return render_template("settings.html", **_context(errors=errors)), 400
    new = deepcopy(_settings())
    chosen = [n for n in cfg.SOURCE_NAMES if form.get(f"enabled_{n}")]
    new["sources"].update(enabled=",".join(chosen), adzuna_country=country)
    for key, value in typed.items():
        if form.get(f"clear_{key}"):
            new["sources"][key] = ""
        elif value:
            new["sources"][key] = value
    cfg.save_config(current_app.config["DATA_DIR"], new)
    current_app.config["ROLECARD"] = new
    flash("settings.saved", "exito")
    return redirect(url_for("settings.edit", _anchor="fuentes"))


@bp.post("/ui")
def save_ui():
    """Interface language ("" follows the browser) and theme (system, light or dark)."""
    language, theme = request.form.get("language", ""), request.form.get("theme", "")
    if language not in cfg.LANGUAGES or theme not in cfg.THEMES:
        errors = {"ui": "settings.error.ui"}
        return render_template("settings.html", **_context(errors=errors)), 400
    new = deepcopy(_settings())
    new.setdefault("ui", {}).update(language=language, theme=theme)
    cfg.save_config(current_app.config["DATA_DIR"], new)
    current_app.config["ROLECARD"] = new
    flash("settings.saved", "exito")
    return redirect(url_for("settings.edit", _anchor="apariencia"))
