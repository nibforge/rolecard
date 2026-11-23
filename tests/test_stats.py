from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from rolecard import get_db
from rolecard.models import Job, JobEvent
from rolecard.services.stats import pending_follow_ups, week_numbers, week_start

MADRID = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 20, 18, 0, tzinfo=MADRID)  # Friday
MONDAY = datetime(2026, 11, 16, 0, 0, tzinfo=MADRID)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def add(db, n, *, created, status="new", follow_up=None, score=None, events=()):
    job = Job(text=f"t{n}", text_key=f"k{n}", title=f"Job {n}", status=status,
              created_at=created, follow_up_on=follow_up, score=score)
    for name, at in events:
        job.events.append(JobEvent(status=name, at=at))
    db.add(job)
    db.commit()
    return job


def test_week_starts_on_local_monday_midnight():
    assert week_start(NOW) == MONDAY
    assert week_start(MONDAY) == MONDAY
    sunday = datetime(2026, 11, 22, 23, 59, tzinfo=MADRID)
    assert week_start(sunday) == MONDAY


def test_naive_now_is_refused(db):
    with pytest.raises(ValueError):
        week_numbers(db, datetime(2026, 11, 20))


def test_week_numbers_use_local_monday_boundary(db):
    just_before = MONDAY - timedelta(seconds=1)  # Sunday 23:59:59 local = Sunday 22:59 UTC
    just_after = MONDAY.astimezone(UTC)  # Sunday 23:00 UTC is already Monday locally
    add(db, 1, created=just_before)
    add(db, 2, created=just_after, events=[("sent", just_after)])
    add(db, 3, created=just_before, events=[("sent", just_before), ("interview", NOW)])
    add(db, 4, created=just_after, events=[("sent", NOW), ("discarded", NOW), ("sent", NOW)])
    numbers = week_numbers(db, NOW)
    assert numbers.since == date(2026, 11, 16)
    assert numbers.added == 2
    assert numbers.sent == 2  # job 2 and job 4 (counted once)
    assert numbers.interviews == 1


def test_overdue_and_pending_follow_ups(db):
    today = NOW.date()
    add(db, 1, created=MONDAY, follow_up=today - timedelta(days=3), score=50)
    add(db, 2, created=MONDAY, follow_up=today, score=90)
    add(db, 3, created=MONDAY, follow_up=today - timedelta(days=3), score=80)
    add(db, 4, created=MONDAY, follow_up=today + timedelta(days=1))
    add(db, 5, created=MONDAY, follow_up=today - timedelta(days=9), status="discarded")
    assert week_numbers(db, NOW).overdue == 2
    assert [j.title for j in pending_follow_ups(db, today)] == ["Job 3", "Job 1", "Job 2"]
