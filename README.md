# 牌运 Haiun

**Haiun** (牌运, the Japanese reading of “牌運”) is a s explainable luck analyzer for riichi mahjong replays. It separates random opportunity from match results so that players can review how chance affected each seat without treating luck as skill.

Haiun supports both four-player mahjong and three-player mahjong, stores replay data and analysis results locally, and provides an English and Simplified Chinese web interface.

## Features

- Search four-player and three-player Mahjong Soul (雀魂) players and recent games through the public Amae-Koromo index.
- Import Mahjong Soul share links, replay IDs, decoded JSON, or Haiun canonical JSON.
- Cache raw and canonical replays by Mahjong Soul replay ID to avoid unnecessary downloads on repeated imports.
- Analyze starting hands, self-draws, dora reveals, and other random events with the deterministic `baseline-v1` algorithm.
- Compare players using a 0–100 luck score, z-score, confidence level, component breakdown, and event timeline.
- Show match points separately from luck results.
- Support three-player rules, including the removal of 2–8 manzu, kita, sanma scoring, and tsumo-loss rules.
- Preserve opponents’ voluntary discards as `opponent_gift` events while excluding them from the main luck score.

## Quick Start

### Nix / NixOS

Create the development environment and install dependencies:

```bash
nix develop
uv venv .venv
uv pip install -e '.[test]'
npm --prefix frontend install
```

Run the development servers:

```bash
nix run .#dev
```

Build the frontend and start the production server:

```bash
nix run .#start
```

### Standard Linux

Requirements:

- Python 3.11 or newer
- Node.js 22 or newer
- npm
- SQLite
- Bash

Create the environment and install dependencies:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'
npm --prefix frontend install
```

Then start Haiun in development or production mode:

```bash
./scripts/dev.sh
./scripts/start.sh
```

The scripts prefer `uv` when it is available and otherwise use the standard Python `venv` and `pip` tools. They resolve the repository root from their own location, so they can be launched from any working directory.

By default, the production server is available at `http://127.0.0.1:8765` and also listens on the local network.

### Docker

Haiun includes two Docker Compose configurations:

- `compose.simple.yml` runs the application directly on port `8765`.
- `compose.production.yml` adds Nginx and a Grafana, Loki, Prometheus, and Alloy monitoring stack.

See the [Docker deployment guide](docs/docker.md) for prerequisites, configuration, TLS guidance, monitoring, backups, upgrades, build proxies, and resource limits.

## Configuration

Haiun uses a local TOML file. Copy the example before starting the application:

```bash
cp config/config.example.toml config/config.toml
chmod 600 config/config.toml
```

Configure one or more accounts for Mahjong Soul's China server and an administrator password:

```toml
timeout_seconds = 15

[[accounts]]
username = "first-account@example.com"
password = "replace-me"
host = "https://game.maj-soul.com"

[[accounts]]
username = "backup-account@example.com"
password = "replace-me"
host = "https://game.maj-soul.com"

[admin]
password = "replace-with-a-long-unique-password"
session_hours = 12
```

Accounts are tried from top to bottom. If an account cannot sign in or access a replay, Haiun continues with the next account. Set `HAIUN_CONFIG` to use a different configuration path.

Keep the real configuration file private. Do not place Mahjong Soul credentials or the administrator password in the example file, documentation, logs, or version control. The current username/password replay-fetch flow is intended for Mahjong Soul’s China server. OAuth tokens, email verification codes, and browser sessions are neither requested nor supported.

## Access Model

Haiun opens in visitor mode by default. Visitors can search for games, import replays, and start analyses, but they cannot browse the global analysis list.

Each submission receives a separate `/results/<random-uuid>` URL. Cached computation may be reused when the same replay is analyzed again, but an existing result URL is never replaced. Result URLs act as capability links: they are not publicly enumerable, but anyone with the complete URL can open them. Share them accordingly.

The administrator page is available at `/admin` and is intentionally absent from public navigation. An administrator password of at least 12 characters grants access to all analysis tasks and protected management operations. Sessions last 12 hours by default, and repeated failed sign-in attempts are temporarily rate-limited.

## Network and Security

