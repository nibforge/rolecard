"""The home page and the lists run a fixed number of queries, whatever the number of
offers (no N+1)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from rolecard import get_db
from rolecard.models import Document, Job

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
PENDING = {"sentences": {"s1": {"text": "x", "state": "unsourced", "sources": []}}}


def _add_jobs(app, start, n):
    with app.app_context():
        db = get_db()
        for i in range(start, start + n):
            job = Job(text=f"t{i}", text_key=f"k{i}", title=f"Job {i}", score=50 + i)
            job.documents.append(Document(kind="cv", language="en", content=PENDING,
                                          source_snapshot={}))
            job.documents.append(Document(kind="letter", language="en", content=PENDING,
                                          source_snapshot={}, reviewed_at=NOW))
            db.add(job)
        db.commit()


def _queries(app, client, path):
    engine = app.extensions["rolecard.sessions"].kw["bind"]
    seen = []

    def count(*_args):
        seen.append(1)

    event.listen(engine, "before_cursor_execute", count)
    try:
        assert client.get(path).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return len(seen)


@pytest.mark.parametrize("path", ["/", "/jobs", "/board"])
def test_queries_do_not_grow_with_offers(app, client, path):
    _add_jobs(app, 0, 2)
    few = _queries(app, client, path)
    _add_jobs(app, 2, 10)
    assert _queries(app, client, path) == few


def test_home_lists_only_documents_not_reviewed(app, client):
    _add_jobs(app, 0, 3)
    with app.app_context():
        from rolecard.services.home import for_today
        today = for_today(get_db(), NOW.date())
        assert [d.kind for d, _ in today.documents] == ["cv"] * 3
        assert all(n == 1 for _, n in today.documents)
