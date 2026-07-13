from typing import Literal

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AnalysisModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel, validation_alias=to_camel),
    )


class AnalysisOptions(AnalysisModel):
    event_details: bool = True


LuckComponent = Literal["initial_hand", "self_draw", "dora_reveal", "special_random", "opponent_gift"]
Confidence = Literal["low", "medium", "high"]


class EventLuckDetail(AnalysisModel):
    sequence: int
    player: int
    component: LuckComponent
    actual: float
    expected: float
    delta: float
    variance: float = Field(ge=0)
    z_score: float
    included_in_total: bool = True
    tile: str | None = None
    explanation_key: str
    features: dict[str, float | int | str | bool] = {}


class RoundPlayerLuck(AnalysisModel):
    seat: int
    raw_delta: float
    variance: float
    z_score: float
    score: float
    confidence: Confidence
    actual_points: int = 0


class RoundLuckAnalysis(AnalysisModel):
    round_index: int
    label: str
    players: list[RoundPlayerLuck]
    events: list[EventLuckDetail]


class PlayerLuckAnalysis(AnalysisModel):
    seat: int
    name: str
    raw_delta: float
    variance: float
    z_score: float
    score: float
    confidence: Confidence
    actual_points: int
    components: dict[str, float]


class GameLuckAnalysis(AnalysisModel):
    analysis_schema_version: str = "1.0.0"
    game_hash: str
    algorithm_id: str
    algorithm_version: str
    options: AnalysisOptions
    players: list[PlayerLuckAnalysis]
    rounds: list[RoundLuckAnalysis]
