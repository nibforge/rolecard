"""Numbers for the dashboard: this week (Monday to now, local time) and follow-ups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rolecard.models import Job, JobEvent


@dataclass(frozen=True)
class WeekNumbers:
    since: date
    added: int
    sent: int
    interviews: int
    overdue: int


def week_start(now: datetime) -> datetime:
    """Local Monday 00:00 of the week containing ``now`` (an aware local datetime)."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=now.weekday())


def _jobs_reaching(db: Session, status: str, since: datetime) -> int:
    query = select(func.count(func.distinct(JobEvent.job_id))).where(
        JobEvent.status == status, JobEvent.at >= since
    )
    return db.scalar(query) or 0


def week_numbers(db: Session, now: datetime) -> WeekNumbers:
    if now.tzinfo is None:
        raise ValueError("naive datetime; pass an aware local datetime")
    since = week_start(now)
    added = db.scalar(select(func.count(Job.id)).where(Job.created_at >= since)) or 0
    overdue = db.scalar(
        select(func.count(Job.id)).where(
            Job.follow_up_on < now.date(), Job.status != "discarded"
        )
    ) or 0
    return WeekNumbers(
        since=since.date(),
        added=added,
        sent=_jobs_reaching(db, "sent", since),
        interviews=_jobs_reaching(db, "interview", since),
        overdue=overdue,
    )


def pending_follow_ups(db: Session, today: date) -> list[Job]:
    """Follow-ups due today or earlier (not discarded), oldest first."""
    query = (
        select(Job)
        .where(Job.follow_up_on <= today, Job.status != "discarded")
        .order_by(Job.follow_up_on, Job.score.desc().nulls_last(), Job.id)
    )
    return list(db.scalars(query))
