"""Offers filtered in SQL (free text in Python afterwards), counted per status and paged:
the board's columns and the list view share these queries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from rolecard.config import SOURCE_NAMES
from rolecard.models import STATUSES, Job

MAX_QUERY = 200
SOURCES = ("manual", *SOURCE_NAMES)
PAGE_SIZE = 20  # cards per board column and per "show more"


@dataclass(frozen=True)
class BoardFilters:
    query: str = ""
    min_score: int | None = None
    overdue_only: bool = False
    show_discarded: bool = False
    source: str = ""
    unscored_only: bool = False

    @property
    def active(self) -> bool:
        return bool(self.query or self.min_score is not None or self.overdue_only
                    or self.source or self.unscored_only)

    @classmethod
    def from_args(cls, args) -> BoardFilters:
        """Read the filters from a query string; invalid values are ignored."""
        raw_min = (args.get("min") or "").strip()
        valid = raw_min.isascii() and raw_min.isdigit() and int(raw_min) <= 100
        min_score = int(raw_min) if valid else None
        return cls(
            query=(args.get("q") or "").strip()[:MAX_QUERY],
            min_score=min_score,
            overdue_only=args.get("overdue") == "1",
            show_discarded=args.get("discarded") == "1",
            source=args.get("source") if args.get("source") in SOURCES else "",
            unscored_only=args.get("unscored") == "1",
        )

    def to_args(self) -> dict[str, str]:
        """The query string that reproduces these filters (for links and HTMX)."""
        args = {"q": self.query, "min": "" if self.min_score is None else str(self.min_score),
                "source": self.source, "unscored": "1" if self.unscored_only else "",
                "overdue": "1" if self.overdue_only else "",
                "discarded": "1" if self.show_discarded else ""}
        return {k: v for k, v in args.items() if v}

    def statuses(self) -> list[str]:
        return [s for s in STATUSES if s != "discarded" or self.show_discarded]


@dataclass(frozen=True)
class Column:
    status: str
    jobs: list[Job]
    total: int
    page: int = 1

    @property
    def remaining(self) -> int:
        return max(self.total - (self.page - 1) * PAGE_SIZE - len(self.jobs), 0)


# Highest score first, unscored last; newest first among equals; id keeps pages stable.
BY_SCORE = (Job.score.is_(None), Job.score.desc(), Job.created_at.desc(), Job.id.desc())


def filtered(filters: BoardFilters, today: date, statuses) -> Select:
    """Every filter but the free text, in SQL."""
    query = select(Job).where(Job.status.in_(list(statuses)))
    if filters.min_score is not None:
        query = query.where(Job.score >= filters.min_score)
    if filters.source:
        query = query.where(Job.source == filters.source)
    if filters.unscored_only:
        query = query.where(Job.score.is_(None))
    if filters.overdue_only:
        query = query.where(Job.follow_up_on < today)
    return query


def _text_matches(db: Session, base: Select, needle: str, order) -> list[tuple[int, str]]:
    """``(id, status)`` of the rows the SQL filters kept whose text contains ``needle``."""
    needle = needle.casefold()
    rows = db.execute(base.with_only_columns(
        Job.id, Job.status, Job.title, Job.company, Job.location, Job.text).order_by(*order))
    return [(row.id, row.status) for row in rows
            if needle in " ".join(row[2:]).casefold()]


def _load(db: Session, ids: list[int]) -> list[Job]:
    by_id = {job.id: job for job in db.scalars(select(Job).where(Job.id.in_(ids)))}
    return [by_id[i] for i in ids]


def select_page(db: Session, filters: BoardFilters, today: date, statuses, *,
                order=BY_SCORE, offset: int = 0, limit: int = PAGE_SIZE) -> tuple[list[Job], int]:
    """One page of matching offers and how many match in all."""
    base = filtered(filters, today, statuses)
    if filters.query:
        ids = [i for i, _ in _text_matches(db, base, filters.query, order)]
        return _load(db, ids[offset:offset + limit]), len(ids)
    total = db.scalar(base.with_only_columns(func.count(Job.id)))
    jobs = db.scalars(base.order_by(*order).offset(offset).limit(limit)).all()
    return list(jobs), total or 0


def count_by_status(db: Session, filters: BoardFilters, today: date,
                    statuses=STATUSES) -> dict[str, int]:
    base = filtered(filters, today, statuses)
    if filters.query:
        counts = Counter(s for _, s in _text_matches(db, base, filters.query, BY_SCORE))
    else:
        counts = dict(db.execute(
            base.with_only_columns(Job.status, func.count(Job.id)).group_by(Job.status)).all())
    return {s: counts.get(s, 0) for s in statuses}


def build_board(db: Session, filters: BoardFilters, today: date) -> list[Column]:
    """The first page of each column in workflow order; ``discarded`` only when asked."""
    statuses = filters.statuses()
    if filters.query:
        matches = _text_matches(db, filtered(filters, today, statuses), filters.query, BY_SCORE)
        ids = {s: [i for i, st in matches if st == s] for s in statuses}
        return [Column(s, _load(db, ids[s][:PAGE_SIZE]), len(ids[s])) for s in statuses]
    counts = count_by_status(db, filters, today, statuses)
    return [Column(s, column_page(db, filters, today, s).jobs if counts[s] else [], counts[s])
            for s in statuses]


def column_page(db: Session, filters: BoardFilters, today: date, status: str,
                page: int = 1) -> Column:
    jobs, total = select_page(db, filters, today, [status], offset=(page - 1) * PAGE_SIZE)
    return Column(status, jobs, total, page)
