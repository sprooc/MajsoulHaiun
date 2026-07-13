from app.algorithms.baseline_v1.algorithm import CALIBRATION, BaselineV1, score_from_z
from app.domain.analysis import AnalysisOptions
from app.domain.events import CallEvent, CallKind, DoraRevealed, RoundStarted, TileDiscarded, TileDrawn, WinEvent
from app.domain.game import CanonicalGame, Player, Round
from app.domain.rules import RuleSet


def fixture_game() -> CanonicalGame:
    starting_hands = [
        ["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "1z", "1z"],
        ["1m", "3m", "5m", "1p", "3p", "5p", "1s", "3s", "5s", "2z", "3z", "4z", "5z"],
        ["1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p", "1s", "1s", "2s", "3s"],
        ["1m", "1m", "2m", "2m", "3m", "3m", "4s", "4s", "5s", "5s", "6s", "6s", "7z"],
    ]
    events = [
        RoundStarted(sequence=0, dealer=0, scores=[25000] * 4, dora_indicator="1z", starting_hands=starting_hands),
        TileDrawn(sequence=1, actor=0, tile="9s"),
        TileDiscarded(sequence=2, actor=0, tile="7s"),
        TileDiscarded(sequence=3, actor=1, tile="5z"),
        WinEvent(sequence=4, winners=[0], loser=1, score_delta=[8000, -8000, 0, 0]),
    ]
    return CanonicalGame(
        source="fixture",
        external_id="algorithm-fixture",
        rules=RuleSet.standard_four_player(),
        players=[Player(seat=seat, name=f"P{seat}") for seat in range(4)],
        rounds=[
            Round(
                index=0,
                wind="east",
                hand=1,
                dealer=0,
                honba=0,
                riichi_sticks=0,
                starting_scores=[25000] * 4,
                events=events,
            )
        ],
        final_scores=[33000, 17000, 25000, 25000],
        final_ranks=[1, 4, 2, 3],
    )


def test_score_mapping_is_bounded_and_centered():
    assert score_from_z(0) == 50
    assert score_from_z(100) == 100
    assert score_from_z(-100) == 0


def test_calibration_matches_seeded_50000_sample_generation():
    assert CALIBRATION == {
        "3p-dealer": {
            "mean": 0.504355233,
            "standard_deviation": 0.066298026,
            "samples": 50000,
            "seed": 20260713,
        },
        "3p-nondealer": {
            "mean": 0.46552913,
            "standard_deviation": 0.065062042,
            "samples": 50000,
            "seed": 20260713,
        },
        "4p-dealer": {
            "mean": 0.49142732,
            "standard_deviation": 0.067149735,
            "samples": 50000,
            "seed": 20260713,
        },
        "4p-nondealer": {
            "mean": 0.455649053,
            "standard_deviation": 0.065988612,
            "samples": 50000,
            "seed": 20260713,
        },
    }


def test_thirteen_tile_dealer_snapshot_uses_predraw_calibration():
    analysis = BaselineV1().analyze(fixture_game(), AnalysisOptions(event_details=True))
    dealer_initial = next(
        event
        for event in analysis.rounds[0].events
        if event.component == "initial_hand" and event.player == 0
    )

    assert dealer_initial.expected == CALIBRATION["4p-nondealer"]["mean"]


def test_identical_inputs_return_identical_json():
    algorithm = BaselineV1()
    first = algorithm.analyze(fixture_game(), AnalysisOptions(event_details=True))
    second = algorithm.analyze(fixture_game(), AnalysisOptions(event_details=True))
    assert first.model_dump_json() == second.model_dump_json()


def test_opponent_discard_is_informational_and_excluded_from_luck_total():
    analysis = BaselineV1().analyze(fixture_game(), AnalysisOptions(event_details=True))
    gifts = [event for event in analysis.rounds[0].events if event.component == "opponent_gift"]
    assert gifts
    assert all(event.included_in_total is False for event in gifts)


def test_analysis_reports_every_player_and_keeps_actual_points_separate():
    analysis = BaselineV1().analyze(fixture_game(), AnalysisOptions(event_details=True))
    assert len(analysis.players) == 4
    assert analysis.players[0].actual_points == 8000
    assert analysis.rounds[0].players[0].actual_points == 8000
    assert 0 <= analysis.players[0].score <= 100
    assert analysis.algorithm_id == "baseline-v1"
    assert analysis.algorithm_version == "1.0.0"


def test_kan_dora_reveal_is_scored_once_for_every_player():
    game = fixture_game()
    start = game.rounds[0].events[0]
    game.rounds[0].events = [
        start,
        DoraRevealed(sequence=1, indicator="4p", reason="kan"),
    ]

    analysis = BaselineV1().analyze(game, AnalysisOptions(event_details=True))
    details = [event for event in analysis.rounds[0].events if event.component == "dora_reveal"]

    assert len(details) == 4
    assert {event.player for event in details} == {0, 1, 2, 3}
    assert all(event.features["reason"] == "kan" for event in details)
    assert all("dora_reveal" in player.components for player in analysis.players)


def test_rinshan_draw_is_special_random_instead_of_self_draw():
    game = fixture_game()
    start = game.rounds[0].events[0]
    game.rounds[0].events = [
        start,
        TileDrawn(sequence=1, actor=0, tile="9s", from_rinshan=True),
    ]

    analysis = BaselineV1().analyze(game, AnalysisOptions(event_details=True))
    draw_details = [event for event in analysis.rounds[0].events if event.sequence == 1]

    assert [event.component for event in draw_details] == ["special_random"]
    assert "special_random" in analysis.players[0].components
    assert "self_draw" not in analysis.players[0].components


def test_kita_replacement_draw_is_special_random():
    rules = RuleSet.standard_three_player()
    starting_hands = [
        ["1m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "1s", "2s", "3s", "1z", "1z"],
        ["1m", "9m", "2p", "3p", "4p", "5p", "6p", "7p", "2s", "3s", "4s", "4z", "5z"],
        ["1m", "9m", "3p", "4p", "5p", "6p", "7p", "8p", "3s", "4s", "5s", "6z", "7z"],
    ]
    game = CanonicalGame(
        source="fixture",
        external_id="kita-fixture",
        rules=rules,
        players=[Player(seat=seat, name=f"P{seat}") for seat in range(3)],
        rounds=[
            Round(
                index=0,
                wind="east",
                hand=1,
                dealer=0,
                honba=0,
                riichi_sticks=0,
                starting_scores=[35000] * 3,
                events=[
                    RoundStarted(
                        sequence=0,
                        dealer=0,
                        scores=[35000] * 3,
                        dora_indicator="9m",
                        starting_hands=starting_hands,
                    ),
                    CallEvent(
                        sequence=1,
                        actor=1,
                        kind=CallKind.KITA,
                        tile="4z",
                        consumed_tiles=["4z"],
                    ),
                    TileDrawn(sequence=2, actor=1, tile="9p"),
                ],
            )
        ],
        final_scores=[35000] * 3,
        final_ranks=[1, 2, 3],
    )

    analysis = BaselineV1().analyze(game, AnalysisOptions(event_details=True))
    replacement = [event for event in analysis.rounds[0].events if event.sequence == 2]

    assert [event.component for event in replacement] == ["special_random"]
    assert replacement[0].features["reason"] == "kita"


def test_ura_dora_is_scored_only_for_winners():
    game = fixture_game()
    start = game.rounds[0].events[0]
    game.rounds[0].events = [
        start,
        WinEvent(
            sequence=1,
            winners=[0],
            loser=1,
            score_delta=[8000, -8000, 0, 0],
            ura_indicators=["4p"],
        ),
    ]

    analysis = BaselineV1().analyze(game, AnalysisOptions(event_details=True))
    details = [event for event in analysis.rounds[0].events if event.component == "dora_reveal"]

    assert [event.player for event in details] == [0]
    assert details[0].features["reason"] == "ura"
