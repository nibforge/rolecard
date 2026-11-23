"""Real CVs: optional fields that are empty or odd must not sink the whole reading."""

import io
import json
import logging

from rolecard import get_db
from rolecard.ai import FakeProvider
from rolecard.services.profile import get_profile
from tests.helpers import PROFILE, make_pdf


def _answer(**basics_changes) -> dict:
    data = json.loads(json.dumps(PROFILE))
    data["basics"].update(basics_changes)
    return data


def _upload(client, csrf, app, answer):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider(answer)
    return client.post("/profile/upload", data={
        "csrf_token": csrf, "cv": (io.BytesIO(make_pdf()), "cv.pdf"),
    }, content_type="multipart/form-data", follow_redirects=True)


def _stored(app):
    with app.app_context():
        profile = get_profile(get_db())
        return profile.data if profile else None


def test_empty_optional_fields_as_null_are_accepted(client, csrf, app):
    data = _answer(email=None, phone=None, links=None)
    data["experience"][0].update(end=None, location=None, highlights=["Built APIs", None])
    _upload(client, csrf, app, json.dumps(data))
    stored = _stored(app)
    assert stored["basics"]["email"] == "" and stored["basics"]["links"] == []
    assert stored["experience"][0]["end"] == ""
    assert stored["experience"][0]["highlights"] == ["Built APIs"]


def test_odd_value_in_optional_date_is_kept_as_text(client, csrf, app):
    data = _answer()
    data["experience"][0].update(start=2019, end="Present")
    data["education"] = [{"degree": "BSc", "institution": "Uni", "start": "?", "end": None}]
    _upload(client, csrf, app, json.dumps(data))
    stored = _stored(app)
    assert stored["experience"][0]["start"] == "2019"
    assert stored["experience"][0]["end"] == "Present"
    assert stored["education"][0]["start"] == "?"


def test_invalid_answer_lists_failing_fields_and_logs_its_shape(client, csrf, app, caplog):
    data = _answer(email=["a@b.es"], nickname="Ana")
    data["summary_text"] = "x" * 3000
    raw = json.dumps(data)
    with caplog.at_level(logging.WARNING, logger="rolecard.ai"):
        page = _upload(client, csrf, app, raw).get_data(as_text=True)
    assert _stored(app) is None
    assert "basics.email</code>: tipo de dato no válido" in page or \
        "basics.email</code>: invalid data type" in page
    assert "basics.nickname" in page and "summary_text" in page
    assert "a@b.es" not in page and "xxxxxxxxxx" not in page  # no AI content in the UI
    logged = caplog.text
    assert "basics.email" in logged and f"{len(raw)} chars" in logged
    assert "a@b.es" not in logged and "xxxxxxxxxx" not in logged


def test_not_json_answer_is_logged_without_its_text(client, csrf, app, caplog):
    with caplog.at_level(logging.WARNING, logger="rolecard.ai"):
        _upload(client, csrf, app, "Here is the profile: {}")
    assert "not_json" in caplog.text and "chars, sha256 " in caplog.text
    assert "Here is the profile" not in caplog.text


def test_rejected_answer_goes_to_the_local_log_file(client, csrf, app):
    _upload(client, csrf, app, "not json at all")
    log_file = app.config["DATA_DIR"] / "rolecard.log"
    logged = log_file.read_text(encoding="utf-8")
    assert "AI answer rejected (not_json)" in logged and "15 chars" in logged
    assert "not json at all" not in logged
