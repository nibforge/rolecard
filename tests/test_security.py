import pytest
from flask import Blueprint

from rolecard import create_app
from tests.conftest import BASE_URL, PORT


@pytest.fixture
def app(data_dir):
    app = create_app(data_dir, port=PORT, testing=True)
    bp = Blueprint("probe", __name__)
    hits = []

    @bp.post("/_probe")
    def probe():
        hits.append(1)
        return "ok"

    app.register_blueprint(bp)
    app.config["PROBE_HITS"] = hits
    return app


@pytest.mark.parametrize(
    "host", ["evil.example:8765", "127.0.0.1:9999", "localhost", "attacker.test"]
)
def test_foreign_host_is_rejected(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "LOCALHOST:8765"])
def test_local_hosts_are_accepted(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 200


def test_post_without_csrf_is_rejected(app, client):
    assert client.post("/_probe").status_code == 400
    assert app.config["PROBE_HITS"] == []


def test_post_with_wrong_csrf_is_rejected(app, client, csrf):
    assert client.post("/_probe", data={"csrf_token": "nope"}).status_code == 400
    assert app.config["PROBE_HITS"] == []


def test_post_with_csrf_form_field_or_header_passes(app, client, csrf):
    assert client.post("/_probe", data={"csrf_token": csrf}).status_code == 200
    assert client.post("/_probe", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert len(app.config["PROBE_HITS"]) == 2


@pytest.mark.parametrize(
    ("origin", "fetch_site"),
    [
        ("http://evil.example", "cross-site"),
        ("null", None),
        ("null", "cross-site"),
        ("null", "same-site"),
        ("http://127.0.0.1:9999", "same-site"),
        ("https://127.0.0.1:8765", "cross-site"),
        ("http://localhost.evil.example:8765", "cross-site"),
    ],
)
def test_post_with_foreign_origin_is_rejected(app, client, csrf, origin, fetch_site):
    headers = {"Origin": origin}
    if fetch_site:
        headers["Sec-Fetch-Site"] = fetch_site
    response = client.post("/_probe", data={"csrf_token": csrf}, headers=headers)
    assert response.status_code == 400
    assert app.config["PROBE_HITS"] == []


def test_post_with_own_origin_passes(client, csrf):
    response = client.post("/_probe", data={"csrf_token": csrf}, headers={"Origin": BASE_URL})
    assert response.status_code == 200


def test_security_headers_on_every_response(client):
    for path in ("/", "/missing"):
        headers = client.get(path).headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "same-origin"
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_session_cookie_is_strict(client, app):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Strict"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True


def test_csrf_token_helper_creates_and_reuses_token(app):
    from rolecard.security import csrf_token

    with app.test_request_context(base_url=BASE_URL):
        first = csrf_token()
        assert len(first) >= 32
        assert csrf_token() == first
