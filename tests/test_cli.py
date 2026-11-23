import pytest

from rolecard import cli
from rolecard.config import ConfigError


def always_free(port):
    return True


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


def test_starts_on_default_port_and_opens_browser(tmp_path, capsys):
    serve, browser = Recorder(), Recorder()
    code = cli.main(
        ["--data-dir", str(tmp_path / "d")], serve=serve, open_browser=browser, is_free=always_free
    )
    assert code == 0
    app, port = serve.calls[0]
    assert port == 8765
    assert app.config["ALLOWED_HOSTS"] == {"127.0.0.1:8765", "localhost:8765"}
    assert browser.calls == [("http://127.0.0.1:8765/",)]
    assert (tmp_path / "d" / "rolecard.sqlite3").exists()
    assert "http://127.0.0.1:8765/" in capsys.readouterr().out


def test_no_browser_and_next_free_port(tmp_path):
    serve, browser = Recorder(), Recorder()
    code = cli.main(
        ["--data-dir", str(tmp_path), "--no-browser"],
        serve=serve,
        open_browser=browser,
        is_free=lambda p: p >= 8767,
        is_running=lambda p: False,
    )
    assert code == 0
    assert serve.calls[0][1] == 8767
    assert browser.calls == []


def test_data_dir_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLECARD_HOME", str(tmp_path / "env"))
    serve = Recorder()
    cli.main(["--no-browser"], serve=serve, is_free=lambda p: True)
    assert serve.calls[0][0].config["DATA_DIR"] == (tmp_path / "env").resolve()


def test_bad_config_exits_with_one_line(tmp_path, capsys):
    (tmp_path / "config.toml").write_text("[ai\n")
    serve = Recorder()
    args = ["--data-dir", str(tmp_path), "--no-browser"]
    code = cli.main(args, serve=serve, is_free=always_free)
    err = capsys.readouterr().err
    assert code == 2
    assert serve.calls == []
    assert err.startswith("rolecard: ") and err.count("\n") == 1
    assert "Traceback" not in err


def test_busy_requested_port_is_an_error(tmp_path, capsys):
    code = cli.main(
        ["--data-dir", str(tmp_path), "--port", "9000", "--no-browser"],
        serve=Recorder(),
        is_free=lambda p: False,
    )
    assert code == 2
    assert "9000" in capsys.readouterr().err


def test_choose_port_rules():
    assert cli.choose_port(9100, lambda p: True) == 9100
    with pytest.raises(ConfigError, match="out of range"):
        cli.choose_port(70000, lambda p: True)
    with pytest.raises(ConfigError, match="no free port"):
        cli.choose_port(None, lambda p: False)


def test_port_is_free_detects_a_bound_socket():
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        assert cli.port_is_free(sock.getsockname()[1]) is False


def test_server_error_is_one_line(tmp_path, capsys):
    def failing_serve(app, port):
        raise OSError(98, "Address already in use")

    args = ["--data-dir", str(tmp_path), "--no-browser"]
    code = cli.main(args, serve=failing_serve, is_free=always_free)
    assert code == 2
    assert "Address already in use" in capsys.readouterr().err


def test_already_running_only_opens_the_browser(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "system_language", lambda: "en")
    monkeypatch.delenv("ROLECARD_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    serve, browser = Recorder(), Recorder()
    code = cli.main([], serve=serve, open_browser=browser,
                    is_free=lambda p: False, is_running=lambda p: p == 8765)
    assert code == 0
    assert serve.calls == []
    assert browser.calls == [("http://127.0.0.1:8765/",)]
    assert "already running at http://127.0.0.1:8765/" in capsys.readouterr().out
    assert not (tmp_path / ".rolecard").exists()


@pytest.mark.parametrize("use_env", [False, True])
def test_other_data_dir_never_reuses_a_running_rolecard(tmp_path, monkeypatch, use_env):
    monkeypatch.setattr(cli, "system_language", lambda: "en")
    argv = ["--no-browser"]
    if use_env:
        monkeypatch.setenv("ROLECARD_HOME", str(tmp_path))
    else:
        monkeypatch.delenv("ROLECARD_HOME", raising=False)
        argv += ["--data-dir", str(tmp_path)]
    serve = Recorder()
    code = cli.main(argv, serve=serve, open_browser=Recorder(),
                    is_free=lambda p: p != 8765, is_running=lambda p: p == 8765)
    assert code == 0
    assert serve.calls and serve.calls[0][1] == 8766


def test_console_message_in_the_system_language(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "system_language", lambda: "es")
    shutdown = Recorder()
    serve = Recorder()
    cli.main(["--data-dir", str(tmp_path), "--no-browser"], serve=serve,
             is_free=always_free, shutdown=shutdown)
    out = capsys.readouterr().out
    assert ("rolecard está abierto en tu navegador en http://127.0.0.1:8765/. No cierres esta "
            "ventana mientras lo uses. Para salir, ciérrala o pulsa Salir en la app.") in out
    assert serve.calls[0][0].config["SHUTDOWN"] is shutdown


@pytest.mark.parametrize("env,lang", [
    ({"LANG": "es_ES.UTF-8"}, "es"), ({"LC_ALL": "en_US.UTF-8", "LANG": "es_ES"}, "en"),
    ({"LANG": "fr_FR.UTF-8"}, "en"),
])
def test_system_language_from_the_environment(env, lang):
    assert cli.system_language(env, platform="linux") == lang


def test_rolecard_is_running_checks_the_server_header():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def version_string(self):
            return self.server.ident

        def log_message(self, *args):
            pass

    for ident, expected in (("rolecard", True), ("other", False)):
        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.ident = ident
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        assert cli.rolecard_is_running(server.server_address[1]) is expected
        thread.join(5)
        server.server_close()
    assert cli.rolecard_is_running(cli.choose_port(None)) is False  # nothing listening
