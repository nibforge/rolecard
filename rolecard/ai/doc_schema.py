"""Strict schemas for the AI's tailored-document answers (CV and cover letter).

Every generated sentence comes with ``sources`` (profile paths, or ``offer`` in a
letter). The list may be empty: the server then marks the sentence unsourced instead of
rejecting the whole answer. Structural CV data is NOT here: the code copies it from the
profile; the AI only picks entries by index and writes sentences.
"""

from __future__ import annotations

SENTENCE_MAX = 400
SOURCE = {"type": "string", "minLength": 1, "maxLength": 80}

SENTENCE = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": SENTENCE_MAX},
        "sources": {"type": "array", "items": SOURCE, "maxItems": 8},
    },
    "required": ["text", "sources"],
}


def _sentences(limit: int) -> dict:
    return {"type": "array", "items": SENTENCE, "maxItems": limit}


_INDEX = {"type": "integer", "minimum": 0, "maximum": 59}


def _picked(limit: int) -> dict:
    return {
        "type": "array",
        "maxItems": limit,
        "items": {
            "type": "object",
            "properties": {"index": _INDEX, "highlights": _sentences(8)},
            "required": ["index", "highlights"],
        },
    }


CV_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": _sentences(4),
        "experience": _picked(15),
        "projects": _picked(8),
        "skills": {"type": "array", "items": _INDEX, "maxItems": 40},
    },
    "required": ["summary", "experience", "projects", "skills"],
}

LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "paragraphs": {"type": "array", "minItems": 1, "maxItems": 5, "items": _sentences(6)},
    },
    "required": ["paragraphs"],
}
