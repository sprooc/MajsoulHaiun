from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_default_host_supports_linux_lan_access():
    assert Settings().host == "0.0.0.0"


def test_runtime_settings_can_be_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("HAIUN_HOST", "127.0.0.1")
    monkeypatch.setenv("HAIUN_PORT", "9876")
    monkeypatch.setenv("HAIUN_DATA_DIR", str(tmp_path))
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 9876
    assert settings.data_dir == tmp_path


def test_allowed_origins_accept_comma_separated_environment_value(monkeypatch):
    monkeypatch.setenv("HAIUN_ALLOWED_ORIGINS", "http://localhost:5173,http://192.168.1.20:5173")
    assert Settings().allowed_origins == ("http://localhost:5173", "http://192.168.1.20:5173")


def test_health_endpoint(tmp_path):
    settings = Settings(data_dir=tmp_path)
    response = TestClient(create_app(settings)).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
