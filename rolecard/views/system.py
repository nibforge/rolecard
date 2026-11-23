"""Quit: the sidebar button that stops the local server."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template, request

bp = Blueprint("system", __name__)


@bp.post("/quit")
def quit_app():
    """Show the goodbye page and stop the server (only for the local browser)."""
    if request.remote_addr != "127.0.0.1":
        abort(400)
    shutdown = current_app.config.get("SHUTDOWN")  # set by cli.py; absent in tests and dev
    if shutdown is not None:
        shutdown()
    return render_template("closed.html")
