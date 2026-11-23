"""Local usage limits per source, kept in ``source_calls`` (one row per source).

A "run" is one search against one source (it may make several HTTP calls, e.g. two
pages); the API's limit is translated into runs per day and seconds between runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from rolecard.models import SourceCall


@dataclass(frozen=True)
class Limit:
    per_day: int | None = None
    min_interval: int = 0  # seconds between runs


class RateLimited(Exception):
    def __init__(self, retry_at: datetime):
        super().__init__(retry_at.isoformat())
        self.retry_at = retry_at


def _row(db: Session, source: str, now: datetime) -> SourceCall:
    row = db.get(SourceCall, source)
    if row is None:
        row = SourceCall(source=source, day=now.date().isoformat(), calls_today=0)
        db.add(row)
    if row.day != now.date().isoformat():
        row.day, row.calls_today = now.date().isoformat(), 0
    return row


def check(db: Session, source: str, limit: Limit, now: datetime) -> None:
    """Raise ``RateLimited`` (with when to retry) if another run would break the limit."""
    row = db.get(SourceCall, source)
    if row is None:
        return
    if row.last_call_at is not None and limit.min_interval:
        ready = row.last_call_at + timedelta(seconds=limit.min_interval)
        if now < ready:
            raise RateLimited(ready)
    if (limit.per_day is not None and row.day == now.date().isoformat()
            and row.calls_today >= limit.per_day):
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(),
                                    tzinfo=now.tzinfo)
        raise RateLimited(midnight)


def record(db: Session, source: str, endpoint: str, now: datetime) -> None:
    """Count one run. ``endpoint`` must be the URL WITHOUT its query (no keys)."""
    row = _row(db, source, now)
    row.endpoint = endpoint.split("?", 1)[0]
    row.calls_today += 1
    row.last_call_at = now
    db.commit()
