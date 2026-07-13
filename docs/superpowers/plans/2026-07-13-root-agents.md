# Root AGENTS.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concise English `AGENTS.md` at the repository root for project-wide coding-agent guidance.

**Architecture:** This is a documentation-only change. One root file will define identity, essential verification commands, non-negotiable product rules, and change discipline while referring readers to existing documentation for details.

**Tech Stack:** Markdown, Git, existing Python/FastAPI and React/Vite verification commands

## Global Constraints

- The file must be named `AGENTS.md` and apply to the entire repository.
- The file must be written in English and remain quick to scan.
- The Chinese product name is “牌运”; “Haiun” is the Japanese reading of “牌運”; never call the product “海运”.
- Do not change application behavior or configuration.

---

### Task 1: Add Root Agent Guidance

**Files:**
- Create: `AGENTS.md`
- Reference: `README.md`
- Reference: `docs/superpowers/plans/2026-07-13-riichi-luck-analyzer.md`

**Interfaces:**
- Consumes: the project identity, commands, security boundary, scoring invariants, three-player rules, and localization requirements documented by the existing repository.
- Produces: repository-wide instructions automatically discoverable by coding agents through the root `AGENTS.md` convention.

- [ ] **Step 1: Confirm that no root guidance file will be overwritten**

Run:

```bash
test ! -e AGENTS.md
```

Expected: exit status 0 with no output.

- [ ] **Step 2: Create the concise root guidance**

Create `AGENTS.md` with exactly this content:

```markdown
# Repository Guidelines

## Project Identity

- The Chinese product name is **牌运**.
- **Haiun** is the Japanese reading of “牌運”. Never call the product “海运”.
- Keep user-facing Chinese and English terminology consistent with the existing locale files.

## Essential Commands

- Backend tests: `nix develop -c .venv/bin/python -m pytest backend/tests -v`
- Frontend tests: `nix develop -c npm --prefix frontend test`
- Frontend build: `nix develop -c npm --prefix frontend run build`
- End-to-end tests: `nix develop -c npm --prefix frontend run e2e`
- Shell checks: `bash -n scripts/dev.sh scripts/start.sh` and `shellcheck scripts/dev.sh scripts/start.sh`

## Non-Negotiable Rules

- Never request, store, or transmit Mahjong Soul passwords, OAuth tokens, verification codes, or browser sessions.
- Opponents’ voluntary discards may be shown as `opponent_gift`, but must not contribute to the main luck score.
- Preserve three-player rules: exclude 2–8 manzu tiles and support kita.
- Keep the recursive key trees of the `zh-CN` and `en` translation resources identical.

## Change Discipline

- Keep changes focused and preserve unrelated user work.
- Follow existing backend, frontend, and test patterns; consult `README.md` for project details.
- Run checks appropriate to every changed area before reporting completion.
```

- [ ] **Step 3: Verify the content and Markdown formatting**

Run:

```bash
git diff --check
rg -n '牌运|Haiun|海运|pytest|opponent_gift|2–8 manzu|zh-CN' AGENTS.md
```

Expected: `git diff --check` exits 0, and `rg` prints matching lines for every required identity, workflow, and product invariant.

- [ ] **Step 4: Confirm that the change is documentation-only**

Run:

```bash
git status --short
```

Expected: only `AGENTS.md` is untracked or modified relative to the committed plan state.

- [ ] **Step 5: Commit the guidance file**

```bash
git add AGENTS.md
git commit -m "docs: add repository agent guidance"
```

Expected: one commit containing only `AGENTS.md`.
