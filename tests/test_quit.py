"""The Quit button stops the local server and says so."""


def test_sidebar_has_a_quit_form_with_csrf(client):
    html = client.get("/").get_data(as_text=True)
    assert 'action="/quit"' in html
    form = html[html.index('action="/quit"'):]
    assert 'name="csrf_token"' in form[: form.index("</form>")]


def test_quit_shows_goodbye_and_calls_shutdown(app, client, csrf):
    calls = []
    app.config["SHUTDOWN"] = lambda: calls.append(True)
    res = client.post("/quit", data={"csrf_token": csrf}, headers={"Accept-Language": "es"})
    assert res.status_code == 200
    assert "rolecard se ha cerrado. Ya puedes cerrar esta pestaña." in res.get_data(as_text=True)
    assert calls == [True]


def test_quit_needs_csrf(app, client):
    calls = []
    app.config["SHUTDOWN"] = lambda: calls.append(True)
    assert client.post("/quit").status_code == 400
    assert calls == []


def test_quit_only_from_loopback(app, client, csrf):
    calls = []
    app.config["SHUTDOWN"] = lambda: calls.append(True)
    res = client.post("/quit", data={"csrf_token": csrf},
                      environ_overrides={"REMOTE_ADDR": "192.168.1.20"})
    assert res.status_code == 400
    assert calls == []


def test_quit_without_shutdown_still_answers(client, csrf):
    assert client.post("/quit", data={"csrf_token": csrf}).status_code == 200


def test_get_quit_does_nothing(client):
    assert client.get("/quit").status_code == 405
