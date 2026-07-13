# Root AGENTS.md Design

## Purpose

Create a concise, English-language `AGENTS.md` at the repository root. It will give coding agents the minimum project-specific context needed to make safe, consistent changes without duplicating the README or implementation plan.

## Scope

The file applies to the entire repository and contains four short sections:

1. Project identity: the Chinese product name is “牌运”; “Haiun” is the Japanese reading of “牌運”, and “海运” must not be used.
2. Essential workflow: the primary backend, frontend, build, and shell verification commands.
3. Non-negotiable product rules: no Mahjong Soul credentials or sessions; opponent discards are not main luck; three-player tile and kita rules remain supported; Chinese and English translation key trees stay aligned.
4. Change discipline: preserve unrelated work, keep changes scoped, and run checks appropriate to changed files before reporting completion.

## Exclusions

The file will not repeat the full architecture, algorithm explanation, environment setup, or implementation history. Those details remain in `README.md` and `docs/superpowers/plans/2026-07-13-riichi-luck-analyzer.md`.

## Acceptance Criteria

- A root-level `AGENTS.md` exists and is written in English.
- It is short enough to scan quickly.
- It states the correct product naming explicitly.
- It includes the essential commands and project invariants listed above.
- It introduces no application behavior or configuration changes.
