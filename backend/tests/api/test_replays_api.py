from pathlib import Path

import app.api.replays as replays_api
from app.sources.majsoul.fetcher import MajsoulReplayFetcher


RECORD_ID = "260307-76323960-cf3c-494e-be24-26dd6ba81c98"


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
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    completed = client.get(f"/api/analyses/{response.json()['id']}")
    assert completed.json()["status"] == "completed"
    assert len(completed.json()["result"]["players"]) == 3


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


def test_second_locator_import_reuses_raw_and_canonical_cache(client, monkeypatch):
    fixture = Path(__file__).parents[1] / "fixtures" / "majsoul" / "three_player_kita.json"
    fetch_calls = 0
    decode_calls = 0
    original_decode = replays_api.decode_majsoul

    async def fetch_fixture(_self, _locator):
        nonlocal fetch_calls
        fetch_calls += 1
        return fixture.read_bytes()

    def count_decode(payload):
        nonlocal decode_calls
        decode_calls += 1
        return original_decode(payload)

    monkeypatch.setattr(MajsoulReplayFetcher, "fetch", fetch_fixture)
    monkeypatch.setattr(replays_api, "decode_majsoul", count_decode)

    first = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})
    second = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert fetch_calls == 1
    assert decode_calls == 1


def test_locator_import_uses_app_settings_and_shared_http_client(client, settings, monkeypatch):
    fixture = Path(__file__).parents[1] / "fixtures" / "majsoul" / "three_player_kita.json"
    captured = {}

    def capture_init(self, config_path, http_client):
        captured["config_path"] = config_path
        captured["http_client"] = http_client

    async def fetch_fixture(_self, _locator):
        return fixture.read_bytes()

    monkeypatch.setattr(MajsoulReplayFetcher, "__init__", capture_init)
    monkeypatch.setattr(MajsoulReplayFetcher, "fetch", fetch_fixture)

    response = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})

    assert response.status_code == 200
    assert captured["config_path"] == settings.majsoul_config_path
    assert captured["http_client"] is client.app.state.http_client


def test_unparseable_remote_replay_is_not_cached_as_success(client, monkeypatch):
    fetch_calls = 0

    async def fetch_invalid(_self, _locator):
        nonlocal fetch_calls
        fetch_calls += 1
        return b"{}"

    monkeypatch.setattr(MajsoulReplayFetcher, "fetch", fetch_invalid)

    first = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})
    second = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})

    assert first.status_code == second.status_code == 422
    assert first.json()["code"] == second.json()["code"] == "INVALID_REPLAY_DATA"
    assert fetch_calls == 2
