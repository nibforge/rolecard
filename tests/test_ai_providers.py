import io
import json
import os
import subprocess
import urllib.error
from copy import deepcopy

import pytest

from rolecard.ai import AIError, FakeProvider, api_key, get_provider, resolve
from rolecard.ai.base import PING_SCHEMA, parse_json_object
from rolecard.ai.claude_code import ClaudeCodeProvider, child_env
from rolecard.ai.openai_compat import OpenAICompatibleProvider
from rolecard.config import DEFAULTS

# --- parsing and validation ------------------------------------------------------


@pytest.mark.parametrize("raw", ['{"ok": true}', '  {"ok": true}\n', '```json\n{"ok": true}\n```'])
def test_parse_accepts_a_bare_object(raw):
    assert parse_json_object(raw) == {"ok": True}


@pytest.mark.parametrize(
    "raw",
    ['Sure! {"ok": true}', '{"ok": true} Done.', "[1]", "not json", '{"ok": tru}', "",
     'Here:\n```json\n{"ok": true}\n```'],
)
def test_parse_rejects_text_around_or_non_objects(raw):
    with pytest.raises(AIError) as info:
        parse_json_object(raw)
    assert info.value.code == "not_json"


def test_complete_json_validates_against_the_schema():
    assert FakeProvider('{"ok": true}').complete_json("p", PING_SCHEMA) == {"ok": True}
    for bad in ('{"ok": true, "extra": 1}', '{"ok": "yes"}', "{}"):
        with pytest.raises(AIError) as info:
            FakeProvider(bad).complete_json("p", PING_SCHEMA)
        assert info.value.code == "invalid"


def test_fake_provider_records_prompts_and_raises():
    fake = FakeProvider(['{"ok": true}', AIError("timeout")])
    fake.check()
    with pytest.raises(AIError):
        fake.check()
    assert len(fake.prompts) == 2


def test_unknown_error_code_is_a_bug():
    with pytest.raises(ValueError):
        AIError("whatever")


# --- Claude Code -------------------------------------------------------------------


class Runner:
    def __init__(self, stdout="", returncode=0, exc=None):
        self.stdout, self.returncode, self.exc = stdout, returncode, exc
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        self.cwd_contents = os.listdir(kwargs["cwd"])
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


def envelope(result, is_error=False):
    return json.dumps({"type": "result", "is_error": is_error, "result": result})


def test_claude_runs_without_tools_shell_or_prompt_in_argv():
    runner = Runner(envelope('{"ok": true}'))
    provider = ClaudeCodeProvider(timeout=7, executable="/bin/claude", runner=runner)
    provider.complete_json("SECRET CV TEXT", PING_SCHEMA)
    cmd, kwargs = runner.calls[0]
    assert cmd[0] == "/bin/claude" and "-p" in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
                 "--safe-mode"):
        assert flag in cmd
    assert not any("SECRET" in part for part in cmd)
    assert kwargs["input"] == "SECRET CV TEXT"
    assert kwargs["shell"] is False and kwargs["timeout"] == 7
    assert runner.cwd_contents == [] and not os.path.exists(kwargs["cwd"])
    assert "ROLECARD_OPENAI_API_KEY" not in kwargs["env"]


def test_claude_gets_only_the_allowed_environment():
    env = child_env({"PATH": "/bin", "USERPROFILE": "C:/u", "LC_ALL": "C",
                     "ANTHROPIC_API_KEY": "a", "CLAUDE_CONFIG_DIR": "/c",
                     "ROLECARD_OPENAI_API_KEY": "sk", "ROLECARD_ADZUNA_APP_KEY": "z",
                     "ADZUNA_APP_KEY": "z", "GITHUB_TOKEN": "g", "AWS_SECRET_ACCESS_KEY": "s"})
    assert sorted(env) == ["ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "LC_ALL", "PATH",
                           "USERPROFILE"]


def test_claude_code_can_bill_an_anthropic_api_key_but_never_gets_rolecards():
    """docs/ai.*: the user's own ANTHROPIC_API_KEY reaches Claude Code unchanged (pay per
    use); rolecard neither stores it nor passes its own keys instead."""
    env = child_env({"ANTHROPIC_API_KEY": "user-key", "ROLECARD_OPENAI_API_KEY": "sk"})
    assert env == {"ANTHROPIC_API_KEY": "user-key"}


@pytest.mark.parametrize(
    ("runner", "code"),
    [
        (Runner(exc=FileNotFoundError("claude")), "not_installed"),
        (Runner(exc=subprocess.TimeoutExpired("claude", 7)), "timeout"),
        (Runner(returncode=1), "failed"),
        (Runner("not json"), "failed"),
        (Runner(envelope("x", is_error=True)), "failed"),
        (Runner(json.dumps({"result": 3})), "failed"),
        (Runner(envelope("I cannot do that")), "not_json"),
    ],
)
def test_claude_failures_become_ai_errors(runner, code):
    provider = ClaudeCodeProvider(executable="claude", runner=runner)
    with pytest.raises(AIError) as info:
        provider.complete_json("p", PING_SCHEMA)
    assert info.value.code == code


