"""Score an offer against the master profile with the AI (one call per offer)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from rolecard.ai import AIProvider
from rolecard.ai.prompts import score_prompt
from rolecard.models import Job, utcnow

_SHORT = {"type": "string", "maxLength": 200}
_REQS = {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 200},
         "maxItems": 15}

SCORE_BATCH = 5  # offers scored per click in bulk (each one is an AI call)

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string", "minLength": 1, "maxLength": 500},
        "met": _REQS,
        "missing": _REQS,
        "language": {"type": "string", "maxLength": 8},
        "title": _SHORT,
        "company": _SHORT,
        "location": _SHORT,
    },
    "required": ["score", "summary", "met", "missing", "language", "title", "company",
                 "location"],
}


def score_job(db: Session, job: Job, profile: dict, provider: AIProvider, ui_lang: str,
              now: datetime | None = None) -> Job:
    """Ask the AI, validate the answer strictly and store it (raises ``AIError``;
    nothing is changed when it does)."""
    answer = provider.complete_json(score_prompt(profile, job.text, ui_lang), SCORE_SCHEMA)
    job.score = answer["score"]
    job.score_summary = answer["summary"].strip()
    job.score_met = [item.strip() for item in answer["met"]]
    job.score_missing = [item.strip() for item in answer["missing"]]
    job.language = answer["language"].strip().lower()
    for field in ("title", "company", "location"):
        if not getattr(job, field) and answer[field].strip():
            setattr(job, field, answer[field].strip())
    job.scored_at = now or utcnow()
    db.commit()
    return job
