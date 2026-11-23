"""The board in pages: counts in SQL, 20 cards per column, the next page on demand."""

from datetime import UTC, date, datetime, timedelta

import pytest
from werkzeug.datastructures import MultiDict

from rolecard import get_db
from rolecard.models import Job
from rolecard.services.board import (
    PAGE_SIZE,
    BoardFilters,
    build_board,
    column_page,
    count_by_status,
)

TODAY = date(2026, 11, 20)
START = datetime(2026, 11, 1, tzinfo=UTC)


def bulk(db, count, *, status="new", start=0, title="Job", **extra):
    db.add_all(Job(text=f"{title} text {n}", text_key=f"k-{status}-{start + n}",
                   title=f"{title} {start + n}", status=status, score=(start + n) % 101,
                   created_at=START + timedelta(minutes=start + n), **extra)
               for n in range(count))
    db.commit()


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def test_thousand_offers_give_twenty_cards_and_the_full_count(db):
    bulk(db, 990)
    bulk(db, 10, status="sent", start=990)
    columns = {c.status: c for c in build_board(db, BoardFilters(), TODAY)}
    assert columns["new"].total == 990 and len(columns["new"].jobs) == PAGE_SIZE
    assert columns["new"].remaining == 970
    assert columns["sent"].total == 10 and columns["sent"].remaining == 0
    assert columns["offer"].total == 0 and columns["offer"].jobs == []
    scores = [job.score for job in columns["new"].jobs]
    assert scores == sorted(scores, reverse=True)


def test_pages_do_not_repeat_and_cover_the_column(db):
    bulk(db, 45)
    seen = []
    for page in (1, 2, 3):
        col = column_page(db, BoardFilters(), TODAY, "new", page)
        seen += [job.id for job in col.jobs]
    assert len(seen) == 45 == len(set(seen))
    assert col.remaining == 0 and len(col.jobs) == 5


def test_free_text_is_applied_after_the_sql_filters(db):
    bulk(db, 30, title="Python")
    bulk(db, 30, title="Java", start=30)
    filters = BoardFilters(query="python", min_score=10)
    counts = count_by_status(db, filters, TODAY)
    assert counts["new"] == 20  # Python 0..29 with score >= 10
    col = column_page(db, filters, TODAY, "new", 2)
    assert col.total == 20 and col.jobs == [] and col.remaining == 0
    board = {c.status: c for c in build_board(db, filters, TODAY)}
    assert board["new"].total == 20 and all("Python" in j.title for j in board["new"].jobs)


def test_counts_include_discarded_even_when_hidden(db):
    bulk(db, 3, status="discarded")
    assert count_by_status(db, BoardFilters(), TODAY)["discarded"] == 3
    assert "discarded" not in [c.status for c in build_board(db, BoardFilters(), TODAY)]


def test_overdue_filter_in_sql(db):
    bulk(db, 2, status="sent", follow_up_on=TODAY - timedelta(days=1))
    bulk(db, 2, status="sent", start=2, follow_up_on=TODAY)
    assert count_by_status(db, BoardFilters(overdue_only=True), TODAY)["sent"] == 2


def test_filters_round_trip_through_the_query_string():
    filters = BoardFilters("go", 70, True, True, "remotive", False)
    assert BoardFilters.from_args(MultiDict(filters.to_args())) == filters
    assert BoardFilters().to_args() == {}


def test_board_page_shows_twenty_cards_and_a_button_for_the_rest(client, db):
    bulk(db, 25)
    bulk(db, 2, status="discarded", start=25)
    html = client.get("/board?min=", headers={"Accept-Language": "es-ES"}).get_data(
        as_text=True)
    assert html.count('class="rc-card"') == PAGE_SIZE
    assert "Ver 5 más · quedan 5" in html
    assert 'hx-get="/board/column/new?page=2"' in html and 'hx-swap="outerHTML"' in html
    assert 'href="/jobs?status=new"' in html  # without JS: the list of that status
    assert "Descartadas: 2, ocultas." in html and '<span class="rc-count">25</span>' in html


def test_column_route_returns_the_next_page_with_the_filters(client, db):
    bulk(db, 45, title="Python")
    bulk(db, 5, title="Java", start=45)
    page = client.get("/board/column/new?page=2&q=python", headers={"Accept-Language": "en"})
    html = page.get_data(as_text=True)
    assert page.status_code == 200 and "<html" not in html
    assert html.count('class="rc-card"') == PAGE_SIZE and "Java" not in html
    assert "/board/column/new?page=3&amp;q=python" in html and "5 left" in html
    last = client.get("/board/column/new?page=3&q=python").get_data(as_text=True)
    assert last.count('class="rc-card"') == 5 and "rc-col__more" not in last


@pytest.mark.parametrize("url", ["/board/column/nope", "/board/column/<b>"])
def test_column_route_rejects_unknown_status(client, url):
    assert client.get(url).status_code == 404


def test_column_route_ignores_a_bad_page(client, db):
    bulk(db, 3)
    for raw in ("abc", "0", "-1", "99999999"):
        html = client.get(f"/board/column/new?page={raw}").get_data(as_text=True)
        assert html.count('class="rc-card"') == 3
