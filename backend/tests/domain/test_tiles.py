import pytest

from app.domain.rules import RuleSet
from app.domain.tiles import Tile


def test_red_five_round_trip():
    tile = Tile.parse("0m")
    assert (tile.suit, tile.rank, tile.red, tile.source_text) == ("m", 5, True, "0m")
    assert tile.code == "0m"


@pytest.mark.parametrize("code", ["", "10m", "8z", "0z", "xm", "1x"])
def test_invalid_tiles_are_rejected(code):
    with pytest.raises(ValueError):
        Tile.parse(code)


def test_three_player_rule_removes_middle_manzu_and_enables_kita():
    rules = RuleSet.standard_three_player()
    assert rules.player_count == 3
    assert rules.kita_enabled is True
    assert all(f"{rank}m" not in rules.tile_codes for rank in range(2, 9))


def test_four_player_rule_has_all_standard_tile_types():
    rules = RuleSet.standard_four_player()
    assert rules.player_count == 4
    assert len(rules.tile_codes) == 34
    assert rules.kita_enabled is False
