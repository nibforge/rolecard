"""What the home page lists besides the week's numbers: the work for today, the best
unsent offers and the funnel of the last weeks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from rolecard.models import Document, Job, JobEvent
from rolecard.services import provenance
from rolecard.services.stats import pending_follow_ups

UNSENT = ("new", "prepared")
FUNNEL = ("sent", "replied", "interview", "offer")
BEST_SHOWN = 5
FUNNEL_WEEKS = 4


@dataclass(frozen=True)
class Today:
    unscored: int
    documents: list[tuple[Document, int]]  # (document, sentences still to review)
    follow_ups: list[Job]

    @property
    def count(self) -> int:
        return (1 if self.unscored else 0) + len(self.documents) + len(self.follow_ups)


def _pending_sentences(doc: Document) -> int:
    return provenance.unresolved(doc.content) + provenance.pending_offer(doc.content)


def for_today(db: Session, today: date) -> Today:
    """Unscored new offers, documents with sentences to review (of jobs not discarded)
    and the follow-ups due today or earlier."""
    unscored = db.scalar(select(func.count(Job.id)).where(
        Job.status == "new", Job.score.is_(None))) or 0
    # A reviewed document has nothing pending: every change that adds a pending sentence
    # clears ``reviewed_at`` (services/documents.py). One query, the job loaded with it.
    docs = db.scalars(select(Document).join(Document.job).options(contains_eager(Document.job))
                      .where(Job.status != "discarded", Document.reviewed_at.is_(None))
                      .order_by(Document.updated_at.desc()))
    documents = [(d, n) for d in docs if (n := _pending_sentences(d))]
    return Today(unscored, documents, pending_follow_ups(db, today))


def best_unsent(db: Session, limit: int = BEST_SHOWN) -> list[Job]:
    """The highest scored offers not sent yet."""
    return list(db.scalars(select(Job).where(Job.status.in_(UNSENT), Job.score.is_not(None))
                           .order_by(Job.score.desc(), Job.id).limit(limit)))


def funnel(db: Session, now: datetime, weeks: int = FUNNEL_WEEKS) -> list[tuple[str, int]]:
    """Offers added in the last ``weeks`` and how many of all offers reached each stage
    in that time (one per offer and stage), in funnel order."""
    since = now - timedelta(weeks=weeks)
    added = db.scalar(select(func.count(Job.id)).where(Job.created_at >= since)) or 0
    reached = dict(db.execute(
        select(JobEvent.status, func.count(func.distinct(JobEvent.job_id)))
        .where(JobEvent.at >= since, JobEvent.status.in_(FUNNEL))
        .group_by(JobEvent.status)).all())
    return [("added", added), *((s, reached.get(s, 0)) for s in FUNNEL)]
