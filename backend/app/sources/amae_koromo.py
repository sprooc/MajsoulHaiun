from urllib.parse import quote

import httpx

from app.errors import SourceUnavailable
from app.sources.base import GameMode, GamePage, RemoteGame, RemotePlayer, SourceCapability


MIRRORS = (
    "https://5-data.amae-koromo.com/",
    "https://1.data.amae-koromo.com/",
    "https://2.data.amae-koromo.com/",
    "https://4.data.amae-koromo.com/",
)
MODE_PATH = {GameMode.FOUR_PLAYER: "api/v2/pl4/", GameMode.THREE_PLAYER: "api/v2/pl3/"}
MODE_IDS = {
    GameMode.FOUR_PLAYER: (16, 12, 9, 15, 11, 8),
    GameMode.THREE_PLAYER: (26, 24, 22, 25, 23, 21),
}
EARLIEST_TIMESTAMP_MS = 1262304000000


class AmaeKoromoSource:
    id = "amae-koromo"
    capabilities = frozenset({SourceCapability.SEARCH_PLAYERS, SourceCapability.LIST_PLAYER_GAMES})

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _get_json(self, path: str) -> object:
        last_error: Exception | None = None
        for mirror in MIRRORS:
            try:
                response = await self.client.get(mirror + path, timeout=5.0)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = exc
        raise SourceUnavailable("AMAE_KOROMO_UNAVAILABLE", "Amae-Koromo is temporarily unavailable.") from last_error

    async def search_players(self, query: str, mode: GameMode, limit: int = 20) -> list[RemotePlayer]:
        safe_limit = min(max(limit, 1), 50)
        path = f"{MODE_PATH[mode]}search_player/{quote(query, safe='')}?limit={safe_limit}&tag=all"
        payload = await self._get_json(path)
        if not isinstance(payload, list):
            raise SourceUnavailable("AMAE_KOROMO_INVALID_RESPONSE", "Amae-Koromo returned invalid player data.")
        players: list[RemotePlayer] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            level = item.get("level") if isinstance(item.get("level"), dict) else {}
            players.append(
                RemotePlayer(
                    source=self.id,
                    external_id=str(item.get("id", "")),
                    nickname=str(item.get("nickname", "")),
                    mode=mode,
                    level_id=level.get("id"),
                    latest_timestamp=item.get("latest_timestamp"),
                )
            )
        return players

    async def list_games(
        self, player_id: str, mode: GameMode, cursor: int | None = None, limit: int = 20
    ) -> GamePage:
        safe_limit = min(max(limit, 1), 50)
        cursor_ms = cursor or 4102444800000
        mode_ids = ",".join(str(value) for value in MODE_IDS[mode])
        path = (
            f"{MODE_PATH[mode]}player_records/{quote(player_id, safe='')}/{cursor_ms}/{EARLIEST_TIMESTAMP_MS}"
            f"?limit={safe_limit}&mode={mode_ids}&descending=true"
        )
        payload = await self._get_json(path)
        if not isinstance(payload, list):
            raise SourceUnavailable("AMAE_KOROMO_INVALID_RESPONSE", "Amae-Koromo returned invalid game data.")
        games: list[RemoteGame] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            games.append(
                RemoteGame(
                    source=self.id,
                    external_id=str(item.get("_id", item.get("uuid", ""))),
                    uuid=str(item.get("uuid", "")),
                    mode=mode,
                    mode_id=item.get("modeId"),
                    started_at=item.get("startTime"),
                    ended_at=item.get("endTime"),
                    players=item.get("players") if isinstance(item.get("players"), list) else [],
                    scores=item.get("scores") if isinstance(item.get("scores"), list) else [],
                    grading_scores=item.get("gradingScore") if isinstance(item.get("gradingScore"), list) else [],
                )
            )
        next_cursor = None
        if games and games[-1].started_at is not None:
            next_cursor = games[-1].started_at * 1000 - 1
        return GamePage(games=games, next_cursor=next_cursor)
