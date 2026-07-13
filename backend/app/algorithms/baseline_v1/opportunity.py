from collections import Counter
from dataclasses import dataclass, field

from app.algorithms.baseline_v1.hand_value import HandState, hand_value
from app.domain.rules import RuleSet
from app.domain.tiles import Tile


@dataclass
class PublicPlayerState:
    hand_codes: list[str]
    rules: RuleSet
    visible_codes: list[str] = field(default_factory=list)
    dora_indicators: list[str] = field(default_factory=list)

    @classmethod
    def from_codes(cls, codes: list[str], rules: RuleSet) -> "PublicPlayerState":
        return cls(hand_codes=list(codes), rules=rules)

    @property
    def remaining_tile_counts(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for base in self.rules.tile_codes:
            if base[0] == "5" and base[1] in "mps":
                red = self.rules.red_fives.get(base[1], 0)
                if red:
                    totals[f"0{base[1]}"] = red
                totals[base] = 4 - red
            else:
                totals[base] = 4
        seen = Counter([*self.hand_codes, *self.visible_codes])
        for code, count in seen.items():
            if code in totals:
                totals[code] = max(0, totals[code] - count)
            else:
                base = Tile.parse(code).base_code
                if base in totals:
                    totals[base] = max(0, totals[base] - count)
        return {code: count for code, count in totals.items() if count > 0}


@dataclass(frozen=True)
class OpportunityResult:
    actual: float
    expected: float
    delta: float
    variance: float
    candidate_count: int


def best_post_draw_value(state: PublicPlayerState, tile: Tile) -> float:
    with_draw = [*state.hand_codes, tile.code]
    if len(with_draw) % 3 != 2:
        return hand_value(HandState.from_codes(with_draw, state.dora_indicators), state.rules)
    values: list[float] = []
    for index in range(len(with_draw)):
        after_discard = with_draw[:index] + with_draw[index + 1 :]
        values.append(hand_value(HandState.from_codes(after_discard, state.dora_indicators), state.rules))
    return max(values)


def draw_opportunity(state: PublicPlayerState, actual_tile: Tile) -> OpportunityResult:
    outcomes: list[tuple[int, float]] = []
    for code, count in state.remaining_tile_counts.items():
        outcomes.append((count, best_post_draw_value(state, Tile.parse(code))))
    total = sum(count for count, _ in outcomes)
    if total == 0:
        actual = best_post_draw_value(state, actual_tile)
        return OpportunityResult(actual=actual, expected=actual, delta=0, variance=0, candidate_count=0)
    expected = sum(count * value for count, value in outcomes) / total
    variance = sum(count * (value - expected) ** 2 for count, value in outcomes) / total
    actual = best_post_draw_value(state, actual_tile)
    return OpportunityResult(
        actual=actual,
        expected=expected,
        delta=actual - expected,
        variance=variance,
        candidate_count=total,
    )


def dora_indicator_opportunity(state: PublicPlayerState, actual_indicator: Tile) -> OpportunityResult:
    current = hand_value(HandState.from_codes(state.hand_codes, state.dora_indicators), state.rules)
    outcomes: list[tuple[int, float]] = []
    for code, count in state.remaining_tile_counts.items():
        value = hand_value(
            HandState.from_codes(state.hand_codes, [*state.dora_indicators, code]),
            state.rules,
        )
        outcomes.append((count, value - current))
    total = sum(count for count, _ in outcomes)
    actual = hand_value(
        HandState.from_codes(state.hand_codes, [*state.dora_indicators, actual_indicator.code]),
        state.rules,
    ) - current
    if total == 0:
        return OpportunityResult(actual=actual, expected=actual, delta=0, variance=0, candidate_count=0)
    expected = sum(count * value for count, value in outcomes) / total
    variance = sum(count * (value - expected) ** 2 for count, value in outcomes) / total
    return OpportunityResult(
        actual=actual,
        expected=expected,
        delta=actual - expected,
        variance=variance,
        candidate_count=total,
    )
