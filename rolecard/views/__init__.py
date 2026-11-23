"""Blueprints, shared view helpers and the navigation."""

from __future__ import annotations

from datetime import datetime

from flask import Flask, current_app

from rolecard.ai import AIError, AIProvider, get_provider
from rolecard.config import THEMES
from rolecard.sources import REGISTRY


def current_provider(strict: bool = False) -> AIProvider | None:
    """The AI provider from the current settings (tests inject ``AI_PROVIDER_FACTORY``).

    A setup that would send the key over plain http counts as no provider, so no page
    fails; with ``strict`` the ``AIError`` goes up for the connection test to show it."""
    factory = current_app.config.get("AI_PROVIDER_FACTORY")
    if factory is not None:
        return factory()
    try:
        return get_provider(current_app.config["ROLECARD"])
    except AIError as exc:
        if strict or exc.code != "insecure":
            raise
        return None


def local_now() -> datetime:
    """Aware local now; tests inject ``CLOCK`` (a callable returning an aware datetime)."""
    clock = current_app.config.get("CLOCK")
    return clock() if clock else datetime.now().astimezone()


def init_views(app: Flask) -> None:
    @app.context_processor
    def _nav():
        from rolecard.views import nav

        def nav_items():
            return nav.nav_items(app)

        def ui_theme():
            theme = app.config["ROLECARD"].get("ui", {}).get("theme", "system")
            return theme if theme in THEMES else "system"

        return {"nav_items": nav_items, "ui_theme": ui_theme,
                "current_section": nav.current_section,
                "has_settings": "settings.edit" in app.view_functions}

    app.jinja_env.globals["source_registry"] = REGISTRY  # attribution in imported macros
    app.jinja_env.filters["isolocaltime"] = _iso_local
    app.jinja_env.filters["localdate"] = lambda value: value.astimezone().strftime("%Y-%m-%d")
    app.jinja_env.filters["localdatetime"] = (
        lambda value: value.astimezone().strftime("%Y-%m-%d %H:%M")
    )


def _iso_local(value: str, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """An ISO timestamp stored as text (search summaries) in local time; '' if invalid."""
    try:
        return datetime.fromisoformat(value).astimezone().strftime(fmt)
    except (TypeError, ValueError):
        return ""
