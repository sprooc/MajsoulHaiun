from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from mahjong.shanten import Shanten
from xiangting import PlayerCount as XiangtingPlayerCount
from xiangting import calculate_necessary_tiles

from app.domain.rules import RuleSet
from app.domain.tiles import Tile


WEIGHTS = {
    "shanten": 0.45,
    "ukeire": 0.25,
    "shape": 0.10,
    "visible_value": 0.15,
    "yaku_potential": 0.05,
}

_SHANTEN = Shanten()


@lru_cache(maxsize=64)
def _parse_tile(code: str) -> Tile:
    return Tile.parse(code)


def tile_index(code: str) -> int:
    tile = _parse_tile(code)
    offsets = {"m": 0, "p": 9, "s": 18, "z": 27}
    return offsets[tile.suit] + tile.rank - 1


def codes_to_34(codes: list[str] | tuple[str, ...]) -> list[int]:
    result = [0] * 34
    for code in codes:
        result[tile_index(code)] += 1
    return result


def _legacy_shanten_and_necessary(tile_counts: tuple[int, ...]) -> tuple[int, int]:
    shanten = _SHANTEN.calculate_shanten(tile_counts)
    necessary = 0
    if sum(tile_counts) % 3 != 1:
        return shanten, necessary
    for index, count in enumerate(tile_counts):
        if count >= 4:
            continue
        candidate = list(tile_counts)
        candidate[index] += 1
        if _SHANTEN.calculate_shanten(candidate) < shanten:
            necessary |= 1 << index
    return shanten, necessary


@lru_cache(maxsize=250_000)
def _cached_shanten_and_necessary(tile_counts: tuple[int, ...]) -> tuple[int, int]:
    try:
        # Baseline v1 historically used the rule-agnostic mahjong.Shanten engine
        # for both modes. Three-player legality is applied later in _ukeire_score.
        replacement_number, necessary = calculate_necessary_tiles(
            list(tile_counts),
            XiangtingPlayerCount.FOUR,
        )
    except ValueError:
        return _legacy_shanten_and_necessary(tile_counts)
    return replacement_number - 1, necessary


@dataclass(frozen=True)
class HandState:
    codes: tuple[str, ...]
    dora_indicators: tuple[str, ...] = ()

    @classmethod
    def from_codes(cls, codes: list[str], dora_indicators: list[str] | None = None) -> "HandState":
        return cls(tuple(codes), tuple(dora_indicators or ()))

    @property
    def shanten(self) -> int:
        tile_counts = tuple(codes_to_34(self.codes))
        shanten, _ = _cached_shanten_and_necessary(tile_counts)
        return shanten


def _next_dora(indicator: str) -> str:
    tile = _parse_tile(indicator)
    if tile.suit != "z":
        return f"{tile.rank % 9 + 1}{tile.suit}"
    if tile.rank <= 4:
        return f"{tile.rank % 4 + 1}z"
    return f"{5 + (tile.rank - 5 + 1) % 3}z"


def _ukeire_score(state: HandState, rules: RuleSet) -> float:
    tile_counts = tuple(codes_to_34(state.codes))
    _, necessary = _cached_shanten_and_necessary(tile_counts)
    improving = 0
    for code in rules.tile_codes:
        index = tile_index(code)
        if necessary & (1 << index):
            improving += 4 - tile_counts[index]
    return min(1.0, improving / 32.0)


def _shape_score(codes: tuple[str, ...]) -> float:
    tiles = [_parse_tile(code) for code in codes]
    counts = Counter(tile.base_code for tile in tiles)
    pairs = sum(1 for count in counts.values() if count >= 2)
    connected = 0
    for suit in "mps":
        ranks = {tile.rank for tile in tiles if tile.suit == suit}
        connected += sum(1 for rank in range(1, 9) if rank in ranks and rank + 1 in ranks)
    return min(1.0, (pairs * 0.12) + (connected * 0.07))


def _visible_value(state: HandState) -> float:
    red_bonus = sum(1 for code in state.codes if _parse_tile(code).red) * 0.18
    dora_codes = [_next_dora(indicator) for indicator in state.dora_indicators]
    normalized = [_parse_tile(code).base_code for code in state.codes]
    dora_bonus = sum(normalized.count(code) for code in dora_codes) * 0.12
    return min(1.0, red_bonus + dora_bonus)


def _yaku_potential(codes: tuple[str, ...]) -> float:
    tiles = [_parse_tile(code) for code in codes]
    simple_only = all(tile.suit != "z" and 2 <= tile.rank <= 8 for tile in tiles)
    honor_pairs = sum(
        1
        for code, count in Counter(tile.base_code for tile in tiles).items()
        if code.endswith("z") and count >= 2
    )
    return min(1.0, (0.55 if simple_only else 0.0) + honor_pairs * 0.18)


@lru_cache(maxsize=100_000)
def _cached_hand_value(
    codes: tuple[str, ...],
    dora_indicators: tuple[str, ...],
    player_count: int,
    tile_codes: tuple[str, ...],
    red_fives: tuple[tuple[str, int], ...],
) -> float:
    state = HandState(codes, dora_indicators)
    rules = RuleSet(
        player_count=player_count,
        initial_score=35000 if player_count == 3 else 25000,
        red_fives=dict(red_fives),
        tile_codes=tile_codes,
        tsumo_loss=False if player_count == 3 else None,
        kita_enabled=player_count == 3,
    )
    shanten_score = max(0.0, min(1.0, (6 - state.shanten) / 6.0))
    values = {
        "shanten": shanten_score,
        "ukeire": _ukeire_score(state, rules),
        "shape": _shape_score(state.codes),
        "visible_value": _visible_value(state),
        "yaku_potential": _yaku_potential(state.codes),
    }
    return sum(WEIGHTS[key] * value for key, value in values.items())


def hand_value(state: HandState, rules: RuleSet) -> float:
    if len(state.codes) % 3 == 2:
        discard_states = {
            tuple(sorted(state.codes[:index] + state.codes[index + 1 :]))
            for index in range(len(state.codes))
        }
        return max(
            hand_value(
                HandState(codes, state.dora_indicators),
                rules,
            )
            for codes in discard_states
        )
    return _cached_hand_value(
        tuple(sorted(state.codes)),
        tuple(sorted(state.dora_indicators)),
        rules.player_count,
        rules.tile_codes,
        tuple(sorted(rules.red_fives.items())),
    )
