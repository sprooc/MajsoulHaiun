def test_player_search_requires_mode(client):
    response = client.get("/api/players/search", params={"source": "amae-koromo", "q": "A"})
    assert response.status_code == 422
