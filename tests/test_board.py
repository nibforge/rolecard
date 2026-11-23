from datetime import UTC, date, datetime, timedelta

import pytest
from werkzeug.datastructures import MultiDict

from rolecard import get_db
from rolecard.models import Job
from rolecard.services.board import BoardFilters, build_board

TODAY = date(2026, 11, 20)


def add_job(db, n, *, status="new", score=None, follow_up=None, title=None, text="", created=0):
    job = Job(
        text=text or f"Offer number {n}", text_key=f"key-{n}", title=title or f"Job {n}",
        company=f"Company {n}", status=status, score=score, follow_up_on=follow_up,
        created_at=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(hours=created),
    )
    db.add(job)
    db.commit()
    return job


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def titles(columns, status):
    return [job.title for col in columns if col.status == status for job in col.jobs]


def test_columns_in_workflow_order_without_discarded(db):
    columns = build_board(db, BoardFilters(), TODAY)
    assert [c.status for c in columns] == [
        "new", "prepared", "sent", "replied", "interview", "offer"]
    shown = build_board(db, BoardFilters(show_discarded=True), TODAY)
    assert shown[-1].status == "discarded"


def test_sorted_by_score_unscored_last_newest_first_on_ties(db):
    add_job(db, 1, score=60, created=1)
    add_job(db, 2, score=None, created=5)
    add_job(db, 3, score=90, created=2)
    add_job(db, 4, score=60, created=3)
    assert titles(build_board(db, BoardFilters(), TODAY), "new") == [
        "Job 3", "Job 4", "Job 1", "Job 2"]


def test_text_filter_is_case_insensitive_and_searches_offer_text(db):
    add_job(db, 1, text="We run Kubernetes in production")
    add_job(db, 2, title="Kubernetes admin")
    add_job(db, 3)
    columns = build_board(db, BoardFilters(query="KUBERNETES"), TODAY)
    assert sorted(titles(columns, "new")) == ["Job 1", "Kubernetes admin"]


def test_min_score_excludes_lower_and_unscored(db):
    add_job(db, 1, score=85)
    add_job(db, 2, score=69)
    add_job(db, 3)
    assert titles(build_board(db, BoardFilters(min_score=70), TODAY), "new") == ["Job 1"]


def test_overdue_only_keeps_past_follow_ups(db):
    add_job(db, 1, status="sent", follow_up=TODAY - timedelta(days=1))
    add_job(db, 2, status="sent", follow_up=TODAY)
    add_job(db, 3, status="sent")
    assert titles(build_board(db, BoardFilters(overdue_only=True), TODAY), "sent") == ["Job 1"]


def test_discarded_hidden_unless_asked(db):
    add_job(db, 1, status="discarded")
    assert "Job 1" not in titles(build_board(db, BoardFilters(), TODAY), "discarded")
    assert titles(build_board(db, BoardFilters(show_discarded=True), TODAY), "discarded") == [
        "Job 1"]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, BoardFilters()),
        ({"q": "  python ", "min": "70", "overdue": "1", "discarded": "1"},
         BoardFilters("python", 70, True, True)),
        ({"min": "abc"}, BoardFilters()),
        ({"min": "101"}, BoardFilters()),
        ({"min": "-5"}, BoardFilters()),
        ({"q": "x" * 500}, BoardFilters(query="x" * 200)),
    ],
)
def test_filters_from_query_string(args, expected):
    assert BoardFilters.from_args(MultiDict(args)) == expected


def test_board_page_shows_cards_and_labels(app, client):
    app.config["CLOCK"] = lambda: datetime(2026, 11, 20, 12, tzinfo=UTC)
    with app.app_context():
        db = get_db()
        add_job(db, 1, status="sent", score=86, follow_up=date(2026, 11, 17),
                title="<b>Backend</b>")
        add_job(db, 2, status="replied", follow_up=TODAY)
    html = client.get("/board", headers={"Accept-Language": "en"}).get_data(as_text=True)
    assert "&lt;b&gt;Backend&lt;/b&gt;" in html and "<b>Backend</b>" not in html
    assert "Overdue: 17 Nov" in html
    assert "Today" in html
    with app.app_context():
        job_id = get_db().query(Job.id).filter(Job.status == "sent").scalar()
    assert f'class="rc-card__title" href="/jobs/{job_id}"' in html
    assert 'name="status"' not in html  # the status changes in the detail or in bulk
    assert "None yet." in html


def test_board_without_jobs_invites_to_add_one(client):
    html = client.get("/board", headers={"Accept-Language": "en"}).get_data(as_text=True)
    assert "Add your first offer" in html
    assert 'class="rc-board"' not in html


def test_board_no_match_offers_to_clear_filters(app, client):
    with app.app_context():
        add_job(get_db(), 1)
    html = client.get("/board?q=kubernetes", headers={"Accept-Language": "en"}).get_data(
        as_text=True)
    assert "No offer matches “kubernetes”" in html
    assert "Clear filters" in html


def test_status_change_from_the_detail(app, client, csrf):
    with app.app_context():
        job_id = add_job(get_db(), 1).id
    for status in ("prepared", "sent"):
        page = client.post(f"/jobs/{job_id}/status", data={"csrf_token": csrf, "status": status})
        assert page.status_code == 302 and page.headers["Location"].endswith(f"/jobs/{job_id}")
    with app.app_context():
        job = get_db().get(Job, job_id)
        assert job.status == "sent"
        assert [e.status for e in job.events] == ["prepared", "sent"]


def test_source_and_unscored_filters(db):
    add_job(db, 1, score=80)
    remote = add_job(db, 2)
    remote.source = "remotive"
    db.commit()
    by_source = build_board(db, BoardFilters.from_args(MultiDict({"source": "remotive"})), TODAY)
    assert titles(by_source, "new") == ["Job 2"]
    manual = build_board(db, BoardFilters.from_args(MultiDict({"source": "manual"})), TODAY)
    assert titles(manual, "new") == ["Job 1"]
    unscored = BoardFilters.from_args(MultiDict({"unscored": "1"}))
    assert unscored.active and titles(build_board(db, unscored, TODAY), "new") == ["Job 2"]
    assert BoardFilters.from_args(MultiDict({"source": "<x>"})).source == ""


def test_card_credits_the_source_and_links_the_original(client, db):
    job = add_job(db, 1)
    job.source, job.url = "arbeitnow", "https://www.arbeitnow.com/jobs/x-1"
    add_job(db, 2)
    db.commit()
    page = client.get("/board?source=arbeitnow", headers={"Accept-Language": "es-ES"})
    html = page.get_data(as_text=True)
    assert 'vía <a href="https://www.arbeitnow.com"' in html
    assert 'href="https://www.arbeitnow.com/jobs/x-1" target="_blank"' in html
    assert "Oferta original" in html and "Job 2" not in html
    assert '<option value="arbeitnow" selected>Arbeitnow</option>' in html
