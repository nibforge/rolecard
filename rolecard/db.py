"""SQLite database: explicit numbered SQL migrations and the SQLAlchemy engine.

Tables are created ONLY by the files in ``rolecard/migrations/``; the ORM models just
map them. Each migration runs in its own transaction together with its row in
``schema_migrations``, so a failing file leaves nothing half-applied.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BACKUPS_KEPT = 2
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


class MigrationError(Exception):
    """The migration files or the database version are inconsistent."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """List migration files in order; a gap or a repeated number is an error."""
    found: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = _NAME.match(path.name)
        if not match:
            raise MigrationError(f"badly named migration file: {path.name}")
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"migration number {version:04d} is used twice")
        found[version] = Migration(version, match.group(2), path)
    versions = sorted(found)
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError(f"migration numbers must be 0001, 0002… without gaps: {versions}")
    return [found[v] for v in versions]


def migrate(db_path: Path, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations in order; return the versions applied now."""
    migrations = discover(directory)
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA secure_delete = ON")
        conn.execute(_BOOKKEEPING)
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        known = {m.version for m in migrations}
        if applied - known:
            raise MigrationError(
                "the database was created by a newer rolecard; update rolecard to open it"
            )
        pending = [m for m in migrations if m.version not in applied]
        if pending and applied:
            backup(conn, db_path, max(applied))
        done = []
        for migration in migrations:
            if migration.version not in applied:
                _apply(conn, migration)
                done.append(migration.version)
        return done
    finally:
        conn.close()


def backup(conn: sqlite3.Connection, db_path: Path, version: int) -> Path:
    """Copy the database as it is before migrating (``<name>.bak-v<version>``, with the
    SQLite backup API) and keep only the ``BACKUPS_KEPT`` newest copies."""
    target = db_path.with_name(f"{db_path.name}.bak-v{version}")
    copy = sqlite3.connect(target)
    try:
        conn.backup(copy)
    finally:
        copy.close()
    copies = sorted(db_path.parent.glob(f"{db_path.name}.bak-v*"), key=_backup_version)
    for old in copies[:-BACKUPS_KEPT]:
        old.unlink()
    return target


def _backup_version(path: Path) -> int:
    tail = path.name.rsplit(".bak-v", 1)[-1]
    return int(tail) if tail.isdigit() else -1


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    sql = migration.path.read_text(encoding="utf-8")
    now = datetime.now(UTC).isoformat()
    try:
        conn.execute("BEGIN")
        for statement in _statements(sql):
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, now),
        )
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK")
        raise MigrationError(f"migration {migration.path.name} failed: {exc}") from exc


def _statements(sql: str) -> list[str]:
    """Split a migration into statements (no semicolons inside literals in our files)."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def make_engine(db_path: Path) -> Engine:
    """Engine for the app. Every connection enforces foreign keys and overwrites deleted
    content (``secure_delete``: a deleted profile or offer does not stay in free pages)."""
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record) -> None:
        dbapi_conn.execute("PRAGMA foreign_keys = ON")
        dbapi_conn.execute("PRAGMA secure_delete = ON")

    return engine
