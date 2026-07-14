import httpx

from app.sources.amae_koromo import AmaeKoromoSource
from app.sources.base import GameMode


async def test_searches_four_player_koromo_api(respx_mock):
    route = respx_mock.get(
        "https://5-data.amae-koromo.com/api/v2/pl4/search_player/A?limit=20&tag=all"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 7, "nickname": "A", "level": {"id": 10401}, "latest_timestamp": 1700000000}],
        )
    )
    async with httpx.AsyncClient() as client:
        players = await AmaeKoromoSource(client).search_players("A", GameMode.FOUR_PLAYER)
    assert route.called
    assert players[0].external_id == "7"
    assert players[0].mode == GameMode.FOUR_PLAYER


async def test_lists_three_player_games_using_sanma_mode_ids(respx_mock):
    route = respx_mock.get(
        "https://5-data.amae-koromo.com/api/v2/pl3/player_records/7/1700000000000/1262304000000?limit=20&mode=26,24,22,25,23,21&descending=true"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "_id": "record",
                    "uuid": "game-uuid",
                    "modeId": 26,
                    "startTime": 1699999999,
                    "endTime": 1700000300,
                    "players": [{"accountId": 7, "nickname": "A"}],
                    "scores": [42000, 33000, 30000],
                    "gradingScore": [12, -4, -8],
                }
            ],
        )
    )
    async with httpx.AsyncClient() as client:
        page = await AmaeKoromoSource(client).list_games("7", GameMode.THREE_PLAYER, cursor=1700000000000)
    assert route.called
    assert page.games[0].uuid == "game-uuid"
    assert page.games[0].mode == GameMode.THREE_PLAYER


async def test_game_results_are_extracted_from_public_player_records(respx_mock):
    respx_mock.get(
        "https://5-data.amae-koromo.com/api/v2/pl4/player_records/7/4102444800000/1262304000000?limit=20&mode=16,12,9,15,11,8&descending=true"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "_id": "record",
                    "uuid": "game-uuid",
                    "modeId": 16,
                    "players": [
                        {"accountId": 1, "nickname": "A", "score": 25000, "gradingScore": 0},
                        {"accountId": 2, "nickname": "B", "score": 41000, "gradingScore": 80},
                        {"accountId": 3, "nickname": "C", "score": 9000, "gradingScore": -120},
                        {"accountId": 4, "nickname": "D", "score": 25000, "gradingScore": 0},
                    ],
                }
            ],
        )
    )

    async with httpx.AsyncClient() as client:
        page = await AmaeKoromoSource(client).list_games("7", GameMode.FOUR_PLAYER)

    assert page.games[0].scores == [25000, 41000, 9000, 25000]
    assert page.games[0].grading_scores == [0, 80, -120, 0]
    assert page.games[0].ranks == [2, 1, 4, 3]


async def test_published_ranks_take_precedence_over_derived_ranks(respx_mock):
    respx_mock.get(
        "https://5-data.amae-koromo.com/api/v2/pl4/player_records/7/4102444800000/1262304000000?limit=20&mode=16,12,9,15,11,8&descending=true"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "_id": "record",
                    "uuid": "game-uuid",
                    "modeId": 16,
                    "players": [
                        {"nickname": "A", "score": 30000, "rank": 2},
                        {"nickname": "B", "score": 30000, "rank": 1},
                        {"nickname": "C", "score": 20000, "rank": 3},
                        {"nickname": "D", "score": 20000, "rank": 4},
                    ],
                }
            ],
        )
    )

    async with httpx.AsyncClient() as client:
        page = await AmaeKoromoSource(client).list_games("7", GameMode.FOUR_PLAYER)

    assert page.games[0].ranks == [2, 1, 3, 4]
