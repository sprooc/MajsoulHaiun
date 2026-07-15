from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_cors_does_not_allow_arbitrary_origins(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_explicit_cors_allowlist_is_honored(tmp_path):
    settings = Settings(data_dir=tmp_path, allowed_origins=("http://192.168.1.20:5173",))
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/api/health",
            headers={"Origin": "http://192.168.1.20:5173", "Access-Control-Request-Method": "GET"},
        )
    assert response.headers["access-control-allow-origin"] == "http://192.168.1.20:5173"


def test_application_schema_contains_no_credential_fields(client):
    schema = client.get("/openapi.json").text.lower()
    for forbidden in ("password", "oauth_token", "email_code", "browser_session", "access_token"):
        assert forbidden not in schema
    assert "/api/admin/session" not in schema
