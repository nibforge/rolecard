"""The tracking board page and the next page of one of its columns (HTMX)."""

from __future__ import annotations

from flask import Blueprint, abort, make_response, render_template, request

from rolecard import get_db
from rolecard.models import STATUSES, Job
from rolecard.services.board import (
    PAGE_SIZE,
    BoardFilters,
    build_board,
    column_page,
    count_by_status,
)
from rolecard.views import local_now
from rolecard.views.nav import remember_offers_view

bp = Blueprint("board", __name__, url_prefix="/board")


@bp.get("")
def index():
    db = get_db()
    filters = BoardFilters.from_args(request.args)
    today = local_now().date()
    columns = build_board(db, filters, today)
    hidden = 0 if filters.show_discarded else count_by_status(
        db, filters, today, ["discarded"])["discarded"]
    html = render_template(
        "board.html",
        columns=columns,
        filters=filters,
        today=today,
        page_size=PAGE_SIZE,
        shown=sum(col.total for col in columns),
        hidden_discarded=hidden,
        has_jobs=db.query(Job.id).first() is not None,
    )
    return remember_offers_view(make_response(html), "board")


@bp.get("/column/<status>")
def column(status: str) -> str:
    """Cards of page ``page`` of one column plus the button for the page after."""
    if status not in STATUSES:
        abort(404)
    raw = request.args.get("page", "")
    page = int(raw) if raw.isascii() and raw.isdigit() and 0 < int(raw) <= 10_000 else 1
    filters = BoardFilters.from_args(request.args)
    today = local_now().date()
    col = column_page(get_db(), filters, today, status, page)
    return render_template("_board_column.html", col=col, filters=filters, today=today,
                           page_size=PAGE_SIZE)
