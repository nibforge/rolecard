"""The master profile: its strict schema, normalisation and the form <-> data mapping.

The same schema validates the AI extraction (closed objects, so unknown fields are
rejected) and what the user saves. Every value is plain text; nothing is a link.
Fields inside the sections are optional and may be null (a CV often lacks an e-mail or
a date), and dates may come as a bare year number; ``normalize`` turns both into text.
"""

from __future__ import annotations

import re
from copy import deepcopy

from rolecard.ai.schema import SchemaError, validate

SHORT, LONG, ITEMS = 300, 3000, 60

BASICS = ("name", "headline", "email", "phone", "location", "links", "summary")
# Repeatable sections: field names in form order; LIST_FIELDS hold one item per line.
SECTIONS: dict[str, tuple[str, ...]] = {
    "experience": ("role", "company", "start", "end", "location", "highlights"),
    "projects": ("name", "description", "highlights"),
    "education": ("degree", "institution", "start", "end"),
    "languages": ("language", "level"),
}
LIST_FIELDS = frozenset({"highlights", "links"})
LONG_FIELDS = frozenset({"summary", "description"})
DATE_FIELDS = frozenset({"start", "end"})


def _text(limit: int = SHORT) -> dict:
    return {"type": "string", "maxLength": limit, "nullable": True}


def _list(limit: int = 500) -> dict:
    return {"type": "array", "items": _text(limit), "maxItems": ITEMS, "nullable": True}


def _field_schema(name: str) -> dict:
    if name in LIST_FIELDS:
        return _list()
    if name in DATE_FIELDS:
        return {**_text(), "type": ["string", "integer"]}
    return _text(LONG if name in LONG_FIELDS else SHORT)


def _entry_schema(fields: tuple[str, ...]) -> dict:
    return {"type": "object", "properties": {f: _field_schema(f) for f in fields}}


PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "basics": _entry_schema(BASICS),
        **{name: {"type": "array", "items": _entry_schema(fields), "maxItems": ITEMS}
           for name, fields in SECTIONS.items()},
        "skills": {**_list(100), "nullable": False},
    },
    "required": ["basics", *SECTIONS, "skills"],
}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FORM_KEY = re.compile(r"^(experience|projects|education|languages)-(\w{1,40})-(\w+)$")


def empty_profile() -> dict:
    return {"basics": {f: _blank(f) for f in BASICS}, **{s: [] for s in SECTIONS}, "skills": []}


def _blank(field: str):
    return [] if field in LIST_FIELDS else ""


def _clean(field: str, value):
    if value is None:
        return _blank(field)
    if field in LIST_FIELDS:
        return [line.strip() for line in value if line and line.strip()]
    return str(value).strip()


def normalize(data: dict) -> dict:
    """Validate ``data`` strictly, then fill missing fields and drop empty entries."""
    validate(data, PROFILE_SCHEMA)
    out = empty_profile()
    for field, value in data["basics"].items():
        out["basics"][field] = _clean(field, value)
    for section, fields in SECTIONS.items():
        for entry in data[section]:
            clean = {f: _clean(f, entry.get(f, _blank(f))) for f in fields}
            if any(clean.values()):
                out[section].append(clean)
    seen = set()
    for skill in data["skills"]:
        skill = (skill or "").strip()
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            out["skills"].append(skill)
    return out


def _lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def from_form(form) -> tuple[dict, dict]:
    """Build a profile from the submitted form. Returns (profile, errors by field id)."""
    data = deepcopy(empty_profile())
    for field in BASICS:
        raw = form.get(f"basics-{field}", "")
        data["basics"][field] = _lines(raw) if field in LIST_FIELDS else raw
    data["skills"] = [s for s in re.split(r"[,\n]", form.get("skills", "")) if s.strip()]
    entries: dict[str, dict[str, dict]] = {s: {} for s in SECTIONS}
    for key in form:
        match = _FORM_KEY.match(key)
        if not match or match.group(3) not in SECTIONS[match.group(1)]:
            continue
        section, entry_id, field = match.groups()
        raw = form.get(key, "")
        entries[section].setdefault(entry_id, {})[field] = (
            _lines(raw) if field in LIST_FIELDS else raw
        )
    for section in SECTIONS:
        data[section] = list(entries[section].values())
    errors: dict[str, str] = {}
    try:
        data = normalize(data)
    except SchemaError:
        errors["form"] = "profile.error.too_long"
        return data, errors
    if not data["basics"]["name"]:
        errors["basics-name"] = "profile.error.name_required"
    email = data["basics"]["email"]
    if email and not _EMAIL.match(email):
        errors["basics-email"] = "profile.error.email"
    return data, errors
