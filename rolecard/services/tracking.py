"""Application status, its event history, notes and the follow-up date."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from rolecard.models import STATUSES, Job, JobEvent, utcnow

MAX_NOTES = 10_000


class TrackingError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def set_status(db: Session, job: Job, status: str, now: datetime | None = None) -> bool:
    """Move ``job`` to ``status`` and log the event. Any status can be chosen (the user
    may correct a mistake); ``discarded`` is reachable from all. Returns True if changed."""
    if status not in STATUSES:
        raise TrackingError("tracking.error.status")
    if status == job.status:
        return False
    now = now or utcnow()
    job.status = status
    job.events.append(JobEvent(status=status, at=now))
    job.updated_at = now
    db.commit()
    return True


def parse_follow_up(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise TrackingError("tracking.error.date") from exc


def set_tracking(db: Session, job: Job, *, notes: str, follow_up_on: date | None) -> None:
    if len(notes) > MAX_NOTES:
        raise TrackingError("tracking.error.notes")
    job.notes = notes.strip()
    job.follow_up_on = follow_up_on
    db.commit()
