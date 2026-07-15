from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings


def test_direct_result_url_serves_spa_without_masking_missing_api_routes(tmp_path, monkeypatch):
    static_directory = tmp_path / "frontend" / "dist"
    static_directory.mkdir(parents=True)
    (static_directory / "index.html").write_text("<html>shareable result shell</html>", encoding="utf-8")
    monkeypatch.setattr(main_module, "REPOSITORY_ROOT", tmp_path)
    settings = Settings(data_dir=tmp_path / "data", config_path=tmp_path / "missing.toml")

    with TestClient(main_module.create_app(settings)) as client:
        result = client.get("/results/00000000-0000-4000-8000-000000000001")
        missing_api = client.get("/api/does-not-exist")

    assert result.status_code == 200
    assert "shareable result shell" in result.text
    assert missing_api.status_code == 404
