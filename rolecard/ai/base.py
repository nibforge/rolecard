"""Provider interface, errors, JSON parsing and the fake provider used in tests.

Every answer goes through ``AIProvider.complete_json``: the raw text must be ONE JSON
object, optionally with whitespace around it or inside ONE ``` / ```json fence (no other
text), and it must match the operation's strict schema. Otherwise the whole answer is
rejected; an object is never fished out of prose.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable

from rolecard.ai.schema import find_errors
from rolecard.encoding import fix_mojibake

ERROR_CODES = ("not_installed", "not_configured", "timeout", "failed", "http", "network",
               "not_json", "invalid", "insecure", "quota", "busy")

_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n?(.*?)\s*```\Z", re.S | re.I)

SYSTEM_PROMPT = (
    "You are a careful assistant inside a local job-search app. Reply with ONLY one JSON "
    "object: no text before or after it, no Markdown and no code fences."
)


log = logging.getLogger(__name__)

PING_PROMPT = 'Reply with exactly this JSON object and nothing else: {"ok": true}'
PING_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


class AIError(Exception):
    """A provider failure. ``code`` maps to the i18n key ``ai.error.<code>``."""

    def __init__(self, code: str, detail: str = "",
                 errors: tuple[tuple[str, str], ...] = (),
                 retry_after: int | None = None) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown AI error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.errors = errors  # (field path, problem code) when ``code`` is "invalid"
        self.retry_after = retry_after  # seconds the service asks to wait ("quota")

    @property
    def message_key(self) -> str | list:
        """The i18n key; for a quota error with a known wait, ``[key, params]`` (``t``
        takes both), so the message says when to try again."""
        if self.code == "quota" and self.retry_after:
            minutes = -(-self.retry_after // 60)  # rounded up: never "try in 0 min"
            return ["ai.error.quota_wait", {"hours": minutes // 60, "minutes": minutes % 60}]
        return f"ai.error.{self.code}"


def parse_json_object(raw: str) -> dict:
    """The JSON object in ``raw``; any text around it is an error."""
    text = raw.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()
        if "```" in text:
            raise AIError("not_json", "more than one code block")
    if not (text.startswith("{") and text.endswith("}")):
        raise AIError("not_json", "answer is not a bare JSON object")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("not_json", str(exc)) from exc
    if not isinstance(data, dict):
        raise AIError("not_json", "answer is not an object")
    return data


class AIProvider(ABC):
    """A language model that turns a prompt into a validated JSON object."""

    name = "base"

    @abstractmethod
    def complete(self, prompt: str, schema: dict | None = None) -> str:
        """Send ``prompt`` and return the model's raw text (raises ``AIError``).

        ``schema`` lets a provider ask its API for structured output when it can."""

    def complete_json(self, prompt: str, schema: dict) -> dict:
        raw = fix_mojibake(self.complete(prompt, schema))
        try:
            data = parse_json_object(raw)
        except AIError as exc:
            _log_rejected(exc, raw)
            raise
        problems = find_errors(data, schema)
        if problems:
            exc = AIError("invalid", str(problems[0]),
                          tuple((p.path.removeprefix("$."), p.code) for p in problems))
            _log_rejected(exc, raw, problems)
            raise exc
        return data

    def check(self) -> None:
        """Round-trip a tiny request; raises ``AIError`` if the provider is not usable."""
        self.complete_json(PING_PROMPT, PING_SCHEMA)


def _log_rejected(exc: AIError, raw: str, problems=()) -> None:
    """Local log only (never the UI): why the answer was rejected, its length and a hash.

    Never its text: an answer can quote the user's CV (constitution X, no personal data
    in logs). The hash tells two failures with the same answer apart."""
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    lines = [f"AI answer rejected ({exc.code}): {exc.detail}"]
    lines += [f"  - {p}" for p in problems]
    lines.append(f"Answer: {len(raw)} chars, sha256 {digest}")
    log.warning("\n".join(lines))


class FakeProvider(AIProvider):
    """Test double: answers from a list (or a function of the prompt) and records prompts."""

    name = "fake"

    def __init__(self, answers: list[str | Exception] | Callable[[str], str] | str) -> None:
        self._answers = [answers] if isinstance(answers, str) else answers
        self.prompts: list[str] = []

    def complete(self, prompt: str, schema: dict | None = None) -> str:
        self.prompts.append(prompt)
        if callable(self._answers):
            return self._answers(prompt)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer
