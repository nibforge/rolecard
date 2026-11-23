"""Build a tailored CV or cover letter from the master profile and the AI's answer.

The CODE copies every structural fact (name, contact, roles, employers, dates, degrees,
languages, skills) from the profile. The AI only picks entries by index and writes
sentences; each sentence is checked by ``provenance.verify`` here.

Document ``content``::

    {"header": {...}, "blocks": [{"type": ..., ...}], "sentences": {id: sentence}}

and, for a letter, ``greeting``, ``closing`` and ``signature`` (from i18n and the profile).
"""

from __future__ import annotations

from rolecard.ai import AIError
from rolecard.i18n import translate
from rolecard.services import provenance

HEADER_FIELDS = ("name", "headline", "email", "phone", "location", "links")
ENTRY_FIELDS = {
    "experience": ("role", "company", "start", "end", "location"),
    "projects": ("name",),
}
COPIED_FIELDS = {
    "education": ("degree", "institution", "start", "end"),
    "languages": ("language", "level"),
}


class _Builder:
    def __init__(self, profile: dict, offer_text: str, allow_offer: bool) -> None:
        self.profile = profile
        self.offer_text = offer_text
        self.allow_offer = allow_offer
        self.sentences: dict[str, dict] = {}

    def add(self, items: list[dict]) -> list[str]:
        ids = []
        for item in items:
            sid = f"s{len(self.sentences) + 1}"
            sentence = {"text": item["text"].strip(), "sources": list(item["sources"])}
            state, reason = provenance.verify(sentence, self.profile, self.offer_text,
                                              self.allow_offer)
            sentence.update(state=state, reason=reason)
            self.sentences[sid] = sentence
            ids.append(sid)
        return ids


def _check_indexes(indexes: list[int], available: int, what: str) -> None:
    if len(set(indexes)) != len(indexes) or any(i >= available for i in indexes):
        raise AIError("invalid", f"{what}: unknown or repeated index")


def _entries(builder: _Builder, section: str, picked: list[dict]) -> list[dict]:
    source = builder.profile.get(section) or []
    _check_indexes([p["index"] for p in picked], len(source), section)
    entries = []
    for pick in picked:
        entry = {f: source[pick["index"]].get(f, "") for f in ENTRY_FIELDS[section]}
        entry["sentences"] = builder.add(pick["highlights"])
        entries.append(entry)
    return entries


def _copied(profile: dict, section: str, fields: tuple[str, ...]) -> list[dict]:
    return [{f: entry.get(f, "") for f in fields} for entry in profile.get(section) or []]


def build_cv(profile: dict, answer: dict) -> dict:
    """CV content; raises ``AIError("invalid")`` for an index that is not in the profile."""
    builder = _Builder(profile, "", allow_offer=False)
    skills = profile.get("skills") or []
    _check_indexes(answer["skills"], len(skills), "skills")
    blocks = [
        {"type": "summary", "sentences": builder.add(answer["summary"])},
        {"type": "experience", "entries": _entries(builder, "experience", answer["experience"])},
        {"type": "projects", "entries": _entries(builder, "projects", answer["projects"])},
        {"type": "skills", "items": [skills[i] for i in answer["skills"]]},
        {"type": "education",
         "entries": _copied(profile, "education", COPIED_FIELDS["education"])},
        {"type": "languages", "entries": _copied(profile, "languages", COPIED_FIELDS["languages"])},
    ]
    basics = profile.get("basics") or {}
    return {
        "header": {f: basics.get(f, [] if f == "links" else "") for f in HEADER_FIELDS},
        "blocks": [b for b in blocks if b.get("sentences") or b.get("entries") or b.get("items")],
        "sentences": builder.sentences,
    }


def build_letter(profile: dict, answer: dict, lang: str, offer_text: str) -> dict:
    """Cover-letter content: greeting, closing and signature come from i18n/profile."""
    builder = _Builder(profile, offer_text, allow_offer=True)
    paragraphs = [builder.add(p) for p in answer["paragraphs"]]
    basics = profile.get("basics") or {}
    return {
        "greeting": translate(lang, "letter.greeting"),
        "blocks": [{"type": "paragraph", "sentences": ids} for ids in paragraphs if ids],
        "closing": translate(lang, "letter.closing"),
        "signature": basics.get("name", ""),
        "sentences": builder.sentences,
    }


def structure(profile: dict, kind: str) -> dict:
    """The profile facts the code copies into a document (to notice later changes)."""
    basics = profile.get("basics") or {}
    if kind != "cv":
        return {"name": basics.get("name", "")}
    sections = {**ENTRY_FIELDS, **COPIED_FIELDS}
    return {
        "basics": {f: basics.get(f, [] if f == "links" else "") for f in HEADER_FIELDS},
        **{name: _copied(profile, name, fields) for name, fields in sections.items()},
        "skills": list(profile.get("skills") or []),
    }
