"""Every write route of the real app refuses a request without the CSRF token.

The guard is global (``security.init_security``); this test keeps it that way: a new
POST route, or an exemption added later, fails here.
"""

from werkzeug.routing import IntegerConverter

from tests.conftest import BASE_URL


def _sample_url(rule) -> str:
    values = {name: 1 if isinstance(conv, IntegerConverter) else "cv"
              for name, conv in rule._converters.items()}
    return rule.build(values)[1]


def _write_rules(app):
    return [r for r in app.url_map.iter_rules()
            if r.methods & {"POST", "PUT", "PATCH", "DELETE"}]


def test_the_app_has_write_routes(app):
    assert len(_write_rules(app)) >= 10


def _record_calls(app) -> list[str]:
    """Wrap every view so the test knows if one ran (a 400 could also come from a view)."""
    called = []
    for endpoint, view in list(app.view_functions.items()):
        def wrapper(*args, _view=view, _endpoint=endpoint, **kwargs):
            called.append(_endpoint)
            return _view(*args, **kwargs)
        app.view_functions[endpoint] = wrapper
    return called


def test_every_write_route_requires_the_csrf_token(app, client):
    called = _record_calls(app)
    unprotected = []
    for rule in _write_rules(app):
        url = _sample_url(rule)
        for method in rule.methods & {"POST", "PUT", "PATCH", "DELETE"}:
            resp = client.open(url, method=method, base_url=BASE_URL)
            if resp.status_code != 400:
                unprotected.append(f"{method} {rule.rule} -> {resp.status_code}")
    assert unprotected == []
    assert called == []


def test_a_wrong_token_is_also_refused(app, client, csrf):
    called = _record_calls(app)
    for rule in _write_rules(app):
        resp = client.post(_sample_url(rule), data={"csrf_token": "wrong"}, base_url=BASE_URL)
        assert resp.status_code == 400, rule.rule
    assert called == []
