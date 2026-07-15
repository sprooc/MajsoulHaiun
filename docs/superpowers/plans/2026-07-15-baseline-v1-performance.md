# Baseline V1 Exact-Result Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated recursive shanten/ukeire searches with one cached native exact calculation per hand while preserving byte-identical `baseline-v1` results.

**Architecture:** Convert each hand to its normalized 34-count tuple and call `xiangting.calculate_necessary_tiles` with four-player semantics. Derive the existing shanten and ukeire values from that result, retain the current Python engine as fallback/oracle, and leave all downstream hand-value and opportunity formulas untouched.

**Tech Stack:** Python 3.11+, `xiangting` 5.x Rust binding, existing `mahjong` 1.x oracle, pytest, uv lockfile.

## Global Constraints

- Results must be byte-identical for identical inputs.
- Do not parallelize analysis.
- Opponent gifts remain informational and excluded from the main luck score.
- Three-player candidate tiles exclude 2–8 manzu and kita behavior remains supported.
- Keep algorithm ID `baseline-v1` and version `1.0.0`.

---

### Task 1: Specify exact native parity

**Files:**
- Modify: `backend/tests/algorithms/test_hand_value.py`
- Modify: `backend/tests/algorithms/test_baseline_v1.py`

**Interfaces:**
- Consumes: existing `HandState`, `_ukeire_score`, `BaselineV1`, and fixture game.
- Produces: parity requirements for `_cached_shanten_and_necessary(tile_counts: tuple[int, ...]) -> tuple[int, int]`.

- [ ] **Step 1: Add a failing native-helper parity test**

Add seeded valid hands at all supported concealed-hand sizes. Assert that the new helper exists, returns the same shanten as `mahjong.shanten.Shanten`, and returns exactly the bit mask obtained by adding each tile and comparing legacy shanten.

- [ ] **Step 2: Add a failing three-player ukeire parity test**

Build seeded hands from `RuleSet.standard_three_player().tile_codes` and compare `_ukeire_score` with the existing legacy loop, including the 2–8 manzu exclusion.

- [ ] **Step 3: Add a fixture result hash assertion**

Assert that the existing fixture analysis JSON SHA-256 remains `4da3bf90dca169e15b94a7fc01cc5f923dc89b030f4fa2ce6e38b0a3e53f6da6`.

- [ ] **Step 4: Run the focused tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/algorithms/test_hand_value.py backend/tests/algorithms/test_baseline_v1.py -v`

Expected: the helper-existence assertion fails while the legacy behavior/hash assertions pass.

### Task 2: Install and use the native exact evaluator

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `backend/app/algorithms/baseline_v1/hand_value.py`

**Interfaces:**
- Produces: `_cached_shanten_and_necessary(tile_counts: tuple[int, ...]) -> tuple[int, int]`.
- Preserves: `HandState.shanten`, `_ukeire_score`, and `hand_value` observable results.

- [ ] **Step 1: Add the dependency**

Run: `nix develop -c uv add 'xiangting>=5.0.5,<6'`

Expected: `pyproject.toml` and `uv.lock` include `xiangting` and the environment installs a compatible wheel.

- [ ] **Step 2: Implement the minimal cached helper**

Import `PlayerCount` and `calculate_necessary_tiles`. Cache by a 34-count tuple, use `PlayerCount.FOUR` for both modes, return `(replacement_number - 1, necessary_tiles)`, and fall back to a legacy helper only when the binding rejects a valid internal state.

- [ ] **Step 3: Derive ukeire from the returned mask**

Convert the hand once to 34 counts. For each code in `rules.tile_codes`, add `4 - count` only when its bit is present in the necessary-tile mask. Preserve the existing division by `32.0` and cap at `1.0`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/algorithms -v`

Expected: all algorithm tests pass.

### Task 3: Verify full result parity and performance

**Files:**
- No production file changes unless verification reveals an exactness defect.

**Interfaces:**
- Consumes: the eight stored completed analyses in `data/haiun.sqlite3`.
- Produces: canonical JSON equality evidence and an updated sequential benchmark.

- [ ] **Step 1: Compare all stored results**

Load each canonical game and completed stored result, run `BaselineV1().analyze` with the stored options, and assert equality after Pydantic JSON normalization.

- [ ] **Step 2: Benchmark the same replay**

Clear in-memory evaluator caches and time the smallest stored four-player replay (305 events, 137 draws) without profiling or parallelism.

- [ ] **Step 3: Run the full backend suite**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests -v`

Expected: 134 passed and one live integration test skipped, or more passing tests after the new parity coverage is counted.

- [ ] **Step 4: Review the final diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors and only the scoped dependency, implementation, tests, and design/plan files are changed.
