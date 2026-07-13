from typing import Literal

from pydantic import BaseModel, ConfigDict


class Tile(BaseModel):
    model_config = ConfigDict(frozen=True)

    suit: Literal["m", "p", "s", "z"]
    rank: int
    red: bool = False
    source_text: str

    @classmethod
    def parse(cls, source_text: str) -> "Tile":
        if len(source_text) != 2:
            raise ValueError(f"invalid tile: {source_text}")
        rank_text, suit = source_text
        if suit not in "mpsz" or not rank_text.isdigit():
            raise ValueError(f"invalid tile: {source_text}")
        red = rank_text == "0"
        rank = 5 if red else int(rank_text)
        max_rank = 7 if suit == "z" else 9
        if rank < 1 or rank > max_rank or (red and suit == "z"):
            raise ValueError(f"invalid tile: {source_text}")
        return cls(suit=suit, rank=rank, red=red, source_text=source_text)

    @property
    def code(self) -> str:
        return self.source_text

    @property
    def base_code(self) -> str:
        return f"{self.rank}{self.suit}"
