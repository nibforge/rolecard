"""Any OpenAI-compatible ``/chat/completions`` endpoint (OpenAI, Ollama, LM Studio…).

Plain ``urllib`` (no SDK). The key travels in the ``Authorization`` header only; the
request never offers ``tools`` or ``functions``. Redirects are NOT followed: urllib would
re-send ``Authorization`` to wherever the ``Location`` points, so a 3xx is an error.
Structured output: the request asks for ``json_schema`` with the operation's schema; if
the server rejects that (400/404/422), it is sent once more with ``json_object``.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlsplit

from rolecard.ai.base import SYSTEM_PROMPT, AIError, AIProvider
from rolecard.ai.schema import to_json_schema

_UNSUPPORTED = frozenset({400, 404, 422})
MAX_ANSWER = 2 * 1024 * 1024  # bytes; an answer is a small JSON object
MAX_ERROR_BODY = 64 * 1024  # bytes read from an error answer (only for its retry delay)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913
        return None  # urllib then raises HTTPError with the 3xx code


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect)


def valid_base_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError for a bad or out-of-range port
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def is_local(url: str) -> bool:
    """True when ``url`` points at this machine (Ollama, LM Studio…): nothing leaves it."""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:  # a name such as 127.evil.com may resolve anywhere
        return False


class OpenAICompatibleProvider(AIProvider):
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 120,
                 opener: Callable = _NO_REDIRECT_OPENER.open) -> None:
        if not valid_base_url(base_url) or not model:
            raise AIError("not_configured", "base_url and model are required")
        if api_key and urlsplit(base_url).scheme == "http" and not is_local(base_url):
            raise AIError("insecure", "an API key is only sent over https or to this machine")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self._api_key = api_key
        self.timeout = timeout
        self._open = opener

    def __repr__(self) -> str:  # never show the key
        return f"OpenAICompatibleProvider(url={self.url!r}, model={self.model!r})"

    def request(self, prompt: str, schema: dict | None = None,
                plain: bool = False) -> urllib.request.Request:
        """The chat request; with ``schema`` it asks for ``json_schema``, else ``json_object``;
        ``plain`` sends no ``response_format`` at all (servers that support neither)."""
        if schema is None:
            response_format = {"type": "json_object"}
        else:
            response_format = {"type": "json_schema", "json_schema": {
                "name": "answer", "strict": False, "schema": to_json_schema(schema)}}
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        if not plain:
            body["response_format"] = response_format
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return urllib.request.Request(
            self.url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )

    def complete(self, prompt: str, schema: dict | None = None) -> str:
        """Ask for ``json_schema``, then ``json_object``, then no format: each step only
        when the server rejects the previous one as unsupported (400, 404 or 422)."""
        attempts = [self.request(prompt, schema)] if schema is not None else []
        attempts += [self.request(prompt), self.request(prompt, plain=True)]
        for req in attempts[:-1]:
            try:
                return self._send(req)
            except AIError as exc:
                if exc.detail not in {f"HTTP {code}" for code in _UNSUPPORTED}:
                    raise
        return self._send(attempts[-1])

    def _send(self, req: urllib.request.Request) -> str:
        try:
            with self._open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_ANSWER + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:  # quota used up: one request, never a retry loop
                raise AIError("quota", "HTTP 429", retry_after=retry_after(exc)) from exc
            if exc.code == 503:  # busy ("high demand"), not a bad key: no retry either
                raise AIError("busy", "HTTP 503") from exc
            raise AIError("http", f"HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise AIError("timeout", f"after {self.timeout}s") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AIError("timeout", f"after {self.timeout}s") from exc
            raise AIError("network", str(exc.reason)) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise AIError("network", str(exc)) from exc
        except ValueError as exc:  # http.client.InvalidURL and friends
            raise AIError("failed", str(exc)) from exc
        if len(raw) > MAX_ANSWER:
            raise AIError("failed", f"answer larger than {MAX_ANSWER} bytes")
        return _message_text(raw)


_DELAY = re.compile(r"\A(\d{1,7})(?:\.\d+)?s\Z")


def retry_after(exc: urllib.error.HTTPError) -> int | None:
    """Seconds a 429 asks to wait: the ``Retry-After`` header, or the ``RetryInfo`` detail
    of a Google error (``"retryDelay": "79674s"``). None when neither says."""
    header = (exc.headers.get("Retry-After") if exc.headers else None) or ""
    if header.strip().isdigit():
        return int(header.strip())
    try:
        payload = json.loads(exc.read(MAX_ERROR_BODY).decode("utf-8"))
    except (AttributeError, OSError, ValueError, http.client.HTTPException):
        return None
    payload = payload[0] if isinstance(payload, list) and payload else payload
    details = payload.get("error", {}).get("details", []) if isinstance(payload, dict) else []
    for item in details if isinstance(details, list) else []:
        delay = _DELAY.match(str(item.get("retryDelay", ""))) if isinstance(item, dict) else None
        if delay:
            return int(delay.group(1)) + 1
    return None


def _message_text(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise AIError("failed", "unexpected response from the endpoint") from exc
    if not isinstance(content, str):
        raise AIError("failed", "the endpoint returned no text")
    return content
