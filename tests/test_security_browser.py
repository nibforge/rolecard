"""Requests shaped like the real browser + HTMX ones (regression: every POST got 400)."""

import io
import re

import pytest

from tests.conftest import PORT
from tests.helpers import make_pdf

HOSTS = [f"127.0.0.1:{PORT}", f"localhost:{PORT}"]


def _browser_token(client, base_url: str, path: str) -> str:
    """Load a page like the browser does and read the token from its <meta>."""
    page = client.get(path, base_url=base_url)
    assert page.status_code == 200
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.get_data(as_text=True))
    assert match
    return match.group(1)


def _htmx_headers(token: str, origin: str, fetch_site: str = "same-origin") -> dict:
    return {
        "HX-Request": "true",
        "X-CSRF-Token": token,
        "Origin": origin,
        "Sec-Fetch-Site": fetch_site,
    }


@pytest.mark.parametrize("host", HOSTS)
def test_htmx_connection_test_is_accepted(client, host):
    base = f"http://{host}"
    token = _browser_token(client, base, "/settings")
    response = client.post(
        "/settings/test",
        base_url=base,
        data={"csrf_token": token, "provider": "anthropic"},
        headers=_htmx_headers(token, base),
    )
    assert response.status_code == 200
    assert "Request rejected" not in response.get_data(as_text=True)


@pytest.mark.parametrize("host", HOSTS)
def test_multipart_cv_upload_is_accepted(client, host):
    base = f"http://{host}"
    token = _browser_token(client, base, "/profile")
    response = client.post(
        "/profile/upload",
        base_url=base,
        data={"csrf_token": token, "cv": (io.BytesIO(make_pdf()), "cv.pdf")},
        content_type="multipart/form-data",
        headers={"Origin": base, "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code == 302  # passes the guard; no provider set -> back to form


def test_null_origin_from_same_origin_page_is_accepted(client):
    # Chrome sends "Origin: null" on POST when the page's Referrer-Policy is no-referrer.
    base = f"http://{HOSTS[0]}"
    token = _browser_token(client, base, "/settings")
    response = client.post(
        "/settings/test", base_url=base, headers=_htmx_headers(token, "null")
    )
    assert response.status_code == 200


def test_other_local_host_origin_is_accepted(client):
    base = f"http://{HOSTS[0]}"
    token = _browser_token(client, base, "/settings")
    headers = _htmx_headers(token, f"http://{HOSTS[1]}", "same-site")
    assert client.post("/settings/test", base_url=base, headers=headers).status_code == 200


def test_cross_site_htmx_post_is_rejected_even_with_token(client):
    base = f"http://{HOSTS[0]}"
    token = _browser_token(client, base, "/settings")
    headers = _htmx_headers(token, "http://evil.example", "cross-site")
    assert client.post("/settings/test", base_url=base, headers=headers).status_code == 400


def test_pages_ask_browser_to_send_real_origin(client):
    assert client.get("/settings").headers["Referrer-Policy"] == "same-origin"
