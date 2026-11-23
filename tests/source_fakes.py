"""Fake network for source tests: canned answers, no real calls (R9)."""

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def http_error(status: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://hidden.test/", status, "err", headers, None)


class FakeNet:
    """Replaces ``rolecard.sources.http._open``. ``answers`` are bytes, dicts/lists (sent
    as JSON) or exceptions, consumed in order; the last one repeats."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, req, timeout):
        self.requests.append(req)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, dict | list):
            answer = json.dumps(answer).encode("utf-8")
        return FakeResponse(answer)


def install(monkeypatch, *answers) -> FakeNet:
    net = FakeNet(*answers)
    monkeypatch.setattr("rolecard.sources.http._open", net)
    return net
