from enum import StrEnum
from typing import Protocol

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )


class GameMode(StrEnum):
    FOUR_PLAYER = "4p"
    THREE_PLAYER = "3p"


class SourceCapability(StrEnum):
    SEARCH_PLAYERS = "search_players"
    LIST_PLAYER_GAMES = "list_player_games"
    FETCH_BY_ID = "fetch_by_id"
    IMPORT_FILE = "import_file"


class RemotePlayer(ApiModel):
    source: str
    external_id: str
    nickname: str
    mode: GameMode
    level_id: int | None = None
    latest_timestamp: int | None = None


class RemoteGame(ApiModel):
    source: str
    external_id: str
    uuid: str
    mode: GameMode
    mode_id: int | None = None
    started_at: int | None = None
    ended_at: int | None = None
    players: list[dict[str, object]] = []
    scores: list[int] = []
    grading_scores: list[int] = []


class GamePage(ApiModel):
    games: list[RemoteGame]
    next_cursor: int | None = None


class ReplaySource(Protocol):
    id: str
    capabilities: frozenset[SourceCapability]

    async def search_players(self, query: str, mode: GameMode, limit: int = 20) -> list[RemotePlayer]: ...

    async def list_games(
        self, player_id: str, mode: GameMode, cursor: int | None = None, limit: int = 20
    ) -> GamePage: ...
