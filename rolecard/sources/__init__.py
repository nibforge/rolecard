"""Job sources by API (never scraping): the registry and their settings.

Each connector module exposes ``SOURCE`` (``base.SourceInfo``). A source is used only if
it is in ``[sources] enabled`` and has its keys; keys come from the environment first,
then from ``config.toml`` in the user's data folder, never from the repo.
"""

from __future__ import annotations

import os

from rolecard import config as cfg
from rolecard.sources import adzuna, arbeitnow, remotive
from rolecard.sources.base import SourceInfo

REGISTRY: dict[str, SourceInfo] = {
    s.name: s for s in (remotive.SOURCE, arbeitnow.SOURCE, adzuna.SOURCE)
}
ENV_KEYS = {"adzuna_app_id": cfg.ENV_ADZUNA_ID, "adzuna_app_key": cfg.ENV_ADZUNA_KEY}

if tuple(REGISTRY) != cfg.SOURCE_NAMES:  # one list of names, kept in config
    raise RuntimeError("sources.REGISTRY and config.SOURCE_NAMES differ")


def source_settings(settings: dict, env: dict[str, str] | None = None) -> dict:
    """``[sources]`` with the environment variables applied over the file."""
    env = os.environ if env is None else env
    merged = dict(settings.get("sources", cfg.DEFAULTS["sources"]))
    for key, var in ENV_KEYS.items():
        if env.get(var):
            merged[key] = env[var]
    return merged


def key_origin(settings: dict, key: str, env: dict[str, str] | None = None) -> str:
    """Where a key comes from: ``env``, ``file`` or ``""`` (missing). Never the key."""
    env = os.environ if env is None else env
    if env.get(ENV_KEYS.get(key, "")):
        return "env"
    return "file" if settings.get("sources", {}).get(key) else ""


def enabled(settings: dict) -> list[str]:
    return [n for n in cfg.split_list(source_settings(settings)["enabled"]) if n in REGISTRY]


def status(settings: dict) -> list[dict]:
    """Every source with whether it is enabled and which keys it lacks (for the UI)."""
    merged, on = source_settings(settings), set(enabled(settings))
    return [{"name": s.name, "label": s.label, "site_url": s.site_url,
             "enabled": s.name in on, "missing": s.missing(merged)}
            for s in REGISTRY.values()]
