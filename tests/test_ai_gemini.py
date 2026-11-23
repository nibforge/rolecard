"""Gemini through the OpenAI-compatible provider: cases seen in the real test of
2026-11-22 (answer shape, free-tier quota, high demand)."""

import io
import json
import urllib.error

import pytest

from rolecard.ai import AIError
from rolecard.ai.openai_compat import OpenAICompatibleProvider
from rolecard.i18n import t


class Opener:
    def __init__(self, body=b"", exc=None):
        self.body, self.exc, self.requests = body, exc, []

    def __call__(self, req, timeout):
        self.requests.append((req, timeout))
        if self.exc:
            raise self.exc
        return io.BytesIO(self.body)


GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai"


def test_gemini_answer_with_its_extra_fields_is_read():
    body = json.dumps({"choices": [{"finish_reason": "stop", "index": 0, "message": {
        "content": '{\n  "ok": true\n}', "role": "assistant",
        "extra_content": {"google": {"thought_signature": "abc"}}}}],
        "model": "gemini-3.5-flash-lite", "object": "chat.completion",
        "usage": {"completion_tokens": 7, "prompt_tokens": 40, "total_tokens": 60}}).encode()
    OpenAICompatibleProvider(GEMINI, "gemini-3.5-flash-lite", "k", opener=Opener(body)).check()


def _http_error(status, body=b"", headers=None):
    return urllib.error.HTTPError("u", status, "x", headers or {}, io.BytesIO(body))


@pytest.mark.parametrize(("status", "code"), [(429, "quota"), (503, "busy")])
def test_gemini_quota_or_busy_is_one_request(status, code):
    """A 429 (free-tier daily quota) or a 503 (high demand) is not a format problem: no
    second or third request that would spend more of the quota."""
    opener = Opener(exc=_http_error(status))
    with pytest.raises(AIError) as info:
        OpenAICompatibleProvider(GEMINI, "gemini-3.8-flash", "k", opener=opener).check()
    assert (info.value.code, info.value.detail) == (code, f"HTTP {status}")
    assert len(opener.requests) == 1


def test_a_busy_service_says_so_and_does_not_blame_the_key(app):
    """503 "high demand" gets its own message, not the one that says to check the key."""
    exc = AIError("busy", "HTTP 503")
    assert exc.message_key == "ai.error.busy"
    with app.test_request_context():
        assert "busy" in t(exc.message_key) and "key" not in t(exc.message_key)


GEMINI_429 = json.dumps([{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
    {"@type": "type.googleapis.com/google.rpc.Help"},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "79674s"}]}}]).encode()


@pytest.mark.parametrize(("error", "seconds"), [
    (_http_error(429, GEMINI_429), 79675),
    (_http_error(429, b"", {"Retry-After": "120"}), 120),
    (_http_error(429, b"<html>busy</html>"), None),
    (_http_error(429, b'{"error": {"details": [{"retryDelay": "soon"}]}}'), None),
])
def test_quota_error_says_how_long_to_wait(error, seconds):
    with pytest.raises(AIError) as info:
        OpenAICompatibleProvider(GEMINI, "m", "k", opener=Opener(exc=error)).check()
    assert info.value.code == "quota" and info.value.retry_after == seconds


def test_quota_message_carries_the_wait():
    from rolecard.i18n import translate
    assert AIError("quota").message_key == "ai.error.quota"
    key = AIError("quota", retry_after=79675).message_key
    assert key == ["ai.error.quota_wait", {"hours": 22, "minutes": 8}]
    assert "22 h 8 min" in translate("en", key[0], **key[1])
    assert "dentro de 22 h 8 min" in translate("es", key[0], **key[1])
