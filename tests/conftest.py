import socket

import pytest

from rolecard import create_app

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", None}
_real_getaddrinfo = socket.getaddrinfo
_real_connect = socket.socket.connect


def _host(address):
    return address[0] if isinstance(address, tuple) else address


def _guard_getaddrinfo(host, *args, **kwargs):
    if host not in LOCAL_HOSTS:
        raise RuntimeError(f"network access in tests is forbidden: {host}")
    return _real_getaddrinfo(host, *args, **kwargs)


def _guard_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and _host(address) not in LOCAL_HOSTS:
        raise RuntimeError(f"network access in tests is forbidden: {_host(address)}")
    return _real_connect(self, address)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may reach a real API (R9): only loopback connections are allowed."""
    monkeypatch.setattr(socket, "getaddrinfo", _guard_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", _guard_connect)

PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def app(data_dir):
    return create_app(data_dir, port=PORT, testing=True)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf(client):
    """A valid CSRF token stored in the client's session."""
    with client.session_transaction(base_url=BASE_URL) as session:
        session["csrf_token"] = "test-token-0123456789"
    return "test-token-0123456789"


def pytest_configure(config):
    # Requests from the Flask test client must look like the local browser.
    from flask.testing import FlaskClient

    original = FlaskClient.open

    def open_local(self, *args, **kwargs):
        kwargs.setdefault("base_url", BASE_URL)
        return original(self, *args, **kwargs)

    FlaskClient.open = open_local
