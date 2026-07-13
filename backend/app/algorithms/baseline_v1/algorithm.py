import json
import math
from collections import defaultdict
from pathlib import Path

from app.algorithms.base import LuckAlgorithm
from app.algorithms.baseline_v1.hand_value import HandState, hand_value
from app.algorithms.baseline_v1.opportunity import (
    PublicPlayerState,
    best_post_draw_value,
    dora_indicator_opportunity,
    draw_opportunity,
)
from app.domain.analysis import (
    AnalysisOptions,
    EventLuckDetail,
    GameLuckAnalysis,
    PlayerLuckAnalysis,
    RoundLuckAnalysis,
    RoundPlayerLuck,
)
from app.domain.events import CallEvent, CallKind, DoraRevealed, RoundStarted, TileDiscarded, TileDrawn, WinEvent
from app.domain.game import CanonicalGame
from app.domain.rules import RuleSet
from app.domain.tiles import Tile
from app.errors import AppError


CALIBRATION = json.loads(Path(__file__).with_name("calibration.json").read_text(encoding="utf-8"))


def score_from_z(z: float) -> float:
    return max(0.0, min(100.0, 50.0 + 15.0 * z))


def _z(delta: float, variance: float) -> float:
    return delta / math.sqrt(variance) if variance > 1e-12 else 0.0


def _confidence(event_count: int, variance: float) -> str:
    if event_count >= 24 and variance > 0:
        return "high"
    if event_count >= 8 and variance > 0:
        return "medium"
    return "low"


def _remove_tile(hand: list[str], code: str) -> None:
    if code in hand:
        hand.remove(code)
        return
    base = Tile.parse(code).base_code
    index = next((index for index, value in enumerate(hand) if Tile.parse(value).base_code == base), None)
    if index is not None:
        hand.pop(index)


