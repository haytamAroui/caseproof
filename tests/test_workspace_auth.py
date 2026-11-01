"""Auth HTTP secrecy, bounds, origin and lifecycle controls (synthetic unit tests)."""
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.workspace_auth import LoginBody, SessionView, create_workspace_auth_router


def rig():
    auth = Mock()
    auth.login.return_value = SessionView(access_token='synthetic-token', expires_at=2000000000)
    app = FastAPI()
    app.include_router(create_workspace_auth_router(auth))
    # Use real composition error projection for sanitized AccessRejected errors.
    from apps.api.litigation_development_app import create_litigation_development_app
    composed = create_litigation_development_app()
    for exception, handler in composed.exception_handlers.items():
        app.add_exception_handler(exception, handler)
    return TestClient(app), auth


def test_credentials_are_secret_in_repr_and_only_access_token_leaves_provider():
    body = LoginBody(email='user@example.com', password='private-password')
    assert 'private-password' not in repr(body)
    client, auth = rig()
    result = client.post('/v2/workspace/session', json={'email': body.email, 'password': 'private-password'},
                         headers={'Origin': 'http://testserver'})
    assert result.status_code == 200
    assert set(result.json()) == {'access_token', 'expires_at'}
    assert auth.login.call_args.args[0].password.get_secret_value() == 'private-password'
    assert not result.cookies


def test_origin_and_fetch_metadata_deny_before_provider():
    client, auth = rig()
    for headers in ({'Origin': 'https://foreign.example'}, {'Sec-Fetch-Site': 'cross-site'}):
        result = client.post('/v2/workspace/session', json={'email': 'u@e.com', 'password': 'secret'}, headers=headers)
        assert result.status_code == 403
        assert 'secret' not in result.text
    auth.login.assert_not_called()


def test_validation_bounds_and_unknown_fields_never_echo_passwords():
    client, auth = rig()
    for payload in ({'email': '', 'password': 'secret'}, {'email': 'u@e.com', 'password': 'secret', 'role': 'admin'}):
        result = client.post('/v2/workspace/session', json=payload)
        assert result.status_code == 422
        assert 'secret' not in result.text
    assert client.post('/v2/workspace/session', content=b'x' * 8193).status_code == 413
    auth.login.assert_not_called()


def test_bounded_rate_limit_and_explicit_logout():
    client, auth = rig()
    for _ in range(12):
        assert client.post('/v2/workspace/session', json={'email': 'u@e.com', 'password': 'secret'}).status_code == 200
    assert client.post('/v2/workspace/session', json={'email': 'u@e.com', 'password': 'secret'}).status_code == 429
    assert client.post('/v2/workspace/session/end').status_code == 401
    assert client.post('/v2/workspace/session/end', headers={'Authorization': 'Bearer token'}).status_code == 204
    auth.logout.assert_called_once_with('token')


def test_static_runtime_is_opt_in_and_keeps_api_out_of_spa(tmp_path):
    from apps.api.litigation_development_app import create_litigation_development_app
    (tmp_path / 'index.html').write_text('<html>synthetic</html>')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/main.js').write_text('/* synthetic */')
    app = create_litigation_development_app(workspace_directory=tmp_path)
    client = TestClient(app, client=('127.0.0.1', 1234))
    response = client.get('/workspace/matters/opaque')
    assert response.status_code == 200
    assert "connect-src 'self'" in response.headers['content-security-policy']
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/workspace/assets/missing.js').status_code == 404
    assert client.get('/v2/unknown').status_code == 404
    assert TestClient(create_litigation_development_app(), client=('127.0.0.1', 1234)).get('/workspace').status_code == 404
