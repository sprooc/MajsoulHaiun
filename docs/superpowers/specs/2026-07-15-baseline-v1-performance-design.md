# Baseline V1 Exact-Result Performance Design

## Goal

Reduce `baseline-v1` replay analysis latency without changing any hand value, event value, aggregate score, explanation payload, three-player legality rule, algorithm ID, or algorithm version. The implementation must remain single-process and single-threaded from the algorithm's perspective.

## Root cause

Each draw evaluates every remaining tile and every legal post-draw discard. Every resulting hand value then evaluates ukeire by running the recursive pure-Python shanten engine once for the current hand and once for every legal tile type. A 305-event replay currently performs 575,779 uncached shanten calculations and takes about 58 seconds.

## Selected approach

Add `xiangting>=5.0.5,<6`, whose Rust implementation exposes `calculate_necessary_tiles`. For one 34-count hand this returns both the replacement number and a bit mask of tiles that reduce it. Subtracting one from the replacement number gives the current shanten value; summing `4 - hand_count` for legal tiles in the returned mask gives the existing ukeire value.

Always call the native engine with four-player shanten semantics. The current `mahjong.shanten.Shanten` implementation is unaware of `RuleSet`, including for three-player games. Three-player behavior remains identical by applying the existing `rules.tile_codes` mask when summing ukeire, so 2–8 manzu remain excluded and kita handling remains unchanged.

## Compatibility and fallback

Keep the existing `mahjong` dependency and legacy shanten engine as a compatibility oracle in tests and as a fallback if the native binding rejects an internally generated hand. Cache native results by the normalized 34-count tuple. Do not change floating-point formulas, weight order, candidate weighting, best-discard selection, event construction, or aggregation.

Keep `baseline-v1` at version `1.0.0` because its observable result is required to remain identical.

## Verification

- Add seeded randomized parity tests covering 1/2, 4/5, 7/8, 10/11, and 13/14-tile hands.
- Compare native shanten and necessary-tile masks with the current recursive implementation.
- Verify three-player ukeire parity while excluding 2–8 manzu.
- Preserve a byte-level fixture analysis hash.
- Compare all eight stored completed `baseline-v1` results with fresh analyses after the change.
- Run all backend tests and repeat the same unprofiled replay benchmark.

## Non-goals

- No parallel processing, threading, process pools, sampling, approximation, altered cache keys for persisted analyses, or score recalibration.
- No opponent-gift scoring changes and no changes to the recursive `zh-CN`/`en` locale trees.