class BaselineV1(LuckAlgorithm):
    id = "baseline-v1"
    version = "1.0.0"
    name_key = "algorithms.baselineV1.name"
    description_key = "algorithms.baselineV1.description"

    def supports(self, rules: RuleSet) -> bool:
        return rules.player_count in {3, 4}

    def analyze(self, game: CanonicalGame, options: AnalysisOptions) -> GameLuckAnalysis:
        if not self.supports(game.rules):
            raise AppError("UNSUPPORTED_GAME_MODE", "This algorithm does not support the replay mode.", status_code=422)

        total_delta = defaultdict(float)
        total_variance = defaultdict(float)
        total_events = defaultdict(int)
        component_delta: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        round_results: list[RoundLuckAnalysis] = []

        for round_ in game.rounds:
            hands: dict[int, list[str]] = {seat: [] for seat in range(game.rules.player_count)}
            actual_points = defaultdict(int)
            for event in round_.events:
                score_delta = getattr(event, "score_delta", None)
                if isinstance(score_delta, list) and len(score_delta) == game.rules.player_count:
                    for seat, delta in enumerate(score_delta):
                        actual_points[seat] += int(delta)
            visible: list[str] = []
            dora_indicators: list[str] = []
            pending_special_draws: dict[int, str] = {}
            event_details: list[EventLuckDetail] = []
            round_delta = defaultdict(float)
            round_variance = defaultdict(float)
            round_event_count = defaultdict(int)

            def include(detail: EventLuckDetail) -> None:
                event_details.append(detail)
                round_delta[detail.player] += detail.delta
                round_variance[detail.player] += detail.variance
                round_event_count[detail.player] += 1
                component_delta[detail.player][detail.component] += detail.delta

            def score_indicator(sequence: int, indicator: str, reason: str, seats: list[int]) -> None:
                for seat in seats:
                    if not hands[seat]:
                        continue
                    state = PublicPlayerState(
                        hand_codes=list(hands[seat]),
                        rules=game.rules,
                        visible_codes=list(visible),
                        dora_indicators=list(dora_indicators),
                    )
                    opportunity = dora_indicator_opportunity(state, Tile.parse(indicator))
                    include(
                        EventLuckDetail(
                            sequence=sequence,
                            player=seat,
                            component="dora_reveal",
                            actual=opportunity.actual,
                            expected=opportunity.expected,
                            delta=opportunity.delta,
                            variance=opportunity.variance,
                            z_score=_z(opportunity.delta, opportunity.variance),
                            tile=indicator,
                            explanation_key="analysis.doraReveal",
                            features={"candidateCount": opportunity.candidate_count, "reason": reason},
                        )
                    )
                dora_indicators.append(indicator)
                visible.append(indicator)

            start = next((event for event in round_.events if isinstance(event, RoundStarted)), None)
            if start and start.dora_indicator:
                dora_indicators.append(start.dora_indicator)
                visible.append(start.dora_indicator)
            if start and start.starting_hands:
                for seat, codes in enumerate(start.starting_hands[: game.rules.player_count]):
                    hands[seat] = list(codes)
                    value = hand_value(HandState.from_codes(hands[seat], dora_indicators), game.rules)
                    uses_dealer_distribution = seat == round_.dealer and len(codes) % 3 == 2
                    key = f"{game.rules.player_count}p-{'dealer' if uses_dealer_distribution else 'nondealer'}"
                    distribution = CALIBRATION[key]
                    delta = value - float(distribution["mean"])
                    variance = float(distribution["standard_deviation"]) ** 2
                    detail = EventLuckDetail(
                        sequence=start.sequence,
                        player=seat,
                        component="initial_hand",
                        actual=value,
                        expected=float(distribution["mean"]),
                        delta=delta,
                        variance=variance,
                        z_score=_z(delta, variance),
                        explanation_key="analysis.initialHand",
                        features={
                            "dealer": seat == round_.dealer,
                            "handSize": len(codes),
                            "shanten": HandState.from_codes(hands[seat]).shanten,
                        },
                    )
                    include(detail)

            for event in round_.events:
                if isinstance(event, TileDrawn) and hands[event.actor]:
                    state = PublicPlayerState(
                        hand_codes=list(hands[event.actor]),
                        rules=game.rules,
                        visible_codes=list(visible),
                        dora_indicators=list(dora_indicators),
                    )
                    opportunity = draw_opportunity(state, Tile.parse(event.tile))
                    special_reason = pending_special_draws.pop(event.actor, None)
                    if event.from_rinshan:
                        special_reason = special_reason or "rinshan"
                    component = "special_random" if special_reason else "self_draw"
                    detail = EventLuckDetail(
                        sequence=event.sequence,
                        player=event.actor,
                        component=component,
                        actual=opportunity.actual,
                        expected=opportunity.expected,
                        delta=opportunity.delta,
                        variance=opportunity.variance,
                        z_score=_z(opportunity.delta, opportunity.variance),
                        tile=event.tile,
                        explanation_key="analysis.specialRandom" if special_reason else "analysis.selfDraw",
                        features={
                            "candidateCount": opportunity.candidate_count,
                            **({"reason": special_reason} if special_reason else {}),
                        },
                    )
                    include(detail)
                    hands[event.actor].append(event.tile)
                elif isinstance(event, TileDiscarded):
                    _remove_tile(hands[event.actor], event.tile)
                    visible.append(event.tile)
                    for seat in range(game.rules.player_count):
                        if seat == event.actor or not hands[seat]:
                            continue
                        gift_state = PublicPlayerState(
                            hand_codes=list(hands[seat]),
                            rules=game.rules,
                            visible_codes=list(visible),
                            dora_indicators=list(dora_indicators),
                        )
                        gift_value = best_post_draw_value(gift_state, Tile.parse(event.tile))
                        baseline = hand_value(HandState.from_codes(hands[seat], dora_indicators), game.rules)
                        event_details.append(
                            EventLuckDetail(
                                sequence=event.sequence,
                                player=seat,
                                component="opponent_gift",
                                actual=gift_value,
                                expected=baseline,
                                delta=gift_value - baseline,
                                variance=0,
                                z_score=0,
                                included_in_total=False,
                                tile=event.tile,
                                explanation_key="analysis.opponentGift",
                                features={"discarder": event.actor},
                            )
                        )
                elif isinstance(event, CallEvent):
                    consumed = list(event.consumed_tiles)
                    if event.kind == CallKind.KITA and not consumed:
                        consumed = [event.tile]
                    for code in consumed:
                        _remove_tile(hands[event.actor], code)
                        visible.append(code)
                    if event.kind in {CallKind.DAIMINKAN, CallKind.ANKAN, CallKind.KAKAN}:
                        pending_special_draws[event.actor] = "rinshan"
                    elif event.kind == CallKind.KITA:
                        pending_special_draws[event.actor] = "kita"
                elif isinstance(event, DoraRevealed):
                    if event.reason == "initial":
                        if event.indicator not in dora_indicators:
                            dora_indicators.append(event.indicator)
                            visible.append(event.indicator)
                    else:
                        score_indicator(
                            event.sequence,
                            event.indicator,
                            event.reason,
                            list(range(game.rules.player_count)),
                        )
                elif isinstance(event, WinEvent):
                    for indicator in event.ura_indicators:
                        score_indicator(event.sequence, indicator, "ura", list(event.winners))

            round_players: list[RoundPlayerLuck] = []
            for seat in range(game.rules.player_count):
                delta = round_delta[seat]
                variance = round_variance[seat]
                z_score = _z(delta, variance)
                round_players.append(
                    RoundPlayerLuck(
                        seat=seat,
                        raw_delta=delta,
                        variance=variance,
                        z_score=z_score,
                        score=score_from_z(z_score),
                        confidence=_confidence(round_event_count[seat], variance),
                        actual_points=actual_points[seat],
                    )
                )
                total_delta[seat] += delta
                total_variance[seat] += variance
                total_events[seat] += round_event_count[seat]
            round_results.append(
                RoundLuckAnalysis(
                    round_index=round_.index,
                    label=f"{round_.wind}-{round_.hand}",
                    players=round_players,
                    events=event_details if options.event_details else [],
                )
            )

        players: list[PlayerLuckAnalysis] = []
        for player in game.players:
            variance = total_variance[player.seat]
            z_score = _z(total_delta[player.seat], variance)
            players.append(
                PlayerLuckAnalysis(
                    seat=player.seat,
                    name=player.name,
                    raw_delta=total_delta[player.seat],
                    variance=variance,
                    z_score=z_score,
                    score=score_from_z(z_score),
                    confidence=_confidence(total_events[player.seat], variance),
                    actual_points=game.final_scores[player.seat] - game.rules.initial_score,
                    components=dict(component_delta[player.seat]),
                )
            )
        return GameLuckAnalysis(
            game_hash=game.content_hash,
            algorithm_id=self.id,
            algorithm_version=self.version,
            options=options,
            players=players,
            rounds=round_results,
        )
