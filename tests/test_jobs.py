from datetime import UTC, datetime

import pytest

from rolecard import get_db
from rolecard.models import Job
from rolecard.services.jobs import (
    Duplicate,
    backfill_match_keys,
    create_job,
    delete_job,
    update_job,
    validate_fields,
)

TEXT = "We are looking for a backend developer with Python, SQL and Docker. " * 2
NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def test_create_stores_new_job_with_event(db):
    job = create_job(db, text=TEXT, url="https://x.com/o/1?utm_source=a", title=" Dev ",
                     now=NOW)
    assert job.status == "new" and job.title == "Dev" and job.score is None
    assert job.url_key == "https://x.com/o/1"
    assert [(e.status, e.at) for e in job.events] == [("new", NOW)]


def test_duplicates_by_url_or_text(db):
    first = create_job(db, text=TEXT, url="https://x.com/o/1")
    by_url = create_job(db, text=TEXT + " different", url="https://X.com/o/1/#top")
    by_text = create_job(db, text="  " + TEXT.upper(), url="")
    assert isinstance(by_url, Duplicate) and by_url.job.id == first.id
    assert isinstance(by_text, Duplicate) and by_text.job.id == first.id


def test_jobs_without_url_do_not_collide(db):
    assert not isinstance(create_job(db, text=TEXT), Duplicate)
    assert not isinstance(create_job(db, text=TEXT + " other"), Duplicate)


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (("short", "", "", ""), "text"),
        ((TEXT, "javascript:alert(1)", "", ""), "url"),
        ((TEXT, "ftp://x.com", "", ""), "url"),
        ((TEXT, "", "t" * 301, ""), "title"),
        (("x" * 50_001, "", "", ""), "text"),
    ],
)
def test_validation(args, field):
    assert field in validate_fields(*args)


def test_valid_fields():
    assert validate_fields(TEXT, "https://x.com/o", "Dev", "Acme") == {}
    assert validate_fields(None, "", "", "", "") == {}


def test_update_and_url_conflict(db):
    a = create_job(db, text=TEXT, url="https://x.com/a")
    b = create_job(db, text=TEXT + " b")
    update_job(db, b, title="T", company="C", location="L", url="https://x.com/b")
    assert (b.title, b.company, b.location, b.url_key) == ("T", "C", "L", "https://x.com/b")
    result = update_job(db, b, title="T", company="C", location="L", url="https://x.com/a/")
    assert isinstance(result, Duplicate) and result.job.id == a.id


def test_delete_cascades_events(db):
    from sqlalchemy import func, select

    from rolecard.models import JobEvent

    job = create_job(db, text=TEXT)
    delete_job(db, job)
    assert db.scalar(select(func.count()).select_from(JobEvent)) == 0


def test_update_recomputes_match_key(db):
    job = create_job(db, text=TEXT)
    assert job.match_key is None
    update_job(db, job, title="Backend Dev", company="Ácme", location="Valencia", url="")
    assert job.match_key == "acme|backend dev|valencia"


def test_backfill_fills_only_empty_match_keys(db):
    old = create_job(db, text=TEXT, title="Dev", company="Acme")
    kept = create_job(db, text=TEXT + " kept", title="Dev", company="Other")
    bare = create_job(db, text=TEXT + " bare")
    old.match_key, kept.match_key = None, "custom"
    db.commit()
    assert backfill_match_keys(db) == 1
    assert (old.match_key, kept.match_key, bare.match_key) == ("acme|dev|", "custom", None)


def test_update_replaces_the_text_and_checks_duplicates(db):
    other = create_job(db, text=TEXT + " other")
    job = create_job(db, text=TEXT[:150])
    full = TEXT + " Full description pasted from the offer's page."
    update_job(db, job, title="", company="", location="", url="", text=f"  {full} ")
    assert job.text == full and not isinstance(create_job(db, text=full + " "), Job)
    result = update_job(db, job, title="", company="", location="", url="", text=other.text)
    assert isinstance(result, Duplicate) and result.job.id == other.id
    update_job(db, job, title="T", company="", location="", url="")  # no text: kept
    assert job.text == full
