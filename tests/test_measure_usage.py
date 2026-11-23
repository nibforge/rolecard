"""scripts/measure_usage.py with simulated providers: no network, no real key."""

import importlib.util
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from rolecard.config import ENV_API_KEY

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "measure_usage.py"
SECRET = "fake-test-value-never-printed-123"


@pytest.fixture(scope="module")
def mu():
    spec = importlib.util.spec_from_file_location("measure_usage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_usage"] = module
    spec.loader.exec_module(module)
    return module


SCORE = {"score": 80, "summary": "Good match.", "met": ["Python"], "missing": [],
         "language": "en", "title": "Dev", "company": "Contoso", "location": "Remote"}


def fake_opener(seen, answer=SCORE, usage=None):
    usage = {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1500} \
        if usage is None else usage

    def open_(req, timeout):
        seen.append(req)
        body = {"choices": [{"message": {"content": json.dumps(answer)}}]}
        if usage:
            body["usage"] = usage
        return io.BytesIO(json.dumps(body).encode())
    return open_


def run(mu, capsys, argv, **kwargs):
    code = mu.main(argv, **kwargs)
    out = capsys.readouterr()
    return code, json.loads(out.out), out.out + out.err


ARGV = ["openai", "--base-url", "https://example.invalid/v1", "--model", "m",
        "--price-in", "0.30", "--price-out", "2.50", "--docs", "10"]


def test_reports_the_usage_the_provider_returns(mu, capsys, monkeypatch):
    monkeypatch.setenv(ENV_API_KEY, SECRET)
    seen = []
    code, report, text = run(mu, capsys, ARGV, opener=fake_opener(seen))
    assert code == 1  # only the score answer is valid for its schema
    assert {r["operation"] for r in report["rows"]} == {"read_cv", "score", "cv", "letter"}
    score_rows = [r for r in report["rows"] if r["operation"] == "score"]
    assert len(score_rows) == len(mu.OFFERS) and all(r["status"] == "ok" for r in score_rows)
    # thinking tokens (total - prompt) count as output
    assert report["per_operation"]["score"] == {"runs": len(mu.OFFERS), "input": 1000,
                                                "output": 500}
    assert SECRET not in text
    assert all(req.get_header("Authorization") == f"Bearer {SECRET}" for req in seen)


def test_cost_of_100_offers(mu):
    summary = {op: {"runs": 1, "input": 1000, "output": 500}
               for op in ("score", "cv", "letter")}
    cost = mu.cost_of_100(summary, 0.30, 2.50, 10)
    assert cost["input_tokens"] == 120 * 1000 and cost["output_tokens"] == 120 * 500
    assert cost["usd"] == round((120_000 * 0.30 + 60_000 * 2.50) / 1e6, 4)
    assert mu.cost_of_100({"score": summary["score"]}, 0.3, 2.5, 10) is None


def test_unreported_usage_is_not_invented(mu, capsys, monkeypatch):
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    _code, report, _text = run(mu, capsys, ARGV, opener=fake_opener([], usage={}))
    assert all("input" not in r for r in report["rows"])
    assert report["per_operation"] == {}
    assert report["cost_of_100_offers"] is None


def test_claude_envelope_usage(mu, capsys, monkeypatch):
    def runner(cmd, **kwargs):
        envelope = {"result": json.dumps(SCORE), "total_cost_usd": 0.01, "usage": {
            "input_tokens": 10, "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 1000, "output_tokens": 50}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(envelope), "")
    real = mu.ClaudeCodeProvider
    monkeypatch.setattr(mu, "ClaudeCodeProvider",
                        lambda **kw: real(executable="claude", **kw))
    _code, report, _text = run(mu, capsys, ["claude", "--timeout", "5"], runner=runner)
    assert report["per_operation"]["score"]["input"] == 1110
    assert report["per_operation"]["score"]["output"] == 50


def test_demo_cv_text_is_the_fictional_profile(mu):
    text = mu.demo_cv_text()
    assert "Alex Demo" in text and "Northwind Labs" in text
    assert "example.com" in text


def test_a_busy_server_is_retried_then_measured(mu):
    calls, waits = [], []
    good = fake_opener([])

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b""))
        return good(req, timeout)
    sink = []
    opener = mu.recording_opener(sink, flaky, waits=(1, 2, 3), sleep=waits.append)
    opener(urllib.request.Request("https://example.invalid"), timeout=1)
    assert waits == [1, 2] and sink == [{"input": 1000, "output": 500}]
    with pytest.raises(urllib.error.HTTPError):  # a 400 is not retried
        mu.recording_opener([], lambda req, timeout: (_ for _ in ()).throw(
            urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b""))),
            sleep=waits.append)(urllib.request.Request("https://example.invalid"), 1)
    assert waits == [1, 2]
