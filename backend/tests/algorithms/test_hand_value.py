from app.algorithms.baseline_v1.hand_value import HandState, hand_value
from app.algorithms.baseline_v1.opportunity import PublicPlayerState, draw_opportunity
from app.domain.rules import RuleSet
from app.domain.tiles import Tile


def test_lower_shanten_is_more_valuable():
    one_shanten = HandState.from_codes(
        ["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "1z", "1z"]
    )
    two_shanten = HandState.from_codes(
        ["1m", "3m", "5m", "1p", "3p", "5p", "1s", "3s", "5s", "1z", "2z", "3z", "4z"]
    )
    assert hand_value(one_shanten, RuleSet.standard_four_player()) > hand_value(
        two_shanten, RuleSet.standard_four_player()
    )


def test_red_five_changes_visible_value_once():
    normal = HandState.from_codes(
        ["5p", "1m", "2m", "3m", "4m", "5m", "6m", "2s", "3s", "4s", "7s", "8s", "9s"]
    )
    red = HandState.from_codes(
        ["0p", "1m", "2m", "3m", "4m", "5m", "6m", "2s", "3s", "4s", "7s", "8s", "9s"]
    )
    difference = hand_value(red, RuleSet.standard_four_player()) - hand_value(
        normal, RuleSet.standard_four_player()
    )
    assert 0 < difference < 0.2


def test_three_player_removed_manzu_have_zero_draw_probability():
    state = PublicPlayerState.from_codes(
        ["1m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "1s", "2s", "3s", "1z", "1z"],
        RuleSet.standard_three_player(),
    )
    assert "2m" not in state.remaining_tile_counts
    assert "8m" not in state.remaining_tile_counts


def test_draw_opportunity_compares_actual_to_weighted_legal_candidates():
    state = PublicPlayerState.from_codes(
        ["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "1z", "1z"],
        RuleSet.standard_four_player(),
    )
    result = draw_opportunity(state, Tile.parse("9s"))
    assert result.variance >= 0
    assert result.delta == result.actual - result.expected
    assert result.candidate_count > 0


def test_fourteen_tile_hand_value_uses_the_best_legal_discard():
    rules = RuleSet.standard_four_player()
    codes = ["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "9s", "1z", "1z"]
    expected = max(
        hand_value(HandState.from_codes(codes[:index] + codes[index + 1 :]), rules)
        for index in range(len(codes))
    )

    assert hand_value(HandState.from_codes(codes), rules) == expected
