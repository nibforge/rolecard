import tomllib

import pytest

from rolecard.ai import AIError, FakeProvider
from rolecard.ai.base import ERROR_CODES
from rolecard.i18n import catalogue

ES = {"Accept-Language": "es-ES"}


def form(csrf, **values):
    data = {"csrf_token": csrf, "provider": "openai", "base_url": "http://localhost:11434/v1",
            "model": "llama3.1:8b", "timeout": "90", "api_key": ""}
    data.update(values)
    return data


@pytest.fixture(autouse=True)
def no_env_key(monkeypatch):
    monkeypatch.delenv("ROLECARD_OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("rolecard.views.settings.find_claude", lambda: None)
    monkeypatch.setattr("rolecard.ai.find_claude", lambda: None)


def saved(data_dir):
    return tomllib.loads((data_dir / "config.toml").read_text(encoding="utf-8"))


def test_page_renders_in_spanish(client):
    page = client.get("/settings", headers=ES).get_data(as_text=True)
    assert "Probar conexión" in page and "No encontrado en este equipo." in page
    assert 'aria-current="page"' in page


def test_save_writes_config_and_keeps_key_secret(client, csrf, data_dir, app):
    resp = client.post("/settings", data=form(csrf, api_key="sk-secret-1"))
    assert resp.status_code == 302
    ai = saved(data_dir)["ai"]
    assert ai == {"provider": "openai", "base_url": "http://localhost:11434/v1",
                  "model": "llama3.1:8b", "api_key": "sk-secret-1", "timeout": 90}
    assert app.config["ROLECARD"]["ai"]["api_key"] == "sk-secret-1"
    page = client.get("/settings").get_data(as_text=True)
    assert "sk-secret-1" not in page and "Configured. Leave empty to keep it." in page


def test_empty_key_keeps_the_saved_one_and_clear_removes_it(client, csrf, data_dir):
    client.post("/settings", data=form(csrf, api_key="sk-1"))
    client.post("/settings", data=form(csrf, model="other"))
    assert saved(data_dir)["ai"]["api_key"] == "sk-1"
    client.post("/settings", data=form(csrf, clear_key="1"))
    assert saved(data_dir)["ai"]["api_key"] == ""


def test_env_key_is_reported_and_field_disabled(client, monkeypatch):
    monkeypatch.setenv("ROLECARD_OPENAI_API_KEY", "sk-env")
    page = client.get("/settings").get_data(as_text=True)
    assert "ROLECARD_OPENAI_API_KEY" in page and "sk-env" not in page
    assert "disabled" in page


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"provider": "evil"}, "Choose one of the providers."),
        ({"base_url": "javascript:alert(1)"}, "Write a full http:// or https:// address."),
        ({"timeout": "0"}, "A whole number between 1 and 3600."),
        ({"timeout": "abc"}, "A whole number between 1 and 3600."),
        ({"model": "m" * 501}, "Too long"),
    ],
)
def test_invalid_values_are_rejected_and_nothing_saved(client, csrf, data_dir, values, message):
    before = (data_dir / "config.toml").read_text(encoding="utf-8")
    resp = client.post("/settings", data=form(csrf, **values))
    assert resp.status_code == 400
    page = resp.get_data(as_text=True)
    assert message in page and 'aria-invalid="true"' in page
    assert (data_dir / "config.toml").read_text(encoding="utf-8") == before


def test_save_needs_csrf(client, data_dir):
    resp = client.post("/settings", data=form("wrong"))
    assert resp.status_code == 400
    assert saved(data_dir)["ai"]["provider"] == "auto"


def test_connection_test_ok(client, csrf, app):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider('{"ok": true}')
    headers = {"HX-Request": "true", **ES}
    resp = client.post("/settings/test", data={"csrf_token": csrf}, headers=headers)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "Conexión correcta" in body and "<html" not in body


def test_connection_test_error_without_htmx_renders_page(client, csrf, app):
    app.config["AI_PROVIDER_FACTORY"] = lambda: FakeProvider([AIError("network")])
    body = client.post("/settings/test", data={"csrf_token": csrf}).get_data(as_text=True)
    assert "Cannot reach the AI service" in body and "<html" in body


def test_connection_test_without_provider(client, csrf):
    body = client.post("/settings/test", data={"csrf_token": csrf}).get_data(as_text=True)
    assert "No AI provider is configured." in body


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_ai_error_and_provider_has_text(lang):
    keys = catalogue(lang)
    for code in ERROR_CODES:
        assert f"ai.error.{code}" in keys
    for name in ("auto", "claude", "openai", "none"):
        assert f"ai.provider.{name}" in keys
        assert f"settings.provider_help.{name}" in keys


def sources_form(csrf, **values):
    data = {"csrf_token": csrf, "enabled_remotive": "1", "adzuna_country": "es",
            "adzuna_app_id": "", "adzuna_app_key": ""}
    data.update(values)
    return data


@pytest.fixture
def no_adzuna_env(monkeypatch):
    monkeypatch.delenv("ROLECARD_ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ROLECARD_ADZUNA_APP_KEY", raising=False)


