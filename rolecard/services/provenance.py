"""Provenance of generated sentences, checked by the server (never trusted from the AI).

A document's ``content["sentences"]`` maps a sentence id to::

    {"text": str, "sources": [path, ...], "state": STATE, "reason": REASON}

A source is a dotted path into the master profile (``experience.0.highlights.2``,
``skills.3``, ``basics.summary``) or, in a cover letter only, ``offer``. Paths are
matched against a strict pattern and resolved by walking the profile dict: they are
never evaluated.

A sentence is UNSOURCED when it has no sources, a path does not exist, or it contains a
figure (number, percentage, year) that is not in the text of its sources. The user
resolves it by editing (``edited``), deleting (``deleted``) or confirming
(``confirmed``); those states are kept on later checks.

A sourced sentence still waits for the user's confirmation (``CONFIRM_REASONS``) when it
cites only the offer, or when it names a TERM that is not in the text of its sources: a
capitalised word that does not start the sentence, an acronym or a technical name
(``PostgreSQL``, ``C++``, ``Node.js``). The check is literal and soft: it catches a name
taken from the offer and claimed for the user, not a false claim in plain words.
"""

from __future__ import annotations

import re

OFFER = "offer"
STATES = ("sourced", "unsourced", "edited", "confirmed", "deleted")
USER_STATES = frozenset({"edited", "confirmed", "deleted"})
# ``offer_only`` marks a SOURCED letter sentence that cites only the offer: it is not an
# error, but it blocks the export until the user confirms it.
# ``term`` marks a SOURCED sentence that names a term its sources do not contain.
REASONS = ("no_sources", "bad_path", "offer_not_allowed", "number", "profile_changed",
           "offer_only", "term")
CONFIRM_REASONS = frozenset({"offer_only", "term"})
MAX_SOURCES = 8

