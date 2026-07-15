import random

from mahjong.shanten import Shanten

import app.algorithms.baseline_v1.hand_value as hand_value_module
from app.algorithms.baseline_v1.hand_value import HandState, hand_value
from app.algorithms.baseline_v1.hand_value import _ukeire_score, codes_to_34
from app.algorithms.baseline_v1.opportunity import PublicPlayerState, draw_opportunity
from app.domain.rules import RuleSet
from app.domain.tiles import Tile


def _legacy_shanten_and_necessary(tile_counts: tuple[int, ...]) -> tuple[int, int]:
    engine = Shanten()
    shanten = engine.calculate_shanten(tile_counts)
    necessary = 0
    if sum(tile_counts) % 3 != 1:
        return shanten, necessary
    for index, count in enumerate(tile_counts):
        if count >= 4:
            continue
        candidate = list(tile_counts)
        candidate[index] += 1
        if engine.calculate_shanten(candidate) < shanten:
            necessary |= 1 << index
    return shanten, necessary


def _legacy_ukeire(codes: list[str], rules: RuleSet) -> float:
    tile_counts = tuple(codes_to_34(codes))
    _, necessary = _legacy_shanten_and_necessary(tile_counts)
    improving = 0
    for code in rules.tile_codes:
        index = hand_value_module.tile_index(code)
        if necessary & (1 << index):
            improving += 4 - tile_counts[index]
    return min(1.0, improving / 32.0)


def test_native_shanten_and_necessary_tiles_match_legacy_engine():
    fast = getattr(hand_value_module, "_cached_shanten_and_necessary", None)
    assert callable(fast), "native cached shanten helper is not implemented"

    rng = random.Random(20260715)
    deck = [code for code in RuleSet.standard_four_player().tile_codes for _ in range(4)]
    for hand_size in (1, 2, 4, 5, 7, 8, 10, 11, 13, 14):
        for _ in range(4):
            tile_counts = tuple(codes_to_34(rng.sample(deck, hand_size)))
            actual_shanten, actual_necessary = fast(tile_counts)
            expected_shanten, expected_necessary = _legacy_shanten_and_necessary(tile_counts)
            assert actual_shanten == expected_shanten
            if hand_size % 3 == 1:
                assert actual_necessary == expected_necessary


def test_three_player_ukeire_matches_legacy_engine_for_legal_tiles():
    rng = random.Random(20260716)
    rules = RuleSet.standard_three_player()
    deck = [code for code in rules.tile_codes for _ in range(4)]
    for hand_size in (1, 4, 7, 10, 13):
        for _ in range(4):
            codes = rng.sample(deck, hand_size)
            state = HandState.from_codes(codes)
            assert _ukeire_score(state, rules) == _legacy_ukeire(codes, rules)


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
