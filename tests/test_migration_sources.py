"""0003 (sources) on top of a 0002 database with data: nothing is lost (R6, R13).

This test replaces the template's CI migrations job: the suite runs it in CI."""

import sqlite3

from sqlalchemy.orm import Session

from rolecard import db, models

NOW = "2026-01-01T00:00:00+00:00"


def _db_at_0002(tmp_path):
    old = tmp_path / "f2"
    old.mkdir()
    for name in ("0001_initial.sql", "0002_documents.sql"):
        (old / name).write_text((db.MIGRATIONS_DIR / name).read_text(encoding="utf-8"),
                                encoding="utf-8")
    path = tmp_path / "x.sqlite3"
    assert db.migrate(path, old) == [1, 2]
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO profile (id, data, updated_at) VALUES (1, '{\"a\": 1}', ?)",
                     (NOW,))
        conn.execute("INSERT INTO jobs (id, url, url_key, text, text_key, title, company, "
                     "status, score, doc_language, created_at, updated_at) VALUES "
                     "(7, 'https://x.test/j', 'https://x.test/j', 'Some text', 'k', 'Dev', "
                     "'Acme', 'sent', 80, 'es', ?, ?)", (NOW, NOW))
        conn.execute("INSERT INTO job_events (job_id, status, at) VALUES (7, 'sent', ?)",
                     (NOW,))
        conn.execute("INSERT INTO documents (job_id, kind, language, content, created_at, "
                     "updated_at) VALUES (7, 'cv', 'es', '{\"s\": []}', ?, ?)", (NOW, NOW))
    return path


def test_0003_keeps_existing_data(tmp_path):
    path = _db_at_0002(tmp_path)
    assert db.migrate(path) == [3]
    assert db.migrate(path) == []
    with sqlite3.connect(path) as conn:
        assert conn.execute(
            "SELECT title, company, status, score, doc_language, source, external_id, "
            "match_key, search_id FROM jobs").fetchall() == [
            ("Dev", "Acme", "sent", 80, "es", "manual", None, None, None)]
        assert conn.execute("SELECT COUNT(*) FROM job_events").fetchone() == (1,)
        assert conn.execute("SELECT kind, content FROM documents").fetchall() == [
            ("cv", '{"s": []}')]
        assert conn.execute("SELECT data FROM profile").fetchone() == ('{"a": 1}',)


def test_deleting_a_search_keeps_its_jobs(tmp_path):
    path = _db_at_0002(tmp_path)
    db.migrate(path)
    with Session(db.make_engine(path)) as session:
        search = models.Search(name="Python remote", sources=["remotive"])
        session.add(search)
        session.flush()
        session.get(models.Job, 7).search_id = search.id
        session.add(models.SourceCall(source="remotive", endpoint="https://remotive.com/api"))
        session.commit()
        session.delete(search)
        session.commit()
        job = session.get(models.Job, 7)
        session.refresh(job)
        assert job.search_id is None and job.title == "Dev"
