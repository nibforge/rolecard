"""rolecard: a local job-search assistant."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, g, render_template
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.exceptions import HTTPException

from rolecard import config as cfg
from rolecard.db import make_engine, migrate
from rolecard.i18n import init_i18n
from rolecard.logs import init_logging
from rolecard.security import init_security
from rolecard.services.jobs import backfill_match_keys

__version__ = "0.1.0"

DEFAULT_PORT = 8765
_TRANSLATED_ERRORS = (400, 404, 413, 500)


def create_app(data_dir: Path | str, *, port: int = DEFAULT_PORT, testing: bool = False) -> Flask:
    """Build the app on top of ``data_dir`` (created, configured and migrated here).

    Raises ``config.ConfigError`` or ``db.MigrationError`` with a one-line message.
    """
    data_dir = cfg.ensure_data_dir(Path(data_dir))
    settings = cfg.load_config(data_dir)
    init_logging(data_dir)
    db_path = data_dir / cfg.DB_FILE
    migrate(db_path)

    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        SECRET_KEY=cfg.load_secret_key(data_dir),
        DATA_DIR=data_dir,
        PORT=port,
        ROLECARD=settings,
    )
    engine = make_engine(db_path)
    app.extensions["rolecard.sessions"] = sessionmaker(engine, expire_on_commit=False)
    with app.extensions["rolecard.sessions"]() as session:
        backfill_match_keys(session)

    init_security(app, port)
    init_i18n(app)
    _register_blueprints(app)
    _register_errors(app)

    @app.teardown_appcontext
    def _close_db(_exc) -> None:
        session = g.pop("db", None)
        if session is not None:
            session.close()

    return app


def get_db() -> Session:
    """The SQLAlchemy session for the current request (closed at teardown)."""
    from flask import current_app

    if "db" not in g:
        g.db = current_app.extensions["rolecard.sessions"]()
    return g.db


def _register_blueprints(app: Flask) -> None:
    from rolecard.views import (
        board,
        dashboard,
        documents,
        init_views,
        jobs,
        profile,
        search,
        settings,
    )

    init_views(app)
    for module in (dashboard, board, search, jobs, documents, profile, settings):
        app.register_blueprint(module.bp)


def _register_errors(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        code = exc.code if exc.code in _TRANSLATED_ERRORS else 400
        return render_template("error.html", code=code), exc.code or 400

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        app.logger.exception("unexpected error")
        return render_template("error.html", code=500), 500
