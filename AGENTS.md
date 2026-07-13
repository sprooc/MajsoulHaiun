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
