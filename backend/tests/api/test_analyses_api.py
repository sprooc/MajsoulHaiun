from uuid import uuid4
import sqlite3

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


ADMIN_PASSWORD = "backend-test-admin-password"


def test_each_create_gets_a_shareable_result_url_while_admin_list_is_protected(client):
    imported = client.post(
        "/api/replays/import-file",
        files={"file": ("game.json", b'{"schema_version":"1.0.0","source":"fixture","external_id":"g","rules":{"player_count":4,"game_length":"south","initial_score":25000,"red_fives":{"m":1,"p":1,"s":1},"open_tanyao":true,"tsumo_loss":null,"kita_enabled":false,"tile_codes":["1m"],"source_rules":{}},"players":[{"seat":0,"name":"A"},{"seat":1,"name":"B"},{"seat":2,"name":"C"},{"seat":3,"name":"D"}],"rounds":[],"final_scores":[41000,25000,19000,15000],"final_ranks":[1,2,3,4],"diagnostics":[]}', "application/json")},
    ).json()

    first_response = client.post(
        "/api/analyses",
        json={"gameId": imported["gameId"], "algorithmId": "baseline-v1", "options": {"eventDetails": True}},
    )
    second_response = client.post(
        "/api/analyses",
        json={"gameId": imported["gameId"], "algorithmId": "baseline-v1", "options": {"eventDetails": True}},
    )

    assert first_response.status_code == second_response.status_code == 202
    queued = first_response.json()
    second = second_response.json()
    assert queued["status"] == "pending"
    assert queued["result"] is None
    assert queued["game"]["finalScores"] == [41000, 25000, 19000, 15000]
    assert queued["id"] != second["id"]

    first_result = client.get(f"/api/results/{queued['id']}")
    second_result = client.get(f"/api/results/{second['id']}")
    assert first_result.status_code == second_result.status_code == 200
    assert first_result.json()["status"] == second_result.json()["status"] == "completed"

    guest_list = client.get("/api/analyses")
    assert guest_list.status_code == 403

    login = client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD})
    assert login.status_code == 200
    listed = client.get("/api/analyses").json()
    assert [item["id"] for item in listed] == [second["id"], queued["id"]]
    assert all(item["status"] == "completed" for item in listed)
    assert all(item["createdAt"] for item in listed)


def test_lists_registered_algorithms(client):
    response = client.get("/api/algorithms")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "baseline-v1"
    assert response.json()[0]["version"] == "1.0.0"


def test_unknown_algorithm_is_typed(client):
    response = client.post(
        "/api/analyses",
        json={"gameId": str(uuid4()), "algorithmId": "missing", "options": {"eventDetails": True}},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "UNKNOWN_ALGORITHM"


def test_get_missing_analysis_is_typed(client):
    response = client.get(f"/api/results/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "ANALYSIS_NOT_FOUND"


def test_startup_backfills_existing_cached_analyses_without_submissions(settings, monkeypatch):
    monkeypatch.setenv("HAIUN_DATA_DIR", str(settings.data_dir))
    alembic_config = Config("backend/alembic.ini")
    command.upgrade(alembic_config, "0002_cache_raw_replay_identity")
    replay_id = f"{1:032x}"
    game_id = f"{2:032x}"
    analysis_id = f"{3:032x}"
    game_json = '{"schema_version":"1.0.0","source":"fixture","external_id":"legacy","rules":{"player_count":4,"game_length":"south","initial_score":25000,"red_fives":{"m":1,"p":1,"s":1},"open_tanyao":true,"tsumo_loss":null,"kita_enabled":false,"tile_codes":["1m"],"source_rules":{}},"players":[{"seat":0,"name":"A"},{"seat":1,"name":"B"},{"seat":2,"name":"C"},{"seat":3,"name":"D"}],"rounds":[],"final_scores":[41000,25000,19000,15000],"final_ranks":[1,2,3,4],"diagnostics":[]}'
    with sqlite3.connect(settings.data_dir / "haiun.sqlite3") as connection:
        connection.execute(
            "INSERT INTO raw_replays (id, source, external_id, payload, sha256) VALUES (?, 'fixture', 'legacy', ?, ?)",
            (replay_id, b"raw", "a" * 64),
        )
        connection.execute(
            "INSERT INTO canonical_games (id, raw_replay_id, schema_version, content_hash, source, external_id, game_json) VALUES (?, ?, '1.0.0', ?, 'fixture', 'legacy', ?)",
            (game_id, replay_id, "b" * 64, game_json),
        )
        connection.execute(
            "INSERT INTO analyses (id, game_id, algorithm_id, algorithm_version, options_hash, status) VALUES (?, ?, 'baseline-v1', '1.0.0', ?, 'completed')",
            (analysis_id, game_id, "c" * 64),
        )
        connection.commit()

    with TestClient(create_app(settings)) as client:
        assert client.post("/api/admin/session", json={"secret": ADMIN_PASSWORD}).status_code == 200
        listed = client.get("/api/analyses").json()
        result = client.get(f"/api/results/{analysis_id}")

    assert [item["id"].replace("-", "") for item in listed] == [analysis_id]
    assert result.status_code == 200
