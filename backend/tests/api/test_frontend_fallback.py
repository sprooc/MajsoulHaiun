from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings


def _create_test_app(tmp_path, monkeypatch):
    static_directory = tmp_path / "frontend" / "dist"
    assets_directory = static_directory / "assets"
    assets_directory.mkdir(parents=True)
    (static_directory / "index.html").write_text("<html>shareable result shell</html>", encoding="utf-8")
    (assets_directory / "app.js").write_text("console.log('haiun')", encoding="utf-8")
    monkeypatch.setattr(main_module, "REPOSITORY_ROOT", tmp_path)
    settings = Settings(data_dir=tmp_path / "data", config_path=tmp_path / "missing.toml")
    return main_module.create_app(settings)


def test_html_navigation_serves_spa_and_real_assets_without_masking_api_routes(tmp_path, monkeypatch):
    with TestClient(_create_test_app(tmp_path, monkeypatch)) as client:
        result = client.get(
            "/results/00000000-0000-4000-8000-000000000001",
            headers={"Accept": "text/html"},
        )
        admin_head = client.head("/admin", headers={"Accept": "text/html"})
        real_asset = client.get("/assets/app.js", headers={"Accept": "*/*"})
        missing_api = client.get("/api/does-not-exist", headers={"Accept": "text/html"})

    assert result.status_code == 200
    assert "shareable result shell" in result.text
    assert admin_head.status_code == 200
    assert real_asset.status_code == 200
    assert real_asset.text == "console.log('haiun')"
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")


def test_missing_asset_does_not_serve_spa_shell(tmp_path, monkeypatch):
    with TestClient(_create_test_app(tmp_path, monkeypatch)) as client:
        response = client.get("/assets/missing.js", headers={"Accept": "text/html"})

    assert response.status_code == 404


def test_extensionless_non_html_request_does_not_serve_spa_shell(tmp_path, monkeypatch):
    with TestClient(_create_test_app(tmp_path, monkeypatch)) as client:
        response = client.get("/results/not-html", headers={"Accept": "application/json"})

    assert response.status_code == 404
