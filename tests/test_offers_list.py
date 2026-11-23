"""The list view GET /jobs: filters, column order, server pages and the remembered view."""

from datetime import UTC, date, datetime, timedelta

import pytest
from werkzeug.datastructures import MultiDict

from rolecard import get_db
from rolecard.models import Job
from rolecard.services.board import BoardFilters
from rolecard.services.offers_list import ListParams, list_page

TODAY = date(2026, 11, 20)
EN = {"Accept-Language": "en"}


def add(db, n, **fields):
    values = {"title": f"Job {n:03}", "company": f"Co {n:03}", "status": "new",
              "created_at": datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=n), **fields}
    db.add(Job(text=f"text {n}", text_key=f"k{n}", **values))


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def page(db, args=None, filters=None):
    params = ListParams.from_args(MultiDict(args or {}))
    return list_page(db, filters or BoardFilters(), params, TODAY)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, ListParams()),
        ({"sort": "title"}, ListParams(sort="title", dir="asc")),
        ({"sort": "created", "dir": "asc", "per_page": "25", "page": "3", "status": "sent"},
         ListParams("sent", "created", "asc", 25, 3)),
        ({"sort": "text; drop", "dir": "sideways"}, ListParams()),
        ({"per_page": "1000"}, ListParams()),
        ({"per_page": "-25", "page": "0"}, ListParams()),
        ({"page": "abc", "status": "<b>"}, ListParams()),
        ({"page": "99999999999"}, ListParams()),
    ],
)
def test_params_from_query_string(args, expected):
    assert ListParams.from_args(MultiDict(args)) == expected


def test_to_args_leaves_defaults_out_and_sort_link_flips():
    assert ListParams().to_args() == {}
    assert ListParams().sort_link("score") == {"dir": "asc"}
    assert ListParams(page=4).sort_link("title") == {"sort": "title"}
    assert ListParams(sort="title", dir="asc").sort_link("title") == {"sort": "title",
                                                                      "dir": "desc"}


def test_pages_of_fifty_by_default_with_range(db):
    for n in range(120):
        add(db, n, score=n % 100)
    db.commit()
    first, last = page(db), page(db, {"page": "3"})
    assert len(first.jobs) == 50 and first.total == 120 and first.pages == 3
    assert (first.start, first.end) == (1, 50) and (last.start, last.end) == (101, 120)
    assert len(page(db, {"per_page": "100"}).jobs) == 100
    past = page(db, {"page": "999"})  # an old link past the end
    assert past.params.page == 3 and (past.start, past.end) == (101, 120)


def test_order_by_column_with_empty_values_last(db):
    add(db, 1, score=40, follow_up_on=TODAY)
    add(db, 2, score=None)
    add(db, 3, score=90, follow_up_on=TODAY - timedelta(days=3))
    db.commit()
    titles = lambda result: [j.title for j in result.jobs]  # noqa: E731
    assert titles(page(db)) == ["Job 003", "Job 001", "Job 002"]
    assert titles(page(db, {"sort": "score", "dir": "asc"})) == ["Job 001", "Job 003", "Job 002"]
    assert titles(page(db, {"sort": "title", "dir": "desc"})) == ["Job 003", "Job 002", "Job 001"]
    assert titles(page(db, {"sort": "follow_up"}))[:2] == ["Job 003", "Job 001"]
    assert titles(page(db, {"sort": "follow_up", "dir": "desc"}))[-1] == "Job 002"


def test_status_and_board_filters_combine(db):
    add(db, 1, status="sent", score=80)
    add(db, 2, status="sent", score=20)
    add(db, 3, status="discarded", score=90)
    add(db, 4, score=85)
    db.commit()
    assert [j.title for j in page(db, {"status": "sent"}, BoardFilters(min_score=50)).jobs] == [
        "Job 001"]
    assert "Job 003" not in [j.title for j in page(db).jobs]
    assert page(db, {"status": "discarded"}).total == 1  # asked for explicitly
    assert page(db, filters=BoardFilters(show_discarded=True)).total == 4


def test_list_page_renders_rows_sort_links_and_pager(client, db):
    for n in range(30):
        add(db, n, score=n)
    db.commit()
    response = client.get("/jobs?per_page=25&q=job", headers=EN)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert html.count('name="ids"') == 25 and "1–25 of 30" in html and "Page 1 of 2" in html
    assert 'hx-push-url="true"' in html and 'hx-select="#offers"' in html
    assert 'href="/jobs?q=job&amp;per_page=25&amp;page=2"' in html
    assert 'aria-sort="descending"' in html
    assert 'href="/jobs?q=job&amp;sort=title&amp;per_page=25"' in html
    assert 'href="/board?q=job"' in html  # the switch keeps the filters
    assert response.headers["Set-Cookie"].startswith("offers_view=list")


def test_list_escapes_titles_and_handles_no_match(client, db):
    add(db, 1, title="<script>x</script>")
    db.commit()
    html = client.get("/jobs", headers=EN).get_data(as_text=True)
    assert "&lt;script&gt;x&lt;/script&gt;" in html and "<script>x</script>" not in html
    empty = client.get("/jobs?q=nothing-like-this", headers=EN).get_data(as_text=True)
    assert "No offer matches “nothing-like-this”" in empty and 'name="ids"' not in empty


def test_offers_menu_opens_the_last_view_used(client, db):
    add(db, 1)
    db.commit()
    client.get("/jobs")
    assert 'href="/jobs"' in client.get("/").get_data(as_text=True)
    client.get("/board")
    home = client.get("/").get_data(as_text=True)
    assert 'class="rc-nav" href="/board"' in home


def test_list_without_offers_invites_to_add_one(client):
    html = client.get("/jobs", headers=EN).get_data(as_text=True)
    assert "Add your first offer" in html and "rc-table" not in html
