import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.events import CallEvent, CallKind, GameEvent
from app.domain.rules import RuleSet


class Player(BaseModel):
    model_config = ConfigDict(frozen=True)

    seat: int = Field(ge=0, le=3)
    name: str
    external_id: str | None = None
    level_id: int | None = None


class Round(BaseModel):
    index: int = Field(ge=0)
    wind: Literal["east", "south", "west", "north"] = "east"
    hand: int = Field(ge=1, le=4)
    dealer: int = Field(ge=0, le=3)
    honba: int = Field(ge=0)
    riichi_sticks: int = Field(ge=0)
    starting_scores: list[int]
    events: list[GameEvent]

    @model_validator(mode="after")
    def order_events(self) -> "Round":
        self.events.sort(key=lambda event: event.sequence)
        sequences = [event.sequence for event in self.events]
        if len(sequences) != len(set(sequences)):
            raise ValueError("event sequences must be unique within a round")
        return self


class CanonicalGame(BaseModel):
    schema_version: str = "1.0.0"
    source: str = "unknown"
    external_id: str
    rules: RuleSet
    players: list[Player]
    rounds: list[Round]
    final_scores: list[int]
    final_ranks: list[int]
    diagnostics: list[str] = []

    @model_validator(mode="after")
    def validate_game_shape(self) -> "CanonicalGame":
        count = self.rules.player_count
        if len(self.players) != count or len(self.final_scores) != count or len(self.final_ranks) != count:
            raise ValueError("players and final results must match rule player count")
        if sorted(player.seat for player in self.players) != list(range(count)):
            raise ValueError("player seats must be contiguous")
        for round_ in self.rounds:
            if len(round_.starting_scores) != count:
                raise ValueError("round score count must match player count")
            for event in round_.events:
                self.validate_event(event)
        return self

    def validate_event(self, event: GameEvent) -> None:
        actor = getattr(event, "actor", None)
        if actor is not None and actor not in range(self.rules.player_count):
            raise ValueError("event actor is outside player range")
        if isinstance(event, CallEvent) and event.kind == CallKind.KITA and not self.rules.kita_enabled:
            raise ValueError("kita is not enabled by these rules")

    @property
    def content_hash(self) -> str:
        payload = self.model_dump_json(exclude_none=True, by_alias=True)
        return hashlib.sha256(payload.encode()).hexdigest()
