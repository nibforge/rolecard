"""Local per-source limits in source_calls (R3)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from rolecard import db
from rolecard.models import SourceCall
from rolecard.sources.limits import Limit, RateLimited, check, record

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)


@pytest.fixture
def session(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    with Session(db.make_engine(path)) as s:
        yield s


def test_per_day_limit_then_next_day(session):
    limit = Limit(per_day=4, min_interval=60)
    now = T0
    for _ in range(4):
        check(session, "remotive", limit, now)
        record(session, "remotive", "https://remotive.com/api/remote-jobs?search=x", now)
        now += timedelta(minutes=5)
    with pytest.raises(RateLimited) as err:
        check(session, "remotive", limit, now)
    assert err.value.retry_at == datetime(2026, 3, 3, tzinfo=UTC)
    check(session, "remotive", limit, datetime(2026, 3, 3, 0, 1, tzinfo=UTC))


def test_min_interval(session):
    limit = Limit(min_interval=60)
    record(session, "arbeitnow", "https://www.arbeitnow.com/api/job-board-api", T0)
    with pytest.raises(RateLimited) as err:
        check(session, "arbeitnow", limit, T0 + timedelta(seconds=30))
    assert err.value.retry_at == T0 + timedelta(seconds=60)
    check(session, "arbeitnow", limit, T0 + timedelta(seconds=60))


def test_endpoint_stored_without_query(session):
    url = "https://api.adzuna.com/v1/api/jobs/es/search/1?app_key=SECRET"
    record(session, "adzuna", url, T0)
    row = session.get(SourceCall, "adzuna")
    assert row.endpoint == "https://api.adzuna.com/v1/api/jobs/es/search/1"
    assert row.calls_today == 1


def test_counter_resets_on_a_new_day(session):
    record(session, "adzuna", "https://a.test/x", T0)
    record(session, "adzuna", "https://a.test/x", T0 + timedelta(days=1))
    assert session.get(SourceCall, "adzuna").calls_today == 1
