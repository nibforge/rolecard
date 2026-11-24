"""Job offers: create (with de-duplication), edit and delete. Manual ones come from the
form; ``services/search`` creates the ones from API sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rolecard.models import Job, JobEvent, utcnow
from rolecard.services.dedup import is_web_url, match_key, text_key, url_key

MIN_TEXT, MAX_TEXT = 80, 50_000
MAX_FIELD, MAX_URL = 300, 2000


@dataclass
class Duplicate:
    job: Job


def _clean(value: str | None) -> str:
    return (value or "").strip()


def validate_fields(text: str | None, url: str, title: str, company: str,
                    location: str = "") -> dict[str, str]:
    """Errors by field name (i18n keys). ``text=None`` skips the text (when editing)."""
    errors = {}
    if text is not None:
        if len(text) < MIN_TEXT:
            errors["text"] = "job.error.text_short"
        elif len(text) > MAX_TEXT:
            errors["text"] = "job.error.text_long"
    if url and (len(url) > MAX_URL or not is_web_url(url)):
        errors["url"] = "job.error.url"
    for name, value in (("title", title), ("company", company), ("location", location)):
        if len(value) > MAX_FIELD:
            errors[name] = "job.error.too_long"
    return errors


def find_duplicate(db: Session, ukey: str | None, tkey: str | None,
                   exclude_id: int | None = None, mkey: str | None = None) -> Job | None:
    """An existing offer with the same URL key or text key (or ``mkey``, only for offers
    from sources: two manual offers may share company and title)."""
    conditions = []
    if mkey:
        conditions.append(Job.match_key == mkey)
    if ukey:
        conditions.append(Job.url_key == ukey)
    if tkey:
        conditions.append(Job.text_key == tkey)
    if not conditions:
        return None
    query = select(Job).where(or_(*conditions))
    if exclude_id is not None:
        query = query.where(Job.id != exclude_id)
    return db.scalars(query.limit(1)).first()


def create_job(db: Session, *, text: str, url: str = "", title: str = "", company: str = "",
               now: datetime | None = None, location: str = "", source: str = "manual",
               external_id: str | None = None, search_id: int | None = None
               ) -> Job | Duplicate:
    """Store a new offer in state ``new``, or return the existing duplicate.

    The caller validates first with ``validate_fields``.
    """
    now = now or utcnow()
    text, url = text.strip(), _clean(url)
    ukey, tkey = url_key(url), text_key(text)
    existing = find_duplicate(db, ukey, tkey)
    if existing is not None:
        return Duplicate(existing)
    title, company, location = _clean(title), _clean(company), _clean(location)
    job = Job(text=text, text_key=tkey, url=url or None, url_key=ukey, title=title,
              company=company, location=location, status="new", source=source,
              external_id=external_id, search_id=search_id,
              match_key=match_key(company, title, location), created_at=now, updated_at=now)
    job.events.append(JobEvent(status="new", at=now))
    db.add(job)
    return _commit_or_duplicate(db, job, ukey, tkey)


def update_job(db: Session, job: Job, *, title: str, company: str, location: str,
               url: str, text: str | None = None) -> Job | Duplicate:
    """Edit the offer's fields; ``text`` replaces its text (e.g. the full description
    pasted over a source's short snippet) and ``None`` keeps it."""
    url = _clean(url)
    ukey = url_key(url)
    text = text.strip() if text is not None else None
    tkey = text_key(text) if text and text != job.text else None
    existing = find_duplicate(db, ukey, tkey, exclude_id=job.id)
    if existing is not None:
        return Duplicate(existing)
    job.title, job.company, job.location = _clean(title), _clean(company), _clean(location)
    job.url, job.url_key = url or None, ukey
    if tkey is not None:
        job.text, job.text_key = text, tkey
    job.match_key = match_key(job.company, job.title, job.location)
    return _commit_or_duplicate(db, job, ukey, tkey)


def _commit_or_duplicate(db: Session, job: Job, ukey: str | None,
                         tkey: str | None) -> Job | Duplicate:
    """Commit; if a concurrent request stored the same offer first (UNIQUE keys), roll
    back and return that one as the duplicate."""
    job_id = job.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = find_duplicate(db, ukey, tkey, exclude_id=job_id)
        if existing is None:
            raise
        return Duplicate(existing)
    return job


def delete_job(db: Session, job: Job) -> None:
    db.delete(job)
    db.commit()


def backfill_match_keys(db: Session) -> int:
    """Fill ``match_key`` only where it is empty (offers from before migration 0003).
    Run once at start-up; offers without company or title stay empty."""
    filled = 0
    for job in db.query(Job).filter(Job.match_key.is_(None)).all():
        job.match_key = match_key(job.company, job.title, job.location)
        filled += job.match_key is not None
    if filled:
        db.commit()
    return filled