def test_sources_save_enables_and_keeps_keys_secret(client, csrf, data_dir, app, no_adzuna_env):
    resp = client.post("/settings/sources", data=sources_form(
        csrf, enabled_adzuna="1", adzuna_app_id="id-123", adzuna_app_key="key-secret-9",
        adzuna_country="gb"))
    assert resp.status_code == 302
    src = saved(data_dir)["sources"]
    assert src == {"enabled": "remotive,adzuna", "adzuna_app_id": "id-123",
                   "adzuna_app_key": "key-secret-9", "adzuna_country": "gb"}
    page = client.get("/settings").get_data(as_text=True)
    assert "key-secret-9" not in page and "id-123" not in page
    assert page.count("Configured. Leave empty to keep it.") == 2
    assert 'value="gb" selected' in page


def test_sources_missing_key_is_reported(client, no_adzuna_env, csrf):
    client.post("/settings/sources", data=sources_form(csrf, enabled_adzuna="1"))
    page = client.get("/settings", headers=ES).get_data(as_text=True)
    assert "Falta la clave." in page and "Lista." in page


def test_sources_empty_key_keeps_and_clear_removes(client, csrf, data_dir, no_adzuna_env):
    client.post("/settings/sources", data=sources_form(csrf, adzuna_app_key="k1"))
    client.post("/settings/sources", data=sources_form(csrf))
    assert saved(data_dir)["sources"]["adzuna_app_key"] == "k1"
    client.post("/settings/sources", data=sources_form(csrf, clear_adzuna_app_key="1"))
    assert saved(data_dir)["sources"]["adzuna_app_key"] == ""


def test_sources_env_key_disables_field(client, monkeypatch):
    monkeypatch.setenv("ROLECARD_ADZUNA_APP_KEY", "env-secret")
    page = client.get("/settings").get_data(as_text=True)
    assert "ROLECARD_ADZUNA_APP_KEY" in page and "env-secret" not in page


@pytest.mark.parametrize("bad", [{"adzuna_country": "xx"}, {"adzuna_app_id": "x" * 501}])
def test_sources_rejects_bad_input(client, csrf, data_dir, bad, no_adzuna_env):
    before = (data_dir / "config.toml").read_text(encoding="utf-8")
    assert client.post("/settings/sources", data=sources_form(csrf, **bad)).status_code == 400
    assert (data_dir / "config.toml").read_text(encoding="utf-8") == before


def test_sources_requires_csrf(client):
    assert client.post("/settings/sources", data={"enabled_remotive": "1"}).status_code == 400


@pytest.mark.parametrize(("theme", "attr"), [
    ("system", None), ("light", 'data-theme="light"'), ("dark", 'data-theme="dark"')])
def test_theme_from_config_sets_data_theme(app, client, theme, attr):
    app.config["ROLECARD"]["ui"]["theme"] = theme
    html = client.get("/").get_data(as_text=True)
    head = html[:html.index(">", html.index("<html"))]
    assert ("data-theme" in head) is (attr is not None)
    if attr:
        assert attr in head


def test_ui_language_and_theme_are_saved_and_applied(client, csrf, data_dir):
    page = client.get("/settings", headers=ES).get_data(as_text=True)
    assert "Idioma y apariencia" in page and 'class="rc-switch"' in page
    assert page.index('id="adzuna_app_id"') > page.index('id="enabled_adzuna"')
    resp = client.post("/settings/ui", data={"csrf_token": csrf, "language": "es",
                                             "theme": "dark"})
    assert resp.status_code == 302 and resp.location.endswith("#apariencia")
    assert saved(data_dir)["ui"] == {"language": "es", "theme": "dark"}
    page = client.get("/settings").get_data(as_text=True)  # no Accept-Language: forced es
    assert '<html lang="es" data-theme="dark">' in page
    assert 'value="dark" checked' in page


@pytest.mark.parametrize("bad", [{"language": "fr", "theme": "dark"},
                                 {"language": "", "theme": "neon"}])
def test_ui_rejects_unknown_values(client, csrf, data_dir, bad):
    resp = client.post("/settings/ui", data={"csrf_token": csrf, **bad})
    assert resp.status_code == 400
    assert saved(data_dir)["ui"] == {"language": "", "theme": "system"}


@pytest.mark.parametrize(("values", "claude", "in_use", "cloud"), [
    ({"provider": "auto"}, "/bin/claude", "OpenAI-compatible", False),  # Ollama wins
    ({"provider": "auto", "base_url": "", "model": ""}, "/bin/claude", "Claude Code", True),
    ({"provider": "openai", "base_url": "https://api.example.com/v1"}, None,
     "OpenAI-compatible", True),
])
def test_page_names_the_provider_in_use_and_warns_of_the_cloud(
        client, csrf, monkeypatch, values, claude, in_use, cloud):
    monkeypatch.setattr("rolecard.views.settings.find_claude", lambda: claude)
    monkeypatch.setattr("rolecard.ai.find_claude", lambda: claude)
    assert client.post("/settings", data=form(csrf, **values)).status_code == 302
    page = client.get("/settings").get_data(as_text=True)
    assert f"In use: {in_use}" in page
    assert ('id="provider-cloud"' in page) is cloud


def test_a_key_over_plain_http_is_no_provider_and_the_test_says_why(client, csrf, app):
    app.config["ROLECARD"]["ai"].update(provider="openai", model="m",
                                        base_url="http://api.example.com/v1")
    app.config["ROLECARD"]["ai"]["api_key"] = "sk-test"
    assert client.get("/").status_code == 200
    body = client.post("/settings/test", data={"csrf_token": csrf}).get_data(as_text=True)
    assert "The API key is only sent over https" in body
