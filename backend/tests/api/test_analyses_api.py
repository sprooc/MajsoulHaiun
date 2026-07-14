from uuid import uuid4


def test_create_analysis_returns_queued_task_and_list_includes_completed_task(client):
    imported = client.post(
        "/api/replays/import-file",
        files={"file": ("game.json", b'{"schema_version":"1.0.0","source":"fixture","external_id":"g","rules":{"player_count":4,"game_length":"south","initial_score":25000,"red_fives":{"m":1,"p":1,"s":1},"open_tanyao":true,"tsumo_loss":null,"kita_enabled":false,"tile_codes":["1m"],"source_rules":{}},"players":[{"seat":0,"name":"A"},{"seat":1,"name":"B"},{"seat":2,"name":"C"},{"seat":3,"name":"D"}],"rounds":[],"final_scores":[41000,25000,19000,15000],"final_ranks":[1,2,3,4],"diagnostics":[]}', "application/json")},
    ).json()

    response = client.post(
        "/api/analyses",
        json={"gameId": imported["gameId"], "algorithmId": "baseline-v1", "options": {"eventDetails": True}},
    )

    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "pending"
    assert queued["result"] is None
    assert queued["game"]["finalScores"] == [41000, 25000, 19000, 15000]

    listed = client.get("/api/analyses").json()
    assert len(listed) == 1
    assert listed[0]["id"] == queued["id"]
    assert listed[0]["status"] == "completed"
    assert listed[0]["createdAt"]


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
    response = client.get(f"/api/analyses/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "ANALYSIS_NOT_FOUND"
