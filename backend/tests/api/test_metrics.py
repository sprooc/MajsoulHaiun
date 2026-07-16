from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_metrics_are_disabled_by_default(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.get("/metrics")

    assert response.status_code == 404


def test_metrics_setting_accepts_environment_override(monkeypatch):
    monkeypatch.setenv("HAIUN_METRICS_ENABLED", "true")

    assert Settings().metrics_enabled is True


def test_enabled_metrics_are_schema_hidden_and_include_process_metrics(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        metrics_response = client.get("/metrics")
        schema_response = client.get("/openapi.json")

    assert metrics_response.status_code == 200
    assert "process_resident_memory_bytes" in metrics_response.text
    assert "/metrics" not in schema_response.json()["paths"]


def test_metrics_observe_only_api_requests(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        client.get("/", headers={"Accept": "text/html"})
        metrics = client.get("/metrics").text

    assert "haiun_http_requests_total{" not in metrics


def test_metrics_normalize_nonstandard_http_methods(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        client.request("X-HAIUN-ONE", "/api/health")
        client.request("X-HAIUN-TWO", "/api/health")
        metrics = client.get("/metrics").text

    assert 'method="OTHER"' in metrics
    assert "X-HAIUN-ONE" not in metrics
    assert "X-HAIUN-TWO" not in metrics


def test_metrics_use_normalized_routes_and_exclude_request_secrets(tmp_path):
    submission_id = uuid4()
    with TestClient(
        create_app(Settings(data_dir=tmp_path, metrics_enabled=True))
    ) as client:
        response = client.get(
            f"/api/results/{submission_id}",
            params={"oauth_token": "must-not-be-exported"},
            cookies={"haiun_admin_session": "must-not-be-exported"},
        )
        metrics = client.get("/metrics").text

    assert response.status_code == 404
    assert 'route="/api/results/{submission_id}"' in metrics
    assert 'status="404"' in metrics
    assert str(submission_id) not in metrics
    assert "must-not-be-exported" not in metrics
    assert "oauth_token" not in metrics
    assert "haiun_admin_session" not in metrics