_PATH = re.compile(r"^[a-z]{1,20}(\.(\d{1,3}|[a-z]{1,20}))*$")
_ROOTS = frozenset({"basics", "experience", "projects", "education", "languages", "skills"})
_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS = re.compile(r"^\d{1,3}([.,])\d{3}(?:\1\d{3})*$")
_WORD = re.compile(r"[^\W\d_][\w+#]*(?:[.\-][\w+#]+)*")
_SENTENCE_START = re.compile(r"(?:^|[.!?:;\n]\s*|[\"'(«“]\s*)$")
_COMMON = frozenset("""
i i'm my me we our the a an and or in on at for with to of as by
el la los las un una y o en con de del al mi mis por para como
e.g i.e etc
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())


def resolve(profile: dict, path: str) -> str | None:
    """Text at ``path`` in the profile, or None if the path is malformed or missing.

    A path names at least one entry (``experience.0``) or a ``basics`` field: a whole
    section is too broad to back a sentence. An entry gives the text of its leaves.
    """
    if not isinstance(path, str) or len(path) > 80 or not _PATH.match(path):
        return None
    parts = path.split(".")
    if parts[0] not in _ROOTS or len(parts) < 2:
        return None
    if parts[0] != "basics" and not parts[1].isdigit():
        return None
    node = profile
    for part in parts:
        if isinstance(node, dict) and not part.isdigit() and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    text = _leaves(node)
    return text if text.strip() else None


def _leaves(node) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return " · ".join(t for t in (_leaves(v) for v in node.values()) if t)
    if isinstance(node, list):
        return " · ".join(t for t in (_leaves(v) for v in node) if t)
    return ""


def figures(text: str) -> set[str]:
    """Numbers in ``text``: ``1.500``, ``1,500`` and ``1500`` compare equal (thousands);
    ``1,5`` and ``1.5`` are the same decimal, and differ from ``15``."""
    return {re.sub(r"[.,]", "", m) if _THOUSANDS.match(m) else m.replace(",", ".")
            for m in _FIGURE.findall(text)}


def terms(text: str) -> list[str]:
    """Names in ``text`` that a source must contain (see the module docstring)."""
    found = []
    for match in _WORD.finditer(text):
        word = match.group()
        if word.casefold() in _COMMON:
            continue
        technical = any(c in "+#." for c in word) or any(c.isupper() for c in word[1:])
        proper = word[0].isupper() and not _SENTENCE_START.search(text[:match.start()])
        if technical or proper:
            found.append(word)
    return found


def missing_terms(text: str, sources: str) -> list[str]:
    haystack = sources.casefold()
    return [w for w in terms(text) if w.casefold() not in haystack]


def source_text(path: str, profile: dict, offer_text: str) -> str | None:
    if path == OFFER:
        return offer_text
    return resolve(profile, path)


def verify(sentence: dict, profile: dict, offer_text: str = "",
           allow_offer: bool = False) -> tuple[str, str]:
    """(state, reason) for an AI sentence: ``("sourced", "")``, ``("sourced", why)`` (to
    confirm) or ``("unsourced", why)``."""
    sources = sentence.get("sources")
    if not isinstance(sources, list) or not sources or len(sources) > MAX_SOURCES:
        return "unsourced", "no_sources"
    texts = []
    for path in sources:
        if path == OFFER and not allow_offer:
            return "unsourced", "offer_not_allowed"
        text = source_text(path, profile, offer_text)
        if text is None:
            return "unsourced", "bad_path"
        texts.append(text)
    if not figures(sentence.get("text", "")) <= figures(" ".join(texts)):
        return "unsourced", "number"
    if all(path == OFFER for path in sources):
        return "sourced", "offer_only"
    if missing_terms(sentence.get("text", ""), " ".join(texts)):
        return "sourced", "term"
    return "sourced", ""


def snapshot(sentences: dict, profile: dict) -> dict:
    """Profile text of every cited path, taken when the document is generated."""
    snap = {}
    for sentence in sentences.values():
        for path in sentence.get("sources") or []:
            if path != OFFER:
                text = resolve(profile, path)
                if text is not None:
                    snap[path] = text
    return snap


def check(content: dict, profile: dict, snap: dict, offer_text: str = "",
          allow_offer: bool = False) -> dict:
    """Re-check every sentence the user has not resolved against the CURRENT profile.

    A cited path that is gone or whose text differs from the snapshot makes the sentence
    unsourced with ``profile_changed``. Returns ``content`` (modified in place).
    """
    for sentence in content.get("sentences", {}).values():
        if sentence.get("state") in USER_STATES:
            continue
        state, reason = verify(sentence, profile, offer_text, allow_offer)
        changed = any(path != OFFER and resolve(profile, path) != snap.get(path)
                      for path in sentence.get("sources") or [])
        if changed:
            state, reason = "unsourced", "profile_changed"
        sentence["state"], sentence["reason"] = state, reason
    return content


def needs_confirmation(sentence: dict) -> bool:
    """A sourced sentence the user must confirm: it cites only the offer, or it names a
    term its sources do not contain."""
    return sentence.get("state") == "sourced" and sentence.get("reason") in CONFIRM_REASONS


def pending_offer(content: dict) -> int:
    """How many offer-only sentences are not confirmed yet (they block the export)."""
    return sum(1 for s in content.get("sentences", {}).values() if needs_confirmation(s))


def unresolved(content: dict) -> int:
    """How many sentences are still unsourced (they block the export)."""
    return sum(1 for s in content.get("sentences", {}).values() if s.get("state") == "unsourced")


def resolve_sentence(sentence: dict, action: str, text: str = "") -> None:
    """Apply the user's ``edit`` | ``delete`` | ``confirm`` to one sentence."""
    if action == "edit":
        if not text.strip():
            raise ValueError("empty text")
        sentence.setdefault("original", sentence.get("text", ""))
        sentence["text"], sentence["state"] = text.strip(), "edited"
    elif action == "delete":
        sentence["state"] = "deleted"
    elif action == "confirm" and (sentence.get("state") == "unsourced"
                                  or needs_confirmation(sentence)):
        sentence["state"] = "confirmed"
    else:
        raise ValueError(f"unknown action: {action}")