Haiun listens on `0.0.0.0:8765` by default so other devices on the local network can connect. Common environment variables include:

| Variable                  | Purpose                                              | Default                      |
| ------------------------- | ---------------------------------------------------- | ---------------------------- |
| `HAIUN_HOST`            | Backend bind address                                 | `0.0.0.0`                  |
| `HAIUN_PORT`            | Backend port                                         | `8765`                     |
| `HAIUN_DATA_DIR`        | Local state directory                                | `./data`                   |
| `HAIUN_CONFIG`          | Configuration file path                              | `./config/config.toml`     |
| `HAIUN_ALLOWED_ORIGINS` | Comma-separated CORS allowlist                       | No unrelated origins allowed |
| `HAIUN_OPEN_BROWSER`    | Open the production URL automatically when supported | `1`                        |
| `HAIUN_REBUILD`         | Force a frontend rebuild when set to `1`           | `0`                        |

Set `HAIUN_HOST=127.0.0.1` to restrict the service to the local machine.

Public deployments must use a TLS-terminating reverse proxy, an appropriate firewall policy, and request rate limiting. The administrator password protects management functionality only; it does not make visitor search, replay import, analysis, or shared result URLs private.

Mahjong Soul credentials and the administrator password are read only by the backend from the local TOML file. They are not written to the database, logs, or error responses. Administrator cookies are HTTP-only, and the database stores only hashes of random session tokens.

## How the Luck Score Works

The `baseline-v1` algorithm compares each observed random result with the weighted expectation of all legal candidate results available at that moment. It accumulates the raw deviation and variance, calculates a z-score, and maps that value to a 0–100 score:

```text
luck score = clamp(50 + 15 × z, 0, 100)
```

A score near 50 indicates results close to expectation. Higher values indicate more favorable random opportunities; lower values indicate less favorable ones. The score is not a skill rating and does not predict final placement.

Starting-hand calibration uses 50,000 generated samples with the fixed seed `20260713` for four-player dealer, four-player non-dealer, three-player dealer, and three-player non-dealer states. Dealer hands are evaluated after the best legal discard. Given identical dependency versions, replay data, algorithm version, and options, the analysis is deterministic.

Red fives, visible dora, kan dora, ura dora, rinshan draws, and kita are evaluated through separate incremental paths to avoid double-counting. Match points remain separate from the luck score, and voluntary opponent discards never contribute to the main score.

## Replay Data

The default state directory is `data/`. It contains the SQLite database, raw replays, canonical game records, and cached analyses, and is ignored by Git. Set `HAIUN_DATA_DIR` to store this data elsewhere.

To back up a local installation, copy the state directory. To remove all local state, stop Haiun and delete the directory.

Uploaded replay files are limited to 32 MiB. Haiun accepts decoded JSON and canonical Haiun JSON. For Mahjong Soul links, it stores the original `ResGameRecord` protobuf and decodes it with the protocol descriptors included in this repository. The descriptors can be refreshed from official static assets with:

```bash
python scripts/update_majsoul_protocol.py
```

Executable files and archives are rejected.

Amae-Koromo is an unofficial public index, so player search and game listings may be delayed or temporarily unavailable. Full replay access depends on whether a locally configured Mahjong Soul account can sign in and access the requested replay. If no account can retrieve it, Haiun returns `REPLAY_FETCH_UNAVAILABLE`; configuration and network failures use their corresponding typed errors.

## Development

The backend is built with FastAPI and SQLite. The frontend uses React, TypeScript, and Vite.

Run the complete project checks with:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
bash -n scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
nix develop -c shellcheck scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
```

When changing translations, keep the recursive key structure of the `zh-CN` and `en` locale resources identical.

## Acknowledgments

Haiun uses the public player and game index provided by [SAPikachu/amae-koromo](https://github.com/SAPikachu/amae-koromo). Thanks to its maintainers and contributors for making this data accessible to the riichi mahjong community.

## Important Notes

- Haiun is an independent project and is not affiliated with Mahjong Soul or Amae-Koromo.
- Luck analysis describes outcomes under a specific algorithm; it should not be interpreted as a complete evaluation of player decisions or ability.
- Keep replay-fetch credentials local and never share configuration files containing secrets.