def test_claude_not_on_path(monkeypatch):
    monkeypatch.setattr("rolecard.ai.claude_code.find_claude", lambda: None)
    with pytest.raises(AIError) as info:
        ClaudeCodeProvider(runner=Runner()).complete("p")
    assert info.value.code == "not_installed"


# --- OpenAI-compatible --------------------------------------------------------------


class Opener:
    def __init__(self, body=b"", exc=None):
        self.body, self.exc, self.requests = body, exc, []

    def __call__(self, req, timeout):
        self.requests.append((req, timeout))
        if self.exc:
            raise self.exc
        return io.BytesIO(self.body)


def chat(content):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def test_openai_sends_key_in_header_and_no_tools():
    opener = Opener(chat('{"ok": true}'))
    provider = OpenAICompatibleProvider("http://localhost:11434/v1/", "llama", "sk-123", 9, opener)
    provider.check()
    req, timeout = opener.requests[0]
    assert req.full_url == "http://localhost:11434/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer sk-123"
    assert "sk-123" not in req.full_url and timeout == 9
    body = json.loads(req.data)
    assert body["model"] == "llama" and "tools" not in body and "functions" not in body
    assert "sk-123" not in repr(provider)


def test_openai_without_key_sends_no_authorization():
    opener = Opener(chat('{"ok": true}'))
    OpenAICompatibleProvider("http://x/v1", "m", "", opener=opener).check()
    assert opener.requests[0][0].get_header("Authorization") is None


@pytest.mark.parametrize(
    ("opener", "code"),
    [
        (Opener(exc=urllib.error.HTTPError("u", 401, "no", {}, None)), "http"),
        (Opener(exc=urllib.error.URLError(ConnectionRefusedError())), "network"),
        (Opener(exc=urllib.error.URLError(TimeoutError())), "timeout"),
        (Opener(exc=TimeoutError()), "timeout"),
        (Opener(b"<html>"), "failed"),
        (Opener(json.dumps({"choices": []}).encode()), "failed"),
        (Opener(chat("Sure, here it is")), "not_json"),
    ],
)
def test_openai_failures_become_ai_errors(opener, code):
    provider = OpenAICompatibleProvider("https://api.example/v1", "m", "k", opener=opener)
    with pytest.raises(AIError) as info:
        provider.check()
    assert info.value.code == code


@pytest.mark.parametrize(("url", "model"), [("", "m"), ("ftp://x", "m"), ("http://x", "")])
def test_openai_needs_http_url_and_model(url, model):
    with pytest.raises(AIError) as info:
        OpenAICompatibleProvider(url, model)
    assert info.value.code == "not_configured"


# --- choosing ----------------------------------------------------------------------


def settings(**ai):
    cfg = deepcopy(DEFAULTS)
    cfg["ai"].update(ai)
    return cfg


OPENAI = {"base_url": "http://localhost:11434/v1", "model": "llama"}


@pytest.mark.parametrize(
    ("ai", "claude", "expected"),
    [
        ({}, "/bin/claude", "claude"),
        ({}, None, "none"),
        (OPENAI, None, "openai"),
        (OPENAI, "/bin/claude", "openai"),  # what the user set up wins over the PATH
        ({"provider": "claude"}, None, "claude"),
        ({"provider": "openai"}, "/bin/claude", "none"),
        ({"provider": "openai", **OPENAI}, "/bin/claude", "openai"),
        ({"provider": "none", **OPENAI}, "/bin/claude", "none"),
    ],
)
def test_resolve(ai, claude, expected):
    assert resolve(settings(**ai), which=lambda: claude) == expected


def test_get_provider_builds_the_right_class():
    assert isinstance(get_provider(settings(), {}, lambda: "/c"), ClaudeCodeProvider)
    provider = get_provider(settings(api_key="cfg", **OPENAI), {}, lambda: None)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert get_provider(settings(provider="none"), {}, lambda: "/c") is None


def test_env_key_wins_over_config():
    env = {"ROLECARD_OPENAI_API_KEY": "from-env"}
    assert api_key(settings(api_key="cfg"), env) == ("from-env", "env")
    assert api_key(settings(api_key="cfg"), {}) == ("cfg", "config")
    assert api_key(settings(), {}) == ("", "")


def test_openai_does_not_follow_redirects_with_the_key():
    """A 3xx from the endpoint is an error: the key never reaches the Location target."""
    import http.server
    import threading

    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen.append((self.path, self.headers.get("Authorization")))
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path.startswith("/v1/"):
                self.send_response(302)
                self.send_header("Location", "/stolen")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                body = chat('{"ok": true}')
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        do_GET = do_POST  # noqa: N815

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1"
        provider = OpenAICompatibleProvider(url, "m", "sk-secret", timeout=5)
        with pytest.raises(AIError) as err:
            provider.check()
    finally:
        server.shutdown()
    assert err.value.code == "http"
    assert [path for path, _ in seen] == ["/v1/chat/completions"]


