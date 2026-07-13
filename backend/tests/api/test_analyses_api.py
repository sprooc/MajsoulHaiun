from uuid import uuid4


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
