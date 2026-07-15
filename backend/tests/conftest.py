import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[admin]\npassword = 'backend-test-admin-password'\nsession_hours = 12\n",
        encoding="utf-8",
    )
    return Settings(data_dir=tmp_path / "data", config_path=config_path)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def load_fixture():
    fixture_root = Path(__file__).parent / "fixtures"

    def load(relative_path: str):
        return json.loads((fixture_root / relative_path).read_text(encoding="utf-8"))

    return load
