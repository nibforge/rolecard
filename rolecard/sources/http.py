"""HTTP for job sources: HTTPS only, no redirects, timeout, size cap and retries.

Some APIs (Adzuna) only accept the key in the query string, so a URL here may hold a
secret. Therefore a URL is NEVER logged or put in an error: every failure is re-raised as
``SourceError`` with a code and a short detail, ``from None`` (no chained exception that
could carry the URL into a traceback). The stdlib ``urllib`` does not log requests; the
``urllib3`` logger is pinned at WARNING in case a dependency ever uses it.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit

TIMEOUT = 15
MAX_BYTES = 8 * 1024 * 1024
BACKOFF = (1, 3)
MAX_RETRY_AFTER = 10
USER_AGENT = "rolecard (local job-search tool)"

for _name in ("urllib3", "urllib"):
    logging.getLogger(_name).setLevel(logging.WARNING)


class SourceError(Exception):
    """A source failed. ``code`` is one of: timeout, network, http_4xx, http_5xx,
    redirect, rate_limited, bad_response, not_configured. Never contains a URL."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913
        return None  # urllib then raises HTTPError with the 3xx code


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(req: urllib.request.Request, timeout: float):
    """The only place that touches the network (tests replace it)."""
    return _OPENER.open(req, timeout=timeout)


def build_url(base: str, params: dict | None = None) -> str:
    if urlsplit(base).scheme != "https":
        raise SourceError("bad_response", "only https sources are allowed")
    return f"{base}?{urlencode(params, doseq=True)}" if params else base


def request_json(base: str, params: dict | None = None, *, body: dict | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> object:
    """GET (or POST ``body`` as JSON) and parse the JSON answer, with retries."""
    url = build_url(base, params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    attempts = len(BACKOFF) + 1
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data is not None else "GET")
        try:
            return _parse(_read(req))
        except _Retry as retry:
            if attempt == attempts - 1:
                raise SourceError(retry.code, retry.detail) from None
            sleep(retry.wait if retry.wait is not None else BACKOFF[attempt])
    raise AssertionError("unreachable")  # pragma: no cover


class _Retry(Exception):
    def __init__(self, code: str, detail: str, wait: float | None = None):
        super().__init__(code)
        self.code, self.detail, self.wait = code, detail, wait


def _read(req: urllib.request.Request) -> bytes:
    try:
        with _open(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status, retry_after = exc.code, exc.headers.get("Retry-After") if exc.headers else None
        exc.close()
        raise _status_error(status, retry_after) from None
    except TimeoutError:
        raise _Retry("timeout", f"after {TIMEOUT}s") from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise _Retry("timeout", f"after {TIMEOUT}s") from None
        raise _Retry("network", type(exc.reason).__name__) from None
    except OSError as exc:
        raise _Retry("network", type(exc).__name__) from None
    if len(raw) > MAX_BYTES:
        raise SourceError("bad_response", "answer too large") from None
    return raw


def _status_error(status: int, retry_after: str | None) -> Exception:
    if status == 429:
        wait = _seconds(retry_after)
        if wait is not None and wait > MAX_RETRY_AFTER:
            return SourceError("rate_limited", f"retry after {wait}s")
        return _Retry("rate_limited", "HTTP 429", wait)
    if 500 <= status < 600:
        return _Retry("http_5xx", f"HTTP {status}")
    if 300 <= status < 400:
        return SourceError("redirect", f"HTTP {status}")
    return SourceError("http_4xx", f"HTTP {status}")


def _seconds(value: str | None) -> int | None:
    try:
        return max(0, int((value or "").strip()))
    except ValueError:
        return None


def _parse(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SourceError("bad_response", "not JSON") from None
