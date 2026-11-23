"""The list view of offers: the board's filters plus status, column order and pages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from rolecard.models import STATUSES, Job
from rolecard.services.board import BY_SCORE, BoardFilters, select_page

PER_PAGE = (25, 50, 100)
DEFAULT_PER_PAGE = 50
SORTS = {
    "title": Job.title,
    "company": Job.company,
    "score": Job.score,
    "source": Job.source,
    "created": Job.created_at,
    "follow_up": Job.follow_up_on,
}
DEFAULT_DIR = {"score": "desc", "created": "desc"}  # the rest start ascending
MAX_PAGE = 100_000


def _int(raw, default: int) -> int:
    raw = (raw or "").strip()
    return int(raw) if raw.isascii() and raw.isdigit() and len(raw) < 7 else default


@dataclass(frozen=True)
class ListParams:
    status: str = ""
    sort: str = "score"
    dir: str = "desc"
    per_page: int = DEFAULT_PER_PAGE
    page: int = 1

    @classmethod
    def from_args(cls, args) -> ListParams:
        """Read status, order and page from a query string; invalid values fall back."""
        sort = args.get("sort") if args.get("sort") in SORTS else "score"
        direction = args.get("dir")
        if direction not in ("asc", "desc"):
            direction = DEFAULT_DIR.get(sort, "asc")
        per_page = _int(args.get("per_page"), DEFAULT_PER_PAGE)
        return cls(
            status=args.get("status") if args.get("status") in STATUSES else "",
            sort=sort,
            dir=direction,
            per_page=per_page if per_page in PER_PAGE else DEFAULT_PER_PAGE,
            page=min(max(_int(args.get("page"), 1), 1), MAX_PAGE),
        )

    def to_args(self, **changes) -> dict[str, str]:
        """Query string for these params (defaults left out), with ``changes`` applied."""
        values = {"status": self.status, "sort": self.sort, "dir": self.dir,
                  "per_page": self.per_page, "page": self.page, **changes}
        defaults = {"status": "", "sort": "score", "per_page": DEFAULT_PER_PAGE, "page": 1,
                    "dir": DEFAULT_DIR.get(values["sort"], "asc")}
        return {k: str(v) for k, v in values.items() if v != defaults[k]}

    def sort_link(self, column: str) -> dict[str, str]:
        """Args to sort by ``column``: flips the direction if it is already the sort."""
        if column == self.sort:
            return self.to_args(dir="asc" if self.dir == "desc" else "desc", page=1)
        return self.to_args(sort=column, dir=DEFAULT_DIR.get(column, "asc"), page=1)


@dataclass(frozen=True)
class ListPage:
    jobs: list[Job]
    total: int
    params: ListParams

    @property
    def pages(self) -> int:
        return max((self.total + self.params.per_page - 1) // self.params.per_page, 1)

    @property
    def start(self) -> int:
        return (self.params.page - 1) * self.params.per_page + 1 if self.jobs else 0

    @property
    def end(self) -> int:
        return self.start + len(self.jobs) - 1 if self.jobs else 0


def _order(params: ListParams):
    if params.sort == "score" and params.dir == "desc":
        return BY_SCORE
    column = SORTS[params.sort]
    ordered = column.desc() if params.dir == "desc" else column.asc()
    return (column.is_(None), ordered, Job.id.desc())  # empty values always last


def list_page(db: Session, filters: BoardFilters, params: ListParams, today: date) -> ListPage:
    statuses = [params.status] if params.status else filters.statuses()
    offset = (params.page - 1) * params.per_page
    jobs, total = select_page(db, filters, today, statuses, order=_order(params),
                              offset=offset, limit=params.per_page)
    last = max((total + params.per_page - 1) // params.per_page, 1)
    if params.page > last:  # an old link past the end: show the last page instead
        return list_page(db, filters, replace(params, page=last), today)
    return ListPage(jobs, total, params)
