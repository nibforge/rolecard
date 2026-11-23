import io

import pytest

from rolecard import get_db
from rolecard.ai import AIError, FakeProvider
from rolecard.services.profile import get_profile, save_profile
from tests.conftest import BASE_URL
from tests.helpers import PROFILE, make_pdf, profile_json


@pytest.fixture
def fake(app):
    provider = FakeProvider(profile_json())
    app.config["AI_PROVIDER_FACTORY"] = lambda: provider
    return provider


def stored(app):
    with app.app_context():
        profile = get_profile(get_db())
        if profile is None:
            return None
        return profile.data, profile.needs_review, profile.source_text


def upload(client, csrf, data=None, name="cv.pdf", **extra):
    payload = {"csrf_token": csrf, "cv": (io.BytesIO(make_pdf() if data is None else data), name)}
    payload.update(extra)
    return client.post("/profile/upload", data=payload, content_type="multipart/form-data")


def test_upload_extracts_and_marks_for_review(client, csrf, app, fake):
    resp = upload(client, csrf)
    assert resp.status_code == 302
    data, needs_review, source = stored(app)
    assert needs_review and data["basics"]["name"] == "Ana Test Example"
    assert "Acme Data" in source and "Acme Data" in fake.prompts[0]
    page = client.get("/profile", headers={"Accept-Language": "es"}).get_data(as_text=True)
    assert "Revisa tu perfil." in page and 'value="Ana Test Example"' in page


def test_bad_file_keeps_previous_profile(client, csrf, app, fake):
    upload(client, csrf)
    before = stored(app)
    resp = upload(client, csrf, data=b"%PDF-1.4 broken", replace="1")
    assert resp.status_code == 302 and stored(app) == before
    assert "could not be read" in client.get("/profile").get_data(as_text=True)


def test_replacing_needs_confirmation(client, csrf, app, fake):
    upload(client, csrf)
    page = client.get("/profile").get_data(as_text=True)
    assert 'name="replace"' in page
    fake._answers = [profile_json(skills=["Rust"])]
    upload(client, csrf)
    assert stored(app)[0]["skills"] == ["Python", "SQL"]
    upload(client, csrf, replace="1")
    assert stored(app)[0]["skills"] == ["Rust"]


@pytest.mark.parametrize("answer", [AIError("timeout"), '{"basics": {}}', "not json"])
def test_ai_failure_saves_nothing(client, csrf, app, answer):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([answer])
    upload(client, csrf)
    assert stored(app) is None


def test_without_provider_profile_is_filled_by_hand(client, csrf, app):
    app.config["AI_PROVIDER_FACTORY"] = lambda: None
    page = client.get("/profile").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' not in page and "fill in your profile by hand" in page
    resp = upload(client, csrf)
    assert resp.status_code == 302 and stored(app) is None
    resp = client.post("/profile", data={"csrf_token": csrf, "basics-name": "Ana",
                                         "experience-1-role": "Dev", "skills": "Go"})
    assert resp.status_code == 302
    data, needs_review, _ = stored(app)
    assert not needs_review and data["experience"][0]["role"] == "Dev"


def test_saving_clears_review_mark_and_keeps_source(client, csrf, app, fake):
    upload(client, csrf)
    client.post("/profile", data={"csrf_token": csrf, "basics-name": "Ana B"})
    data, needs_review, source = stored(app)
    assert data["basics"]["name"] == "Ana B" and not needs_review and "Acme" in source


def test_invalid_form_shows_errors_and_saves_nothing(client, csrf, app):
    resp = client.post("/profile", data={"csrf_token": csrf, "basics-name": "",
                                         "basics-email": "bad", "experience-1-role": "Kept"})
    page = resp.get_data(as_text=True)
    assert resp.status_code == 400 and 'aria-invalid="true"' in page
    assert 'value="Kept"' in page and stored(app) is None


def test_delete(client, csrf, app):
    with app.app_context():
        save_profile(get_db(), PROFILE)
    page = client.get("/profile").get_data(as_text=True)
    assert "data-confirm" in page
    client.post("/profile/delete", data={"csrf_token": csrf})
    assert stored(app) is None


def test_profile_text_is_escaped(client, app):
    evil = dict(PROFILE, basics=dict(PROFILE["basics"], name='<script>alert(1)</script>'))
    with app.app_context():
        save_profile(get_db(), evil)
    page = client.get("/profile").get_data(as_text=True)
    assert "<script>alert(1)" not in page and "&lt;script&gt;" in page


def test_repeatable_entry_templates_exist(client):
    page = client.get("/profile").get_data(as_text=True)
    for section in ("experience", "projects", "education", "languages"):
        assert f'data-repeat-template="{section}"' in page
        assert f'data-repeat-add="{section}"' in page
    assert 'name="experience-__new__-role"' in page


def test_ai_field_paths_are_truncated_in_the_session(client, csrf, app, monkeypatch):
    errors = tuple((f"unexpected.{'k' * 3000}{n}", "unexpected") for n in range(12))

    def reject(text, provider):
        raise AIError("invalid", "bad", errors=errors)

    monkeypatch.setattr("rolecard.services.profile.extract_profile", reject)
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([])
    upload(client, csrf)
    with client.session_transaction(base_url=BASE_URL) as session:
        shown = [m for cat, m in session["_flashes"] if cat == "campo"]
    assert len(shown) == 10 and all(len(path) == 80 for path, _ in shown)


def _panel(page, name):
    start = page.index(f'data-tab-panel="{name}"')
    return page[page.rindex("<section", 0, start):page.index("</section>", start)]


def test_tab_is_chosen_by_query_and_rendered_on_the_server(client, app):
    with app.app_context():
        save_profile(get_db(), PROFILE)
    page = client.get("/profile?tab=experience").get_data(as_text=True)
    assert 'data-tab="experience" aria-current="page"' in page
    assert "hidden" not in _panel(page, "experience").split(">", 1)[0]
    assert "hidden" in _panel(page, "basics").split(">", 1)[0]
    assert 'value="Acme Data"' in page and 'name="basics-name"' in page  # every tab's fields
    assert "<details" in page and 'href="/profile?tab=skills"' in page
    bogus = client.get("/profile?tab=bogus").get_data(as_text=True)
    assert 'data-tab="basics" aria-current="page"' in bogus


def test_saving_from_one_tab_keeps_every_field_and_returns_to_it(client, csrf, app):
    resp = client.post("/profile", data={
        "csrf_token": csrf, "tab": "education", "basics-name": "Ana",
        "experience-1-role": "Dev", "education-1-degree": "BSc", "languages-1-language": "en",
        "skills": "Go, SQL"})
    assert resp.status_code == 302 and resp.location.endswith("/profile?tab=education")
    data, _, _ = stored(app)
    assert data["basics"]["name"] == "Ana" and data["experience"][0]["role"] == "Dev"
    assert data["education"][0]["degree"] == "BSc" and data["skills"] == ["Go", "SQL"]
    assert data["languages"][0]["language"] == "en"


def test_errors_open_the_tab_of_the_first_bad_field(client, csrf):
    page = client.post("/profile", data={"csrf_token": csrf, "tab": "experience",
                                         "basics-name": ""}).get_data(as_text=True)
    assert 'data-tab="basics" aria-current="page"' in page
