import argparse
import json
import random
import statistics
from pathlib import Path

from app.algorithms.baseline_v1.hand_value import HandState, hand_value
from app.domain.rules import RuleSet


OUTPUT_PATH = Path(__file__).with_name("calibration.json")


def _deck(rules: RuleSet) -> list[str]:
    deck: list[str] = []
    for code in rules.tile_codes:
        if code[0] == "5" and code[1] in "mps":
            red = rules.red_fives.get(code[1], 0)
            deck.extend([f"0{code[1]}"] * red)
            deck.extend([code] * (4 - red))
        else:
            deck.extend([code] * 4)
    return deck


def generate(seed: int, samples: int) -> dict[str, dict[str, float | int]]:
    rng = random.Random(seed)
    output: dict[str, dict[str, float | int]] = {}
    for rules in (RuleSet.standard_four_player(), RuleSet.standard_three_player()):
        deck = _deck(rules)
        for dealer in (True, False):
            hand_size = 14 if dealer else 13
            values = [hand_value(HandState.from_codes(rng.sample(deck, hand_size)), rules) for _ in range(samples)]
            key = f"{rules.player_count}p-{'dealer' if dealer else 'nondealer'}"
            output[key] = {
                "mean": round(statistics.fmean(values), 9),
                "standard_deviation": round(statistics.pstdev(values), 9),
                "samples": samples,
                "seed": seed,
            }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260713)
    parser.add_argument("--samples", type=int, default=50000)
    arguments = parser.parse_args()
    output = generate(arguments.seed, arguments.samples)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
