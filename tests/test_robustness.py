"""Edge cases found in review: bad ports, broken HTTP, hung subprocesses, races."""

import http.client
import subprocess
import sys
import time

import pytest
from werkzeug.datastructures import MultiDict

from rolecard import get_db
from rolecard.ai import AIError
from rolecard.ai.claude_code import run_tree
from rolecard.ai.openai_compat import OpenAICompatibleProvider, valid_base_url
from rolecard.ai.prompts import delimit
from rolecard.models import Job
from rolecard.services import jobs as svc
from rolecard.services.board import BoardFilters
from rolecard.services.dedup import is_web_url, url_key

TEXT = "Backend developer wanted: Python and SQL, hybrid in Valencia. " * 3


@pytest.mark.parametrize("url", ["http://a.com:99999/x", "http://a.com:abc/x"])
def test_bad_port_is_not_a_web_url(url):
    assert not is_web_url(url) and url_key(url) is None
    assert not valid_base_url(url)


def test_bad_port_offer_url_gives_form_error(client, csrf):
    response = client.post("/jobs", data={"csrf_token": csrf, "text": TEXT,
                                          "url": "http://a.com:99999/x"})
    assert response.status_code == 400


@pytest.mark.parametrize("exc", [http.client.IncompleteRead(b""), http.client.InvalidURL("x")])
def test_http_client_errors_become_ai_errors(exc):
    def opener(*_args, **_kwargs):
        raise exc

    provider = OpenAICompatibleProvider("http://127.0.0.1:1/v1", "m", opener=opener)
    with pytest.raises(AIError):
        provider.complete("hi")


def test_run_tree_timeout_does_not_hang(tmp_path):
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_tree([sys.executable, "-c", "import time; time.sleep(30)"], input="",
                 cwd=str(tmp_path), timeout=1)
    assert time.monotonic() - start < 15


def test_run_tree_decodes_bad_utf8(tmp_path):
    code = "import sys; sys.stdout.buffer.write(b'ok' + bytes([255]))"
    proc = run_tree([sys.executable, "-c", code], input="", cwd=str(tmp_path), timeout=30)
    assert proc.returncode == 0 and proc.stdout.startswith("ok")


def test_concurrent_duplicate_insert_returns_duplicate(app, monkeypatch):
    with app.app_context():
        db = get_db()
        first = svc.create_job(db, text=TEXT)
        monkeypatch.setattr(svc, "find_duplicate", _none_then(svc.find_duplicate))
        second = svc.create_job(db, text=TEXT)
        assert isinstance(second, svc.Duplicate) and second.job.id == first.id
        assert db.query(Job).count() == 1


def _none_then(real):
    calls = []

    def fake(*args, **kwargs):
        calls.append(1)
        return None if len(calls) == 1 else real(*args, **kwargs)

    return fake


def test_non_ascii_digit_min_score_is_ignored():
    assert BoardFilters.from_args(MultiDict({"min": "²"})).min_score is None


def test_spaced_closing_tag_is_neutralised():
    assert delimit("x < /untrusted_document> y").count("</untrusted_document>") == 1
