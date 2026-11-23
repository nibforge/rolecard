"""Owner review of the redesign (004): filters apply on change, the job page saves on
change, the profile tabs hold only their own section, the key fields are wide and never
show a stored key."""

import re
import tomllib
from pathlib import Path

import pytest

from rolecard import get_db
from rolecard.ai import FakeProvider
from rolecard.services.profile import save_profile
from rolecard.views.profile import _error_tab
from tests.helpers import PROFILE

ES = {"Accept-Language": "es-ES"}
HX = {"HX-Request": "true"}
TEXT = "Acme Data seeks a backend developer: Python, SQL, Kubernetes. Hybrid in Valencia. " * 2
CSS = Path(__file__).resolve().parent.parent / "rolecard" / "static" / "css" / "app.css"


@pytest.fixture(autouse=True)
def no_env_keys(monkeypatch):
    for var in ("ROLECARD_OPENAI_API_KEY", "ROLECARD_ADZUNA_APP_ID", "ROLECARD_ADZUNA_APP_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("rolecard.views.settings.find_claude", lambda: None)


@pytest.fixture
def job(client, csrf, app):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([])
    client.post("/jobs", data={"csrf_token": csrf, "text": TEXT})
    return 1


def outside_noscript(page):
    return re.sub(r"<noscript>.*?</noscript>", "", page, flags=re.S)


@pytest.mark.parametrize("path", ["/board", "/jobs"])
def test_filters_apply_on_change_with_short_labels(client, job, path):
    page = client.get(path, headers=ES).get_data(as_text=True)
    start = page.index('role="search"')
    toolbar = page[start - 200:page.index("</form>", start)]
    assert 'hx-trigger="change, input delay:400ms from:#q, submit"' in toolbar
    assert ">Filtrar</button>" not in outside_noscript(toolbar)
    assert "Puntuación ≥</option>" in toolbar and "Puntuación ≥ 70</option>" in toolbar
    assert ">Sin puntuar</label>" in toolbar and ">Seguimiento vencido</label>" in toolbar
    assert 'class="rc-page rc-page--full"' in page


def test_job_page_saves_on_change_without_buttons(client, job):
    page = client.get(f"/jobs/{job}", headers=ES).get_data(as_text=True)
    for form_id in ("estado", "seguimiento-form", "idioma-docs", "datos"):
        tag = page[page.index(f'<form id="{form_id}"'):]
        tag = tag[:tag.index(">")]
        assert 'hx-trigger="change"' in tag and "data-autosave" in tag
        assert 'hx-select="#principal"' in tag
    visible = outside_noscript(page)
    for label in ("Guardar seguimiento", "Cambiar estado", "Guardar idioma", "Guardar datos"):
        assert label not in visible
    assert visible.count("data-saved") == 4


def test_autosave_does_not_flash_a_banner(client, csrf, job, app):
    resp = client.post(f"/jobs/{job}/tracking", headers={**HX, **ES}, follow_redirects=True,
                       data={"csrf_token": csrf, "notes": "Called HR", "follow_up_on": ""})
    assert resp.status_code == 200 and "Seguimiento guardado." not in resp.get_data(as_text=True)
    plain = client.post(f"/jobs/{job}/tracking", headers=ES, follow_redirects=True,
                        data={"csrf_token": csrf, "notes": "Again", "follow_up_on": ""})
    assert "Seguimiento guardado." in plain.get_data(as_text=True)


def _panel(page, name):
    start = page.index(f'data-tab-panel="{name}"')
    return page[page.rindex("<section", 0, start):page.index("</section>", start)]


def test_profile_tabs_hold_only_their_section(client, app):
    with app.app_context():
        save_profile(get_db(), PROFILE)
    page = client.get("/profile?tab=languages", headers=ES).get_data(as_text=True)
    assert 'data-tab="languages" aria-current="page"' in page and ">Idiomas" in page
    assert 'data-repeat-list="languages"' in _panel(page, "languages")
    assert 'data-repeat-list="languages"' not in _panel(page, "skills")
    assert 'id="subir-cv" hidden' in page  # empty forms take no gap under the tabs
    assert "[hidden] { display: none !important; }" in CSS.read_text(encoding="utf-8")
    assert _error_tab({"languages-1-language": "x"}) == "languages"
    assert _error_tab({"skills": "x"}) == "skills"


def test_key_fields_are_wide_and_never_show_a_stored_key(client, csrf, data_dir):
    client.post("/settings/sources", data={
        "csrf_token": csrf, "adzuna_country": "es",
        "adzuna_app_id": "id-QZXW", "adzuna_app_key": "S3CRETVALUE"})
    client.post("/settings", data={"csrf_token": csrf, "provider": "openai", "timeout": "90",
                                   "base_url": "", "model": "", "api_key": "sk-PRIVATE"})
    page = client.get("/settings", headers=ES).get_data(as_text=True)
    for secret in ("id-QZXW", "S3CRETVALUE", "sk-PRIVATE", "QZXW", "TVALUE"):
        assert secret not in page
    inputs = re.findall(r'<input[^>]*type="password"[^>]*>', page)
    assert len(inputs) == 3
    for tag in inputs:
        assert 'autocomplete="new-password"' in tag and 'spellcheck="false"' in tag
        assert "Guardada; no se muestra." in tag  # placeholder, never the value
        assert "value=" not in tag
    assert page.count('class="rc-field span-12"><label class="rc-label" for="adzuna_app') == 2


@pytest.mark.parametrize("bad", ["two words", "line\nbreak", "tab\tkey", "x" * 501])
def test_a_key_with_spaces_or_breaks_is_rejected(client, csrf, data_dir, bad):
    resp = client.post("/settings/sources", data={"csrf_token": csrf, "adzuna_country": "es",
                                                  "adzuna_app_key": bad})
    assert resp.status_code == 400
    ai = client.post("/settings", data={"csrf_token": csrf, "provider": "openai",
                                        "timeout": "90", "api_key": bad})
    assert ai.status_code == 400 and bad not in ai.get_data(as_text=True)
    config = data_dir / "config.toml"
    if config.exists():
        text = tomllib.loads(config.read_text(encoding="utf-8"))
        assert text["sources"].get("adzuna_app_key", "") == ""
        assert text["ai"].get("api_key", "") == ""


@pytest.mark.parametrize("path", ["/settings", "/profile"])
def test_own_h1_flag_is_not_printed_and_in_use_names_the_provider(client, path):
    page = client.get(path).get_data(as_text=True)
    header = page[page.index('<header class="rc-header">'):page.index("</header>")]
    assert "yes" not in header
    if path == "/settings":
        assert "ai.provider.settings" not in page
        assert re.search(r"In use: (Claude Code|OpenAI-compatible|None)<", page)


def test_follow_up_panel_keeps_source_and_link_in_its_own_rows(client, job):
    page = client.get(f"/jobs/{job}").get_data(as_text=True)
    panel = page[page.index('aria-labelledby="seguimiento"'):]
    panel = panel[:panel.index("</section>")]
    tracking = panel[panel.index('id="seguimiento-form"'):panel.index("</form>")]
    assert tracking.count("<span") == tracking.count("</span>")  # nothing spills into <dl>
    assert '</form>\n    <dl class="rc-props">' in panel
