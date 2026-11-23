import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rolecard import db, models

ROOT = Path(__file__).resolve().parent.parent


def _tables(path):
    with sqlite3.connect(path) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_migrates_from_empty_and_records_version(tmp_path):
    path = tmp_path / "x.sqlite3"
    assert db.migrate(path) == [1, 2, 3]
    assert {"profile", "jobs", "job_events", "documents", "schema_migrations"} <= _tables(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version, name FROM schema_migrations").fetchall() == [
            (1, "initial"), (2, "documents"), (3, "sources")
        ]


def test_reopening_does_not_reapply(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    assert db.migrate(path) == []


def _write(directory, files):
    directory.mkdir()
    for name, sql in files.items():
        (directory / name).write_text(sql)
    return directory


@pytest.mark.parametrize(
    "files, fragment",
    [
        ({"0001_a.sql": "", "0003_c.sql": ""}, "without gaps"),
        ({"0001_a.sql": "", "0001_b.sql": ""}, "used twice"),
        ({"0001_a.sql": "", "2_b.sql": ""}, "badly named"),
    ],
)
def test_gap_duplicate_or_bad_name_is_error(tmp_path, files, fragment):
    directory = _write(tmp_path / "m", files)
    with pytest.raises(db.MigrationError, match=fragment):
        db.migrate(tmp_path / "x.sqlite3", directory)


def test_failing_migration_rolls_back_whole_file(tmp_path):
    directory = _write(
        tmp_path / "m",
        {
            "0001_a.sql": "CREATE TABLE a (id INTEGER);",
            "0002_b.sql": "CREATE TABLE b (id INTEGER);\nINSERT INTO nope VALUES (1);",
        },
    )
    path = tmp_path / "x.sqlite3"
    with pytest.raises(db.MigrationError, match="0002_b.sql"):
        db.migrate(path, directory)
    assert "a" in _tables(path)
    assert "b" not in _tables(path)
    with sqlite3.connect(path) as conn:
        assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations")] == [1]


def test_database_newer_than_code_is_error(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO schema_migrations VALUES (99, 'future', 'x')")
    with pytest.raises(db.MigrationError, match="newer"):
        db.migrate(path)


def test_models_match_migrated_schema(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    inspector = inspect(db.make_engine(path))
    for table in models.Base.metadata.sorted_tables:
        on_disk = {c["name"] for c in inspector.get_columns(table.name)}
        assert on_disk == set(table.columns.keys()), table.name


def test_no_create_all_anywhere():
    sources = (ROOT / "rolecard").rglob("*.py")
    assert not [p for p in sources if "create_all(" in p.read_text(encoding="utf-8")]


def test_models_round_trip_and_cascade(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    engine = db.make_engine(path)
    with Session(engine) as session:
        job = models.Job(text="Python dev", text_key="k", follow_up_on=date(2026, 12, 1))
        job.events.append(models.JobEvent(status="new"))
        session.add(job)
        session.add(models.Profile(data={"name": "A"}, needs_review=True))
        session.commit()
        job_id = job.id
    with Session(engine) as session:
        job = session.get(models.Job, job_id)
        assert job.created_at.tzinfo is not None
        assert job.follow_up_on == date(2026, 12, 1)
        assert job.score_met == []
        assert session.get(models.Profile, 1).needs_review is True
        session.delete(job)
        session.commit()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM job_events").fetchone() == (0,)


def test_naive_datetime_is_rejected(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    with Session(db.make_engine(path)) as session:
        session.add(models.Job(text="t", text_key="k", scored_at=datetime(2026, 1, 1)))
        with pytest.raises(Exception, match="naive"):
            session.commit()
    aware = datetime(2026, 1, 1, tzinfo=UTC)
    assert models.UTCDateTime().process_bind_param(aware, None).endswith("+00:00")


def test_documents_migration_keeps_f1_data_and_cascades(tmp_path):
    """0002 runs on top of an F1 database with data, leaves it intact, and documents go
    away with their job."""
    path = tmp_path / "x.sqlite3"
    f1 = tmp_path / "f1"
    f1.mkdir()
    (f1 / "0001_initial.sql").write_text(
        (db.MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8"), encoding="utf-8")
    db.migrate(path, f1)
    with sqlite3.connect(path) as conn:
        now = "2026-01-01T00:00:00+00:00"
        conn.execute("INSERT INTO jobs (id, text, text_key, title, created_at, updated_at) "
                     "VALUES (7, 't', 'k', 'Dev', ?, ?)", (now, now))
    assert db.migrate(path) == [2, 3]
    assert db.migrate(path) == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT title, doc_language FROM jobs").fetchall() == [("Dev", "")]
    with Session(db.make_engine(path)) as session:
        session.add(models.Document(job_id=7, kind="cv", language="en", content={"s": []}))
        session.commit()
        doc = session.scalars(select(models.Document)).one()
        assert doc.job.title == "Dev" and doc.content == {"s": []} and doc.reviewed_at is None
        session.add(models.Document(job_id=7, kind="cv", language="es", content={}))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.delete(session.get(models.Job, 7))
        session.commit()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone() == (0,)


def _migrations(tmp_path, upto):
    folder = tmp_path / f"m{upto}"
    folder.mkdir(exist_ok=True)
    for n in range(1, upto + 1):
        (folder / f"{n:04d}_step{n}.sql").write_text(f"CREATE TABLE t{n} (id INTEGER);",
                                                     encoding="utf-8")
    return folder


def test_backup_before_pending_migrations_keeps_the_two_newest(tmp_path):
    path = tmp_path / "rolecard.sqlite3"
    db.migrate(path, _migrations(tmp_path, 1))
    assert list(tmp_path.glob("*.bak-v*")) == []  # a new database needs no copy
    for upto in (2, 3, 4):
        db.migrate(path, _migrations(tmp_path, upto))
    db.migrate(path, _migrations(tmp_path, 4))  # nothing pending: no new copy
    copies = sorted(p.name for p in tmp_path.glob("*.bak-v*"))
    assert copies == ["rolecard.sqlite3.bak-v2", "rolecard.sqlite3.bak-v3"]
    assert _tables(tmp_path / "rolecard.sqlite3.bak-v3") == {"schema_migrations", "t1",
                                                             "t2", "t3"}


def test_every_connection_overwrites_deleted_content(tmp_path):
    path = tmp_path / "x.sqlite3"
    db.migrate(path)
    with db.make_engine(path).connect() as conn:
        assert conn.exec_driver_sql("PRAGMA secure_delete").scalar() == 1
