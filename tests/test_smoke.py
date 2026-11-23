from pathlib import Path

from rolecard import __version__, config, create_app, get_db
from tests.conftest import PORT


def test_home_responds(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "rolecard" in response.get_data(as_text=True)


def test_version_matches_version_file():
    root = Path(__file__).resolve().parent.parent
    assert (root / "VERSION").read_text().strip() == __version__


def test_factory_prepares_data_dir(data_dir):
    app = create_app(data_dir, port=PORT, testing=True)
    for name in (config.CONFIG_FILE, config.SECRET_FILE, config.DB_FILE):
        assert (data_dir / name).exists(), name
    assert app.secret_key == (data_dir / config.SECRET_FILE).read_text()
    # A second start reuses the same key and database.
    again = create_app(data_dir, port=PORT, testing=True)
    assert again.secret_key == app.secret_key


def test_404_and_unexpected_error_render_translated_pages(app, client):
    @app.get("/_boom")
    def boom():
        raise RuntimeError("secret detail")

    missing = client.get("/missing")
    assert missing.status_code == 404
    boom_response = client.get("/_boom")
    assert boom_response.status_code == 500
    body = boom_response.get_data(as_text=True)
    assert "Something went wrong" in body
    assert "secret detail" not in body


def test_db_session_per_request(app):
    with app.test_request_context():
        session = get_db()
        assert get_db() is session


def test_layout_loads_local_assets_only(client):
    page = client.get("/").get_data(as_text=True)
    assets = ("css/tokens.css", "css/componentes.css", "css/app.css", "js/htmx.min.js", "js/app.js")
    for asset in assets:
        assert f"/static/{asset}" in page
        assert client.get(f"/static/{asset}").status_code == 200
    assert "<script>" not in page and "style=" not in page and "https://" not in page
    assert '"includeIndicatorStyles":false' in page  # htmx must not inject inline styles


def test_navigation_only_lists_existing_pages(client):
    page = client.get("/").get_data(as_text=True)
    assert "/settings" in page and 'class="saltar"' in page


def test_inter_is_served_locally_with_its_license(client):
    css = client.get("/static/css/app.css").get_data(as_text=True)
    for weight in ("Regular", "Medium", "SemiBold"):
        assert f"../fonts/Inter-{weight}.woff2" in css
        assert client.get(f"/static/fonts/Inter-{weight}.woff2").status_code == 200
    assert client.get("/static/fonts/Inter.LICENSE.txt").status_code == 200
