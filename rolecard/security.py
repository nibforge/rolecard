"""Request guards for a local-only app: Host check, CSRF + Origin, security headers.

There are no accounts; the protection is that only the local browser, on this exact
host and port, can talk to the server and submit forms.
"""

from __future__ import annotations

import hmac
import secrets

from flask import Flask, abort, request, session

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def allowed_hosts(port: int) -> frozenset[str]:
    """Hosts the server answers to (DNS rebinding defence)."""
    return frozenset({f"127.0.0.1:{port}", f"localhost:{port}"})


def csrf_token() -> str:
    """The session's CSRF token, created on first use (exposed to templates)."""
    token = session.get(CSRF_FIELD)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_FIELD] = token
    return token


def _check_host(app: Flask) -> None:
    if request.host.lower() not in app.config["ALLOWED_HOSTS"]:
        abort(400)


def _check_origin(app: Flask) -> None:
    """Reject cross-site writes. The CSRF token is still required on top of this.

    Accepted: no Origin (older clients), ``http://`` plus an allowed host (127.0.0.1 or
    localhost on the real port), or ``null`` when the browser itself marks the request
    as same-origin (``Sec-Fetch-Site`` cannot be set by page scripts).
    """
    origin = request.headers.get("Origin")
    if origin is None:
        return
    origin = origin.strip().lower()
    if origin == "null":
        if request.headers.get("Sec-Fetch-Site", "").lower() != "same-origin":
            abort(400)
        return
    allowed = {f"http://{host}" for host in app.config["ALLOWED_HOSTS"]}
    if origin not in allowed:
        abort(400)


def _check_csrf() -> None:
    expected = session.get(CSRF_FIELD)
    sent = request.form.get(CSRF_FIELD) or request.headers.get(CSRF_HEADER) or ""
    if not expected or not hmac.compare_digest(str(expected), str(sent)):
        abort(400)


def init_security(app: Flask, port: int) -> None:
    """Register the guards and headers on ``app``."""
    app.config["ALLOWED_HOSTS"] = allowed_hosts(port)
    app.config.update(
        SESSION_COOKIE_NAME="rolecard_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,  # 10 MB CV plus form overhead
    )
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def _guard() -> None:
        _check_host(app)
        if request.method in UNSAFE_METHODS:
            _check_origin(app)
            _check_csrf()

    @app.after_request
    def _headers(response):
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Cache-Control", "no-store")
        return response
