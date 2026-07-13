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
