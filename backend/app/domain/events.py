from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int = Field(ge=0)


class CallKind(StrEnum):
    CHI = "chi"
    PON = "pon"
    DAIMINKAN = "daiminkan"
    ANKAN = "ankan"
    KAKAN = "kakan"
    KITA = "kita"


class RoundStarted(EventModel):
    event_type: Literal["round_started"] = "round_started"
    dealer: int
    scores: list[int]
    dora_indicator: str | None = None
    starting_hands: list[list[str]] | None = None


class TileDrawn(EventModel):
    event_type: Literal["tile_drawn"] = "tile_drawn"
    actor: int
    tile: str
    from_rinshan: bool = False


class TileDiscarded(EventModel):
    event_type: Literal["tile_discarded"] = "tile_discarded"
    actor: int
    tile: str
    tsumogiri: bool = False


class CallEvent(EventModel):
    event_type: Literal["call"] = "call"
    actor: int
    kind: CallKind
    tile: str
    consumed_tiles: list[str]
    target: int | None = None


class RiichiDeclared(EventModel):
    event_type: Literal["riichi_declared"] = "riichi_declared"
    actor: int


class RiichiAccepted(EventModel):
    event_type: Literal["riichi_accepted"] = "riichi_accepted"
    actor: int
    score_delta: list[int] | None = None


class DoraRevealed(EventModel):
    event_type: Literal["dora_revealed"] = "dora_revealed"
    indicator: str
    reason: Literal["initial", "kan", "ura"] = "kan"


class WinEvent(EventModel):
    event_type: Literal["win"] = "win"
    winners: list[int]
    loser: int | None = None
    score_delta: list[int]
    ura_indicators: list[str] = []


class ExhaustiveDraw(EventModel):
    event_type: Literal["exhaustive_draw"] = "exhaustive_draw"
    tenpai_players: list[int] = []
    score_delta: list[int]


class AbortiveDraw(EventModel):
    event_type: Literal["abortive_draw"] = "abortive_draw"
    reason: str
    score_delta: list[int] = []


class ScoreChanged(EventModel):
    event_type: Literal["score_changed"] = "score_changed"
    score_delta: list[int]
    reason: str


class RoundEnded(EventModel):
    event_type: Literal["round_ended"] = "round_ended"
    final_scores: list[int]


class UnknownEvent(EventModel):
    event_type: Literal["unknown"] = "unknown"
    raw_type: str
    raw_payload: dict[str, object]


GameEvent = Annotated[
    RoundStarted
    | TileDrawn
    | TileDiscarded
    | CallEvent
    | RiichiDeclared
    | RiichiAccepted
    | DoraRevealed
    | WinEvent
    | ExhaustiveDraw
    | AbortiveDraw
    | ScoreChanged
    | RoundEnded
    | UnknownEvent,
    Field(discriminator="event_type"),
]
