"""AI providers: pick one from the settings (``auto | claude | openai | none``)."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from rolecard.ai.base import AIError, AIProvider, FakeProvider
from rolecard.ai.claude_code import ClaudeCodeProvider, find_claude
from rolecard.ai.openai_compat import OpenAICompatibleProvider, is_local, valid_base_url
from rolecard.config import ENV_API_KEY

__all__ = ["AIError", "AIProvider", "FakeProvider", "api_key", "get_provider", "is_cloud",
           "resolve"]


def api_key(settings: Mapping, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """The OpenAI-compatible key and where it comes from (``env``, ``config`` or ``""``)."""
    env = os.environ if env is None else env
    if env.get(ENV_API_KEY):
        return env[ENV_API_KEY], "env"
    key = str(settings["ai"].get("api_key", ""))
    return key, ("config" if key else "")


def resolve(settings: Mapping, which: Callable[[], str | None] | None = None) -> str:
    """Which provider ``settings`` lead to: ``claude``, ``openai`` or ``none``."""
    which = which or find_claude
    ai = settings["ai"]
    choice = ai["provider"]
    openai_ready = valid_base_url(str(ai["base_url"])) and bool(ai["model"])
    if choice == "claude":
        return "claude"
    if choice == "openai":
        return "openai" if openai_ready else "none"
    if choice == "auto":  # what the user set up wins over what happens to be installed
        if openai_ready:
            return "openai"
        return "claude" if which() else "none"
    return "none"


def is_cloud(settings: Mapping, kind: str) -> bool:
    """Whether provider ``kind`` sends the CV and the offers off this machine."""
    if kind == "openai":
        return not is_local(str(settings["ai"]["base_url"]))
    return kind == "claude"


def get_provider(settings: Mapping, env: Mapping[str, str] | None = None,
                 which: Callable[[], str | None] | None = None) -> AIProvider | None:
    """The configured provider, or None when there is none."""
    which = which or find_claude
    ai = settings["ai"]
    timeout = int(ai["timeout"])
    kind = resolve(settings, which)
    if kind == "claude":
        return ClaudeCodeProvider(timeout=timeout, executable=which())
    if kind == "openai":
        key, _source = api_key(settings, env)
        return OpenAICompatibleProvider(str(ai["base_url"]), str(ai["model"]), key, timeout)
    return None
