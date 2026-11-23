"""Source HTTP client: retries, limits, no URL in errors or logs; no real network (R3, R4, R9)."""

import logging
import socket
import urllib.error
import urllib.request

import pytest

from rolecard.sources import http
from tests.source_fakes import http_error, install

SECRET = "sk-secret-123"
URL = "https://api.example.test/search"


def _waits():
    waits = []
    return waits, waits.append


def test_real_network_is_blocked_in_tests():
    with pytest.raises(RuntimeError, match="forbidden"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises((RuntimeError, urllib.error.URLError)):
        urllib.request.urlopen("https://example.com", timeout=1)


def test_ok_json_and_query_built(monkeypatch):
    net = install(monkeypatch, {"jobs": []})
    assert http.request_json(URL, {"q": "py dev"}) == {"jobs": []}
    assert net.requests[0].full_url == URL + "?q=py+dev"
    assert net.requests[0].get_method() == "GET"


def test_post_body_is_json(monkeypatch):
    net = install(monkeypatch, {"ok": 1})
    http.request_json(URL, body={"keywords": "x"})
    assert net.requests[0].get_method() == "POST"
    assert net.requests[0].data == b'{"keywords": "x"}'


def test_only_https():
    with pytest.raises(http.SourceError) as err:
        http.request_json("http://api.example.test/x")
    assert err.value.code == "bad_response"


@pytest.mark.parametrize("first", [
    http_error(503),
    urllib.error.URLError(TimeoutError()),
    TimeoutError(),
    urllib.error.URLError(ConnectionRefusedError()),
    http_error(429),
])
def test_retries_with_backoff_then_succeeds(monkeypatch, first):
    waits, sleep = _waits()
    net = install(monkeypatch, first, first, {"ok": True})
    assert http.request_json(URL, sleep=sleep) == {"ok": True}
    assert len(net.requests) == 3 and waits == [1, 3]


def test_gives_up_after_two_retries(monkeypatch):
    waits, sleep = _waits()
    install(monkeypatch, http_error(500))
    with pytest.raises(http.SourceError) as err:
        http.request_json(URL, sleep=sleep)
    assert err.value.code == "http_5xx" and waits == [1, 3]


def test_retry_after_is_honoured_or_gives_up(monkeypatch):
    waits, sleep = _waits()
    install(monkeypatch, http_error(429, "2"), {"ok": 1})
    http.request_json(URL, sleep=sleep)
    assert waits == [2]
    install(monkeypatch, http_error(429, "3600"))
    with pytest.raises(http.SourceError) as err:
        http.request_json(URL, sleep=sleep)
    assert err.value.code == "rate_limited" and waits == [2]


@pytest.mark.parametrize("answer, code", [
    (http_error(404), "http_4xx"),
    (http_error(302), "redirect"),
    (b"<html>no</html>", "bad_response"),
    (b"\xff\xfe", "bad_response"),
])
def test_no_retry_for_client_errors_or_bad_body(monkeypatch, answer, code):
    net = install(monkeypatch, answer)
    with pytest.raises(http.SourceError) as err:
        http.request_json(URL, sleep=lambda s: None)
    assert err.value.code == code and len(net.requests) == 1


def test_answer_too_large(monkeypatch):
    monkeypatch.setattr(http, "MAX_BYTES", 10)
    install(monkeypatch, b'{"a": "0123456789"}')
    with pytest.raises(http.SourceError, match="too large"):
        http.request_json(URL)


def test_key_in_url_never_leaks_to_error_or_log(monkeypatch, caplog):
    """P1: Adzuna's key travels in the query; a network error must not expose it."""
    caplog.set_level(logging.DEBUG)
    install(monkeypatch, urllib.error.URLError(ConnectionRefusedError(f"refused {SECRET}")),
            http_error(500))
    with pytest.raises(http.SourceError) as err:
        http.request_json(URL, {"app_key": SECRET}, sleep=lambda s: None)
    assert SECRET not in str(err.value) and "api.example.test" not in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__
    logging.getLogger("rolecard").exception("search failed", exc_info=err.value)
    assert SECRET not in caplog.text
    assert logging.getLogger("urllib3").level == logging.WARNING
