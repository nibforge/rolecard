"""What protects the user's data on the way to the AI: whether a provider is a cloud
service, no key over plain http, and a cap on the answer's size."""

import pytest

from rolecard.ai import AIError, is_cloud
from rolecard.ai.openai_compat import MAX_ANSWER, OpenAICompatibleProvider
from tests.test_ai_providers import OPENAI, Opener, settings


@pytest.mark.parametrize(("ai", "kind", "expected"), [
    (OPENAI, "openai", False),
    ({"base_url": "http://127.0.0.1:1234/v1"}, "openai", False),
    ({"base_url": "https://api.openai.com/v1"}, "openai", True),
    ({}, "claude", True),
    ({}, "none", False),
])
def test_is_cloud(ai, kind, expected):
    assert is_cloud(settings(**ai), kind) is expected


@pytest.mark.parametrize(("url", "key", "ok"), [
    ("http://api.example.com/v1", "sk", False),   # the key would travel unencrypted
    ("http://api.example.com/v1", "", True),
    ("http://127.0.0.1:11434/v1", "sk", True),
    ("http://localhost:1234/v1", "sk", True),
    ("https://api.example.com/v1", "sk", True),
    ("http://[::1]:1234/v1", "sk", True),
    ("http://127.evil.com/v1", "sk", False),       # a name, not the loopback address
    ("http://127.0.0.1.nip.io/v1", "sk", False),
])
def test_a_key_is_never_sent_over_plain_http_to_another_machine(url, key, ok):
    if ok:
        OpenAICompatibleProvider(url, "m", key)
    else:
        with pytest.raises(AIError) as info:
            OpenAICompatibleProvider(url, "m", key)
        assert info.value.code == "insecure"


def test_an_oversized_answer_is_refused():
    opener = Opener(b"x" * (MAX_ANSWER + 1))
    with pytest.raises(AIError) as info:
        OpenAICompatibleProvider("https://api.example/v1", "m", "k", opener=opener).check()
    assert info.value.code == "failed"
