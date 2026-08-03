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
CAPTCHA_PATTERN = "[x-cap-token-required]"


def _integer_list(value: object) -> list[int]:
    if not isinstance(value, list) or not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        return []
    return value


def _player_values(players: list[dict[str, object]], *keys: str) -> list[int]:
    values: list[int] = []
    for player in players:
        value = next((player[key] for key in keys if key in player), None)
        if not isinstance(value, int) or isinstance(value, bool):
            return []
        values.append(value)
    return values


def _ranks(item: dict[str, object], players: list[dict[str, object]], scores: list[int]) -> list[int]:
    for key in ("ranks", "finalRanks", "final_ranks"):
        published = _integer_list(item.get(key))
        if len(published) == len(players):
            return published
    published = _player_values(players, "rank", "finalRank", "final_rank")
    if len(published) == len(players):
        return published
    if len(scores) != len(players):
        return []
    ordered_seats = sorted(range(len(scores)), key=lambda seat: (-scores[seat], seat))
    ranks = [0] * len(scores)
    for rank, seat in enumerate(ordered_seats, start=1):
        ranks[seat] = rank
    return ranks


class AmaeKoromoSource:
    id = "amae-koromo"
    capabilities = frozenset({SourceCapability.SEARCH_PLAYERS, SourceCapability.LIST_PLAYER_GAMES})

    def __init__(self, client: httpx.AsyncClient, *, cap_token: str | None = None):
        self.client = client
        self.cap_token = cap_token

    async def _get_json(self, path: str) -> object:
        headers: dict[str, str] = {}
        if self.cap_token:
            headers["x-cap-token"] = self.cap_token
        last_error: Exception | None = None
        for mirror in MIRRORS:
            try:
                response = await self.client.get(mirror + path, timeout=5.0, headers=headers)
                if response.status_code == 429:
                    raise SourceUnavailable(
                        "AMAE_KOROMO_RATE_LIMITED", "Amae-Koromo returned HTTP 429 (rate limited)."
                    )
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError:
                    text = response.text
                    if CAPTCHA_PATTERN in text:
                        raise SourceUnavailable(
                            "AMAE_KOROMO_CAP_REQUIRED",
                            "Amae-Koromo requires a CAPTCHA token.",
                        )
                    raise SourceUnavailable(
                        "AMAE_KOROMO_INVALID_RESPONSE", "Amae-Koromo returned non-JSON content."
                    )
            except SourceUnavailable:
                raise
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
            players = [player for player in item.get("players", []) if isinstance(player, dict)]
            scores = _integer_list(item.get("scores")) or _player_values(players, "score")
            grading_scores = _integer_list(item.get("gradingScore")) or _player_values(
                players, "gradingScore", "grading_score"
            )
            games.append(
                RemoteGame(
                    source=self.id,
                    external_id=str(item.get("_id", item.get("uuid", ""))),
                    uuid=str(item.get("uuid", "")),
                    mode=mode,
                    mode_id=item.get("modeId"),
                    started_at=item.get("startTime"),
                    ended_at=item.get("endTime"),
                    players=players,
                    scores=scores,
                    ranks=_ranks(item, players, scores),
                    grading_scores=grading_scores,
                )
            )
        next_cursor = None
        if games and games[-1].started_at is not None:
            next_cursor = games[-1].started_at * 1000 - 1
        return GamePage(games=games, next_cursor=next_cursor)
