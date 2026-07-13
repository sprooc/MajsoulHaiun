from typing import Literal

from pydantic import BaseModel, ConfigDict


class RuleSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_count: Literal[3, 4]
    game_length: Literal["east", "south"] = "south"
    initial_score: int
    red_fives: dict[str, int]
    open_tanyao: bool = True
    tsumo_loss: bool | None = None
    kita_enabled: bool = False
    tile_codes: tuple[str, ...]
    source_rules: dict[str, object] = {}

    @classmethod
    def standard_four_player(cls) -> "RuleSet":
        codes = tuple(f"{rank}{suit}" for suit in "mps" for rank in range(1, 10)) + tuple(
            f"{rank}z" for rank in range(1, 8)
        )
        return cls(
            player_count=4,
            initial_score=25000,
            red_fives={"m": 1, "p": 1, "s": 1},
            tile_codes=codes,
        )

    @classmethod
    def standard_three_player(cls) -> "RuleSet":
        codes = ("1m", "9m") + tuple(
            f"{rank}{suit}" for suit in "ps" for rank in range(1, 10)
        ) + tuple(f"{rank}z" for rank in range(1, 8))
        return cls(
            player_count=3,
            initial_score=35000,
            red_fives={"m": 0, "p": 1, "s": 1},
            tsumo_loss=False,
            kita_enabled=True,
            tile_codes=codes,
        )

    def permits_tile(self, code: str) -> bool:
        normalized = "5" + code[1:] if len(code) == 2 and code[0] == "0" else code
        return normalized in self.tile_codes
