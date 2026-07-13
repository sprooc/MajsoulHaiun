import pytest
from pydantic import ValidationError

from app.domain.events import CallEvent, CallKind, TileDrawn, WinEvent
from app.domain.game import CanonicalGame, Player, Round
from app.domain.rules import RuleSet


def make_players(count: int) -> list[Player]:
    return [Player(seat=seat, name=f"P{seat}") for seat in range(count)]


def test_kita_is_valid_only_when_rules_enable_it():
    event = CallEvent(sequence=3, actor=1, kind=CallKind.KITA, tile="4z", consumed_tiles=[])
    game = CanonicalGame(
        external_id="g",
        rules=RuleSet.standard_three_player(),
        players=make_players(3),
        rounds=[],
        final_scores=[35000] * 3,
        final_ranks=[1, 2, 3],
    )
    game.validate_event(event)

    four_player = CanonicalGame(
        external_id="g4",
        rules=RuleSet.standard_four_player(),
        players=make_players(4),
        rounds=[],
        final_scores=[25000] * 4,
        final_ranks=[1, 2, 3, 4],
    )
    with pytest.raises(ValueError, match="kita"):
        four_player.validate_event(event)


def test_win_event_supports_multiple_winners():
    event = WinEvent(sequence=20, winners=[1, 2], loser=0, score_delta=[-12000, 8000, 4000, 0])
    assert event.winners == [1, 2]


def test_round_events_are_discriminated_and_ordered():
    round_ = Round(
        index=0,
        wind="east",
        hand=1,
        dealer=0,
        honba=0,
        riichi_sticks=0,
        starting_scores=[25000] * 4,
        events=[
            {"event_type": "tile_drawn", "sequence": 2, "actor": 0, "tile": "1m"},
            {"event_type": "tile_drawn", "sequence": 1, "actor": 1, "tile": "2m"},
        ],
    )
    assert isinstance(round_.events[0], TileDrawn)
    assert [event.sequence for event in round_.events] == [1, 2]


def test_player_count_must_match_rules():
    with pytest.raises(ValidationError):
        CanonicalGame(
            external_id="bad",
            rules=RuleSet.standard_three_player(),
            players=make_players(4),
            rounds=[],
            final_scores=[25000] * 4,
            final_ranks=[1, 2, 3, 4],
        )
