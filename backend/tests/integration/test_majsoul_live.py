import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


RECORD_LINK = (
    "https://game.maj-soul.com/1/"
    "?paipu=260714-ec4c890c-abec-4758-9337-2bce7085dbe6_a215808906"
)


@pytest.mark.skipif(
    os.getenv("HAIUN_RUN_MAJSOUL_LIVE") != "1",
    reason="live Mahjong Soul test disabled",
)
def test_live_import_cache_and_analysis(tmp_path: Path):
    config_path = Path(os.environ["HAIUN_MAJSOUL_CONFIG"])
    settings = Settings(data_dir=tmp_path / "data", majsoul_config_path=config_path)

    with TestClient(create_app(settings)) as client:
        first = client.post("/api/replays/import-locator", json={"locator": RECORD_LINK})
        assert first.status_code == 200, first.text
        imported = first.json()
        assert imported.get("gameId")

        analysis = client.post(
            "/api/analyses",
            json={
                "gameId": imported["gameId"],
                "algorithmId": "baseline-v1",
                "options": {"eventDetails": True},
            },
        )
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["status"] == "completed"

        second = client.post("/api/replays/import-locator", json={"locator": RECORD_LINK})
        assert second.status_code == 200, second.text
        assert second.json() == imported
