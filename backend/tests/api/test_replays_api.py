from pathlib import Path

from app.sources.majsoul.fetcher import MajsoulReplayFetcher


def test_imported_decoded_replay_returns_canonical_game_id(client):
    fixture = Path(__file__).parents[1] / "fixtures" / "majsoul" / "three_player_kita.json"
    response = client.post(
        "/api/replays/import-file",
        files={"file": ("three-player.json", fixture.read_bytes(), "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["replayId"]
    assert response.json()["gameId"]


def test_imported_game_can_be_analyzed_without_network(client):
    fixture = Path(__file__).parents[1] / "fixtures" / "majsoul" / "three_player_kita.json"
    imported = client.post(
        "/api/replays/import-file",
        files={"file": ("three-player.json", fixture.read_bytes(), "application/json")},
    ).json()
    response = client.post(
        "/api/analyses",
        json={"gameId": imported["gameId"], "algorithmId": "baseline-v1", "options": {"eventDetails": True}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert len(response.json()["result"]["players"]) == 3


def test_remote_import_rejects_private_network_url(client):
    response = client.post("/api/replays/import-locator", json={"locator": "http://127.0.0.1/private"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REPLAY_LOCATOR"


def test_successful_locator_import_is_canonicalized_for_analysis(client, monkeypatch):
    fixture = Path(__file__).parents[1] / "fixtures" / "majsoul" / "three_player_kita.json"

    async def fetch_fixture(_self, _locator):
        return fixture.read_bytes()

    monkeypatch.setattr(MajsoulReplayFetcher, "fetch", fetch_fixture)
    response = client.post(
        "/api/replays/import-locator",
        json={"locator": "260307-76323960-cf3c-494e-be24-26dd6ba81c98"},
    )

    assert response.status_code == 200
    assert response.json()["replayId"]
    assert response.json()["gameId"]
