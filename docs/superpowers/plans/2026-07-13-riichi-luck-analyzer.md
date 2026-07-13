# Riichi Mahjong Luck Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local bilingual Web application that searches Amae-Koromo players and games, imports standard four-player and three-player riichi-mahjong replays, normalizes them, and calculates explainable per-round and per-game luck scores for every player.

**Architecture:** Use a React/TypeScript browser UI served by a FastAPI application. Keep platform acquisition, raw replay storage, canonical game events, and derived analyses in separate modules so a future source or algorithm is added by implementing a normal code interface and registering it. Persist repository-local state in SQLite and default to LAN-capable Linux operation with an environment override for loopback-only binding.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, httpx, protobuf, pytest, React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, i18next, TanStack Query, ECharts, Vitest, Playwright.

## Global Constraints

- The application binds to `0.0.0.0` by default for LAN access; `HAIUN_HOST=127.0.0.1` restores loopback-only operation. It has no authentication and must not be exposed directly to the public Internet.
- The application never requests, stores, or transmits a Mahjong Soul account password, OAuth token, email code, or browser session.
- Chinese (`zh-CN`) and English (`en`) are complete first-class locales; UI code must use translation keys rather than embedded display text.
- Standard four-player and three-player riichi mahjong are supported; unknown activity modes return `UNSUPPORTED_GAME_MODE` instead of being silently analyzed.
- Three-player rules include kita, missing manzu tiles, player-count-specific scoring, and possible tsumo-loss differences.
- Algorithms are ordinary Python implementations of `LuckAlgorithm` registered in source code; there is no dynamic plugin loader.
- Raw source bytes, canonical facts, and derived analysis results remain separate and independently versioned.
- `baseline-v1` measures random opportunity quality and must not score an opponent's voluntary discard as the winner's wall luck.
- Red fives, normal dora, kan dora, ura dora, rinshan, and kita must not be counted twice across components.
- Identical replay hash, algorithm version, and options must produce an identical cached result.
- Amae-Koromo is an unofficial public index. Its anonymous APIs can supply player matches and replay UUIDs, but anonymous raw-replay RPC access is not guaranteed. When raw bytes are unavailable, return `REPLAY_FETCH_UNAVAILABLE`, preserve match metadata, and offer link/file import without asking for Mahjong Soul credentials.

---

## Planned File Structure

```text
Haiun/
├── pyproject.toml
├── package.json
├── README.md
├── scripts/
│   ├── dev.sh
│   ├── start.sh
│   └── update_majsoul_protocol.py
├── backend/
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial.py
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── errors.py
│   │   ├── db.py
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── sources.py
│   │   │   ├── replays.py
│   │   │   └── analyses.py
│   │   ├── domain/
│   │   │   ├── tiles.py
│   │   │   ├── rules.py
│   │   │   ├── events.py
│   │   │   ├── game.py
│   │   │   └── analysis.py
│   │   ├── models/
│   │   │   ├── replay.py
│   │   │   ├── game.py
│   │   │   └── analysis.py
│   │   ├── repositories/
│   │   │   ├── replay_repository.py
│   │   │   └── analysis_repository.py
│   │   ├── sources/
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── amae_koromo.py
│   │   │   ├── local_file.py
│   │   │   └── majsoul/
│   │   │       ├── locator.py
│   │   │       ├── protocol.py
│   │   │       ├── fetcher.py
│   │   │       ├── decoder.py
│   │   │       ├── canonicalizer.py
│   │   │       └── protocol/liqi.json
│   │   ├── algorithms/
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   └── baseline_v1/
│   │   │       ├── algorithm.py
│   │   │       ├── hand_value.py
│   │   │       ├── opportunity.py
│   │   │       ├── calibration.py
│   │   │       └── calibration.json
│   │   └── services/
│   │       ├── import_service.py
│   │       └── analysis_service.py
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       ├── domain/
│       ├── sources/
│       ├── algorithms/
│       ├── services/
│       └── api/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── app.tsx
    │   ├── api/client.ts
    │   ├── i18n/index.ts
    │   ├── locales/zh-CN/*.json
    │   ├── locales/en/*.json
    │   ├── components/
    │   ├── pages/
    │   │   ├── home-page.tsx
    │   │   ├── player-page.tsx
    │   │   ├── game-analysis-page.tsx
    │   │   └── settings-page.tsx
    │   └── test/
    └── tests/e2e/
```

### Task 1: Bootstrap the local backend and repository tooling

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `.gitignore`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/api/test_health.py`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Produces: `GET /api/health -> {"status": "ok", "version": str}`
- Produces: `Settings.host == "0.0.0.0"` and a repository-local SQLite path.

- [ ] **Step 1: Initialize Git and declare Python dependencies**

```toml
[project]
name = "haiun"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.34,<1",
  "pydantic-settings>=2.7,<3",
  "sqlalchemy>=2.0,<3",
  "alembic>=1.14,<2",
  "aiosqlite>=0.20,<1",
  "httpx>=0.28,<1",
  "protobuf>=5,<7",
  "mahjong>=1.3,<2",
]

[project.optional-dependencies]
test = ["pytest>=8,<9", "pytest-asyncio>=0.25,<1", "respx>=0.22,<1"]

[tool.pytest.ini_options]
pythonpath = ["backend"]
testpaths = ["backend/tests"]
asyncio_mode = "auto"
```

Run: `git init`

Expected: `.git` is created and `git status --short` succeeds.

- [ ] **Step 2: Write the failing health and binding tests**

```python
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_default_host_supports_linux_lan_access():
    assert Settings().host == "0.0.0.0"


def test_health_endpoint():
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 3: Run the tests and confirm the missing modules fail**

Run: `python -m pytest backend/tests/api/test_health.py -v`

Expected: FAIL because `app.config` and `app.main` do not exist.

- [ ] **Step 4: Implement minimal settings and the health route**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAIUN_")
    host: str = "0.0.0.0"
    port: int = 8765
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    version: str = "0.1.0"
```

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
```

```python
from fastapi import FastAPI
from app.api.health import router as health_router
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Haiun", version=(settings or Settings()).version)
    app.include_router(health_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the backend tests**

Run: `python -m pytest backend/tests/api/test_health.py -v`

Expected: 2 tests PASS.

- [ ] **Step 6: Commit the bootstrap**

```bash
git add .gitignore pyproject.toml package.json backend
git commit -m "chore: bootstrap local FastAPI application"
```

### Task 2: Bootstrap the React shell and bilingual resource system

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app.tsx`
- Create: `frontend/src/i18n/index.ts`
- Create: `frontend/src/locales/zh-CN/common.json`
- Create: `frontend/src/locales/en/common.json`
- Create: `frontend/src/test/app.test.tsx`

**Interfaces:**
- Produces: `setLanguage(language: "zh-CN" | "en") -> Promise<void>`
- Produces: a top-level app shell with navigation, language switcher, and backend health status.

- [ ] **Step 1: Declare frontend dependencies and scripts**

```json
{
  "name": "haiun-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.66.0",
    "echarts": "^5.6.0",
    "i18next": "^24.2.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-i18next": "^15.4.0",
    "react-router-dom": "^7.1.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.50.0",
    "@testing-library/react": "^16.2.0",
    "@vitejs/plugin-react": "^4.4.0",
    "typescript": "^5.7.0",
    "vite": "^6.1.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 2: Write a failing locale-switch test**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { App } from "../app";

it("switches the application shell from Chinese to English", async () => {
  render(<App />);
  expect(await screen.findByText("牌运")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(await screen.findByText("Luck Analysis")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run the frontend test and verify failure**

Run: `npm --prefix frontend install && npm --prefix frontend test`

Expected: FAIL because the React application and i18n initialization do not exist.

- [ ] **Step 4: Implement resource-based localization**

```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zhCN from "../locales/zh-CN/common.json";
import en from "../locales/en/common.json";

void i18n.use(initReactI18next).init({
  resources: { "zh-CN": { common: zhCN }, en: { common: en } },
  lng: localStorage.getItem("language") ?? "zh-CN",
  fallbackLng: "en",
  defaultNS: "common",
  interpolation: { escapeValue: false },
});

export async function setLanguage(language: "zh-CN" | "en") {
  localStorage.setItem("language", language);
  await i18n.changeLanguage(language);
}

export default i18n;
```

```json
{"app":{"title":"牌运"},"language":{"english":"English","chinese":"中文"}}
```

```json
{"app":{"title":"Luck Analysis"},"language":{"english":"English","chinese":"中文"}}
```

- [ ] **Step 5: Run unit tests and production build**

Run: `npm --prefix frontend test && npm --prefix frontend run build`

Expected: locale test PASS and Vite build succeeds.

- [ ] **Step 6: Commit the bilingual shell**

```bash
git add frontend
git commit -m "feat: add bilingual React application shell"
```

### Task 3: Define canonical tiles, rules, events, and game models

**Files:**
- Create: `backend/app/domain/tiles.py`
- Create: `backend/app/domain/rules.py`
- Create: `backend/app/domain/events.py`
- Create: `backend/app/domain/game.py`
- Create: `backend/tests/domain/test_tiles.py`
- Create: `backend/tests/domain/test_game.py`

**Interfaces:**
- Produces: `Tile.parse(source_text: str) -> Tile`
- Produces: `RuleSet.standard_four_player()` and `RuleSet.standard_three_player()`.
- Produces: `CanonicalGame`, `Round`, and discriminated event models.

- [ ] **Step 1: Write failing tile and rule tests**

```python
from app.domain.rules import RuleSet
from app.domain.tiles import Tile


def test_red_five_round_trip():
    tile = Tile.parse("0m")
    assert (tile.suit, tile.rank, tile.red, tile.source_text) == ("m", 5, True, "0m")


def test_three_player_rule_removes_middle_manzu_and_enables_kita():
    rules = RuleSet.standard_three_player()
    assert rules.player_count == 3
    assert rules.kita_enabled is True
    assert all(f"{rank}m" not in rules.tile_codes for rank in range(2, 9))
```

- [ ] **Step 2: Run tests and verify missing-domain failure**

Run: `python -m pytest backend/tests/domain -v`

Expected: FAIL because domain modules do not exist.

- [ ] **Step 3: Implement immutable tile and rule models**

```python
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
        rank_text, suit = source_text[0], source_text[1]
        red = rank_text == "0"
        rank = 5 if red else int(rank_text)
        if suit not in "mpsz" or rank < 1 or rank > (7 if suit == "z" else 9):
            raise ValueError(f"invalid tile: {source_text}")
        return cls(suit=suit, rank=rank, red=red, source_text=source_text)
```

```python
from typing import Literal
from pydantic import BaseModel


class RuleSet(BaseModel):
    player_count: Literal[3, 4]
    game_length: Literal["east", "south"] = "south"
    initial_score: int
    red_fives: dict[str, int]
    open_tanyao: bool = True
    tsumo_loss: bool | None = None
    kita_enabled: bool = False
    tile_codes: tuple[str, ...]

    @classmethod
    def standard_four_player(cls) -> "RuleSet":
        codes = tuple(f"{r}{s}" for s in "mps" for r in range(1, 10)) + tuple(f"{r}z" for r in range(1, 8))
        return cls(player_count=4, initial_score=25000, red_fives={"m": 1, "p": 1, "s": 1}, tile_codes=codes)

    @classmethod
    def standard_three_player(cls) -> "RuleSet":
        codes = ("1m", "9m") + tuple(f"{r}{s}" for s in "ps" for r in range(1, 10)) + tuple(f"{r}z" for r in range(1, 8))
        return cls(player_count=3, initial_score=35000, red_fives={"m": 0, "p": 1, "s": 1}, tsumo_loss=False, kita_enabled=True, tile_codes=codes)
```

- [ ] **Step 4: Add event and game validation tests**

```python
import pytest
from app.domain.events import CallEvent, CallKind, WinEvent
from app.domain.game import CanonicalGame, Player
from app.domain.rules import RuleSet


def test_kita_is_valid_only_when_rules_enable_it():
    event = CallEvent(sequence=3, actor=1, kind=CallKind.KITA, tile="4z", consumed_tiles=[])
    game = CanonicalGame(external_id="g", rules=RuleSet.standard_three_player(), players=[Player(seat=i, name=str(i)) for i in range(3)], rounds=[], final_scores=[35000] * 3, final_ranks=[1, 2, 3])
    game.validate_event(event)


def test_win_event_supports_multiple_winners():
    event = WinEvent(sequence=20, winners=[1, 2], loser=0, score_delta=[-12000, 8000, 4000, 0])
    assert event.winners == [1, 2]
```

- [ ] **Step 5: Implement the discriminated event union and game validation**

```python
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


class CallKind(StrEnum):
    CHI = "chi"
    PON = "pon"
    DAIMINKAN = "daiminkan"
    ANKAN = "ankan"
    KAKAN = "kakan"
    KITA = "kita"


class CallEvent(BaseModel):
    event_type: Literal["call"] = "call"
    sequence: int
    actor: int
    kind: CallKind
    tile: str
    consumed_tiles: list[str]


class WinEvent(BaseModel):
    event_type: Literal["win"] = "win"
    sequence: int
    winners: list[int]
    loser: int | None
    score_delta: list[int]
```

Implement the other event classes with the same stable fields: `RoundStarted`, `TileDrawn`, `TileDiscarded`, `RiichiDeclared`, `RiichiAccepted`, `DoraRevealed`, `ExhaustiveDraw`, `AbortiveDraw`, `ScoreChanged`, and `RoundEnded`.

- [ ] **Step 6: Run all domain tests**

Run: `python -m pytest backend/tests/domain -v`

Expected: all domain tests PASS.

- [ ] **Step 7: Commit canonical domain models**

```bash
git add backend/app/domain backend/tests/domain
git commit -m "feat: define canonical riichi game model"
```

### Task 4: Add SQLite persistence and content-addressed replay storage

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/replay.py`
- Create: `backend/app/models/game.py`
- Create: `backend/app/models/analysis.py`
- Create: `backend/app/repositories/replay_repository.py`
- Create: `backend/app/repositories/analysis_repository.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/tests/repositories/test_replay_repository.py`

**Interfaces:**
- Produces: `ReplayRepository.put_raw_replay(raw: RawReplay) -> UUID`
- Produces: `ReplayRepository.get_by_sha256(sha256: str) -> RawReplayRecord | None`
- Produces: analysis cache key `(game_id, algorithm_id, algorithm_version, options_hash)`.

- [ ] **Step 1: Write a failing deduplication test**

```python
async def test_raw_replays_are_deduplicated_by_sha256(replay_repository):
    first = await replay_repository.put_bytes(source="local", external_id="a", payload=b"same")
    second = await replay_repository.put_bytes(source="local", external_id="b", payload=b"same")
    assert first == second
```

- [ ] **Step 2: Run the repository test and verify failure**

Run: `python -m pytest backend/tests/repositories/test_replay_repository.py -v`

Expected: FAIL because database and repository classes do not exist.

- [ ] **Step 3: Implement async SQLite session creation**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 4: Implement replay hashing and idempotent insertion**

```python
import hashlib
from uuid import UUID
from sqlalchemy import select


class ReplayRepository:
    def __init__(self, session):
        self.session = session

    async def put_bytes(self, source: str, external_id: str, payload: bytes) -> UUID:
        digest = hashlib.sha256(payload).hexdigest()
        existing = await self.session.scalar(select(RawReplayModel).where(RawReplayModel.sha256 == digest))
        if existing:
            return existing.id
        model = RawReplayModel(source=source, external_id=external_id, payload=payload, sha256=digest)
        self.session.add(model)
        await self.session.commit()
        return model.id
```

- [ ] **Step 5: Create and apply the initial migration**

Run: `python -m alembic -c backend/alembic.ini upgrade head`

Expected: SQLite contains tables for raw replays, canonical games, players, rounds, events, analyses, player analyses, round analyses, and event analyses.

- [ ] **Step 6: Run persistence tests**

Run: `python -m pytest backend/tests/repositories -v`

Expected: repository tests PASS.

- [ ] **Step 7: Commit persistence**

```bash
git add backend/app/db.py backend/app/models backend/app/repositories backend/alembic* backend/tests/repositories
git commit -m "feat: persist raw replays games and analyses"
```

### Task 5: Implement source capabilities and Amae-Koromo search/list access

**Files:**
- Create: `backend/app/sources/base.py`
- Create: `backend/app/sources/registry.py`
- Create: `backend/app/sources/amae_koromo.py`
- Create: `backend/app/api/sources.py`
- Create: `backend/tests/sources/test_amae_koromo.py`
- Create: `backend/tests/api/test_sources_api.py`

**Interfaces:**
- Produces: `ReplaySource.search_players(query, mode) -> list[RemotePlayer]`
- Produces: `ReplaySource.list_games(player, cursor, limit) -> GamePage`
- Produces: `GET /api/players/search` and `GET /api/players/{source}/{player_id}/games`.

- [ ] **Step 1: Write failing source contract tests**

```python
@pytest.mark.asyncio
async def test_searches_four_player_koromo_api(respx_mock):
    route = respx_mock.get("https://5-data.amae-koromo.com/api/v2/pl4/search_player/A?limit=20&tag=all").mock(
        return_value=httpx.Response(200, json=[{"id": 7, "nickname": "A", "level": {"id": 10401}, "latest_timestamp": 1700000000}])
    )
    players = await AmaeKoromoSource(httpx.AsyncClient()).search_players("A", GameMode.FOUR_PLAYER)
    assert route.called
    assert players[0].external_id == "7"
```

- [ ] **Step 2: Run source tests and verify failure**

Run: `python -m pytest backend/tests/sources/test_amae_koromo.py -v`

Expected: FAIL because source interfaces and Amae-Koromo client do not exist.

- [ ] **Step 3: Define source capabilities and stable DTOs**

```python
from enum import StrEnum
from typing import Protocol
from pydantic import BaseModel


class GameMode(StrEnum):
    FOUR_PLAYER = "4p"
    THREE_PLAYER = "3p"


class SourceCapability(StrEnum):
    SEARCH_PLAYERS = "search_players"
    LIST_PLAYER_GAMES = "list_player_games"
    FETCH_BY_ID = "fetch_by_id"
    IMPORT_FILE = "import_file"


class RemotePlayer(BaseModel):
    source: str
    external_id: str
    nickname: str
    mode: GameMode
    level_id: int | None
    latest_timestamp: int | None
```

- [ ] **Step 4: Implement mirrored API requests with bounded retry**

```python
MIRRORS = (
    "https://5-data.amae-koromo.com/",
    "https://1.data.amae-koromo.com/",
    "https://2.data.amae-koromo.com/",
    "https://4.data.amae-koromo.com/",
)

MODE_PATH = {GameMode.FOUR_PLAYER: "api/v2/pl4/", GameMode.THREE_PLAYER: "api/v2/pl3/"}


async def _get_json(self, path: str):
    last_error = None
    for mirror in MIRRORS:
        try:
            response = await self.client.get(mirror + path, timeout=5.0)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            last_error = exc
    raise SourceUnavailable("AMAE_KOROMO_UNAVAILABLE") from last_error
```

- [ ] **Step 5: Implement player records pagination**

Use mode IDs exactly as exposed by Amae-Koromo:

```python
MODE_IDS = {
    GameMode.FOUR_PLAYER: (16, 12, 9, 15, 11, 8),
    GameMode.THREE_PLAYER: (26, 24, 22, 25, 23, 21),
}
```

Map each result into a metadata-only `RemoteGame` containing `_id`, `modeId`, `uuid`, timestamps, players, scores, and grading scores.

- [ ] **Step 6: Add API route tests and implementation**

```python
def test_player_search_requires_mode(client):
    response = client.get("/api/players/search", params={"source": "amae-koromo", "q": "A"})
    assert response.status_code == 422
```

Implement query parameters `source`, `q`, `mode`, `limit`, and `cursor`. Return stable application DTOs rather than forwarding third-party JSON.

- [ ] **Step 7: Run source and API tests**

Run: `python -m pytest backend/tests/sources backend/tests/api/test_sources_api.py -v`

Expected: all tests PASS with no live network dependency.

- [ ] **Step 8: Commit Amae-Koromo integration**

```bash
git add backend/app/sources backend/app/api/sources.py backend/tests/sources backend/tests/api/test_sources_api.py
git commit -m "feat: search Amae-Koromo players and games"
```

### Task 6: Parse Mahjong Soul locators and implement credential-free import behavior

**Files:**
- Create: `backend/app/errors.py`
- Create: `backend/app/sources/local_file.py`
- Create: `backend/app/sources/majsoul/locator.py`
- Create: `backend/app/sources/majsoul/fetcher.py`
- Create: `backend/app/services/import_service.py`
- Create: `backend/app/api/replays.py`
- Create: `backend/tests/sources/majsoul/test_locator.py`
- Create: `backend/tests/services/test_import_service.py`

**Interfaces:**
- Produces: `MajsoulLocator.parse(value: str) -> MajsoulLocator`
- Produces: `ImportService.import_file(...) -> UUID`
- Produces: `ImportService.import_remote(...) -> UUID`
- Produces typed error code `REPLAY_FETCH_UNAVAILABLE` without requesting credentials.

- [ ] **Step 1: Write failing share-link parsing tests**

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("260307-76323960-cf3c-494e-be24-26dd6ba81c98", "260307-76323960-cf3c-494e-be24-26dd6ba81c98"),
        ("https://game.maj-soul.com/1/?paipu=260307-76323960-cf3c-494e-be24-26dd6ba81c98_a21590812", "260307-76323960-cf3c-494e-be24-26dd6ba81c98"),
    ],
)
def test_parse_majsoul_locator(value, expected):
    assert MajsoulLocator.parse(value).record_id == expected
```

- [ ] **Step 2: Run locator tests and verify failure**

Run: `python -m pytest backend/tests/sources/majsoul/test_locator.py -v`

Expected: FAIL because `MajsoulLocator` does not exist.

- [ ] **Step 3: Implement strict locator normalization**

```python
from urllib.parse import parse_qs, urlparse
from pydantic import BaseModel


class MajsoulLocator(BaseModel):
    original: str
    record_id: str
    account_token: str | None = None

    @classmethod
    def parse(cls, value: str) -> "MajsoulLocator":
        raw = value.strip()
        paipu = parse_qs(urlparse(raw).query).get("paipu", [raw])[0]
        base, *suffixes = paipu.split("_")
        account = next((s[1:] for s in suffixes if s.startswith("a")), None)
        if not base or len(base) > 160:
            raise ValueError("invalid Mahjong Soul replay locator")
        return cls(original=raw, record_id=base, account_token=account)
```

- [ ] **Step 4: Write import size, hash, and unavailable-fetch tests**

```python
async def test_file_import_rejects_more_than_32_mib(import_service):
    with pytest.raises(AppError) as error:
        await import_service.import_file("large.bin", b"x" * (32 * 1024 * 1024 + 1))
    assert error.value.code == "REPLAY_FILE_TOO_LARGE"


async def test_remote_import_does_not_request_credentials(import_service, replay_fetcher):
    replay_fetcher.fetch.side_effect = ReplayFetchUnavailable()
    with pytest.raises(AppError) as error:
        await import_service.import_remote("260307-example")
    assert error.value.code == "REPLAY_FETCH_UNAVAILABLE"
```

- [ ] **Step 5: Implement the credential-free fetcher contract**

```python
class MajsoulReplayFetcher:
    async def fetch(self, locator: MajsoulLocator) -> bytes:
        raise ReplayFetchUnavailable(
            code="REPLAY_FETCH_UNAVAILABLE",
            message="No anonymous raw-replay resolver is available for this record."
        )
```

Keep this explicit fallback until a no-credential resolver passes an integration test. Do not add a login form or hidden service credential.

- [ ] **Step 6: Implement safe file import**

Accept binary protobuf, decoded JSON, and application-generated canonical JSON. Reject executable archives and oversized input before parsing. Store payload bytes by SHA-256 through `ReplayRepository`.

- [ ] **Step 7: Implement replay import endpoints**

```text
POST /api/replays/import-file
POST /api/replays/import-locator
GET  /api/replays/{replay_id}
DELETE /api/replays/{replay_id}
```

Use multipart upload for files and JSON `{ "locator": "..." }` for links/IDs.

- [ ] **Step 8: Run import tests**

Run: `python -m pytest backend/tests/sources/majsoul backend/tests/services/test_import_service.py -v`

Expected: locator and file imports PASS; an unavailable anonymous resolver returns a stable typed error.

- [ ] **Step 9: Commit import boundaries**

```bash
git add backend/app/errors.py backend/app/sources/local_file.py backend/app/sources/majsoul backend/app/services/import_service.py backend/app/api/replays.py backend/tests/sources/majsoul backend/tests/services/test_import_service.py
git commit -m "feat: add safe Mahjong Soul replay imports"
```

### Task 7: Vendor the Mahjong Soul protocol and canonicalize decoded events

**Files:**
- Create: `scripts/update_majsoul_protocol.py`
- Create: `backend/app/sources/majsoul/protocol.py`
- Create: `backend/app/sources/majsoul/protocol/liqi.json`
- Create: `backend/app/sources/majsoul/decoder.py`
- Create: `backend/app/sources/majsoul/canonicalizer.py`
- Create: `backend/tests/fixtures/majsoul/four_player_actions.json`
- Create: `backend/tests/fixtures/majsoul/three_player_kita.json`
- Create: `backend/tests/fixtures/majsoul/four-player-canonical.json`
- Create: `backend/tests/fixtures/majsoul/three-player-canonical.json`
- Create: `backend/tests/sources/majsoul/test_canonicalizer.py`

**Interfaces:**
- Produces: `decode_majsoul(payload: bytes, descriptor: dict) -> DecodedMajsoulGame`
- Produces: `canonicalize_majsoul(decoded: DecodedMajsoulGame) -> CanonicalGame`
- Preserves unknown event names and payloads for diagnostics.

- [ ] **Step 1: Write canonicalization tests from decoded fixtures**

```python
def test_four_player_actions_become_ordered_events(load_fixture):
    game = canonicalize_majsoul(load_fixture("majsoul/four_player_actions.json"))
    assert game.rules.player_count == 4
    assert [event.sequence for event in game.rounds[0].events] == sorted(event.sequence for event in game.rounds[0].events)


def test_three_player_babei_becomes_kita(load_fixture):
    game = canonicalize_majsoul(load_fixture("majsoul/three_player_kita.json"))
    calls = [event for event in game.rounds[0].events if event.event_type == "call"]
    assert any(event.kind == "kita" for event in calls)
```

- [ ] **Step 2: Run canonicalizer tests and verify failure**

Run: `python -m pytest backend/tests/sources/majsoul/test_canonicalizer.py -v`

Expected: FAIL because the decoder and canonicalizer do not exist.

- [ ] **Step 3: Add deterministic protocol-resource discovery**

```python
VERSION_URL = "https://game.maj-soul.com/1/version.json"


def descriptor_url(version: str, resversion: dict) -> str:
    entry = resversion["res/proto/liqi.json"]
    prefix = entry["prefix"]
    return f"https://game.maj-soul.com/1/{prefix}/res/proto/liqi.json"
```

The update script downloads `version.json`, the matching `resversion{version}.json`, and the descriptor, then writes the descriptor plus a SHA-256 metadata file. Normal application startup uses the vendored descriptor and does not require network access.

- [ ] **Step 4: Implement new and old replay containers**

Decode outer `Wrapper`, then `GameDetailRecords`. Read both legacy `records[]` and current `actions[].result`; each child is another typed wrapper. If an event is not recognized, create an `UnknownEvent` containing `raw_type` and decoded `raw_payload`.

- [ ] **Step 5: Map all standard event types**

```python
EVENT_MAP = {
    ".lq.RecordNewRound": "round_started",
    ".lq.RecordDealTile": "tile_drawn",
    ".lq.RecordDiscardTile": "tile_discarded",
    ".lq.RecordChiPengGang": "call",
    ".lq.RecordAnGangAddGang": "call",
    ".lq.RecordBaBei": "kita",
    ".lq.RecordHule": "win",
    ".lq.RecordNoTile": "exhaustive_draw",
    ".lq.RecordLiuJu": "abortive_draw",
}
```

Infer player count from accounts and score arrays, preserve the rules object, keep multiple winners, and trust replay `delta_scores` as the settlement fact.

- [ ] **Step 6: Run Mahjong Soul decoding and canonicalization tests**

Run: `python -m pytest backend/tests/sources/majsoul -v`

Expected: four-player, three-player kita, multi-winner, and unknown-event tests PASS.

- [ ] **Step 7: Commit protocol and canonicalizer**

```bash
git add scripts/update_majsoul_protocol.py backend/app/sources/majsoul backend/tests/fixtures/majsoul backend/tests/sources/majsoul
git commit -m "feat: decode and normalize Mahjong Soul replays"
```

### Task 8: Implement the `baseline-v1` opportunity-quality algorithm

**Files:**
- Create: `backend/app/domain/analysis.py`
- Create: `backend/app/algorithms/base.py`
- Create: `backend/app/algorithms/registry.py`
- Create: `backend/app/algorithms/baseline_v1/hand_value.py`
- Create: `backend/app/algorithms/baseline_v1/opportunity.py`
- Create: `backend/app/algorithms/baseline_v1/calibration.py`
- Create: `backend/app/algorithms/baseline_v1/calibration.json`
- Create: `backend/app/algorithms/baseline_v1/algorithm.py`
- Create: `backend/tests/algorithms/test_hand_value.py`
- Create: `backend/tests/algorithms/test_baseline_v1.py`

**Interfaces:**
- Produces: `LuckAlgorithm.analyze(game, options) -> GameLuckAnalysis`
- Produces: registered algorithm ID `baseline-v1`, version `1.0.0`.
- Produces per-player, per-round, and per-event raw deltas, variances, z-scores, 0–100 scores, and confidence labels.

- [ ] **Step 1: Write failing hand-value tests**

```python
def test_lower_shanten_is_more_valuable():
    one_shanten = HandState.from_codes(["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "1z", "1z"])
    two_shanten = HandState.from_codes(["1m", "3m", "5m", "1p", "3p", "5p", "1s", "3s", "5s", "1z", "2z", "3z", "4z"])
    assert hand_value(one_shanten, RuleSet.standard_four_player()) > hand_value(two_shanten, RuleSet.standard_four_player())


def test_red_five_changes_visible_value_once():
    normal = HandState.from_codes(["5p", "1m", "2m", "3m", "4m", "5m", "6m", "2s", "3s", "4s", "7s", "8s", "9s"])
    red = HandState.from_codes(["0p", "1m", "2m", "3m", "4m", "5m", "6m", "2s", "3s", "4s", "7s", "8s", "9s"])
    assert hand_value(red, RuleSet.standard_four_player()) > hand_value(normal, RuleSet.standard_four_player())
```

- [ ] **Step 2: Run algorithm tests and verify failure**

Run: `python -m pytest backend/tests/algorithms -v`

Expected: FAIL because algorithm modules do not exist.

- [ ] **Step 3: Define the algorithm contract and analysis DTOs**

```python
from abc import ABC, abstractmethod


class LuckAlgorithm(ABC):
    id: str
    version: str
    name_key: str
    description_key: str

    @abstractmethod
    def supports(self, rules: RuleSet) -> bool: ...

    @abstractmethod
    def analyze(self, game: CanonicalGame, options: AnalysisOptions) -> GameLuckAnalysis: ...
```

Use stable components `initial_hand`, `self_draw`, `dora_reveal`, `special_random`, and informational `opponent_gift`.

- [ ] **Step 4: Implement deterministic hand value**

```python
WEIGHTS = {
    "shanten": 0.45,
    "ukeire": 0.25,
    "shape": 0.10,
    "visible_value": 0.15,
    "yaku_potential": 0.05,
}
```

Use `mahjong.shanten.Shanten` for regular, chiitoitsu, and kokushi shanten. Count only legal remaining tiles for the current rule set. Evaluate a draw by selecting the highest-valued legal discard after the draw, not the player's actual discard.

- [ ] **Step 5: Implement weighted candidate-draw expectation**

```python
def draw_opportunity(state: PublicPlayerState, actual_tile: Tile) -> OpportunityResult:
    outcomes = []
    for tile, count in state.remaining_tile_counts.items():
        if count:
            outcomes.append((count, best_post_draw_value(state, tile)))
    total = sum(count for count, _ in outcomes)
    expected = sum(count * value for count, value in outcomes) / total
    variance = sum(count * (value - expected) ** 2 for count, value in outcomes) / total
    actual = best_post_draw_value(state, actual_tile)
    return OpportunityResult(actual=actual, expected=expected, delta=actual - expected, variance=variance)
```

- [ ] **Step 6: Implement non-duplicating dora and special-event scoring**

Initial and drawn red/normal dora remain inside hand value. Score only the incremental effect of newly revealed kan/ura indicators against the weighted set of possible indicators. Record opponent discards as `opponent_gift` information and exclude them from the main luck z-score.

- [ ] **Step 7: Generate deterministic calibration tables**

Generate 50,000 starting hands for each combination of player count and dealer flag using seed `20260713`. Save mean and standard deviation of starting-hand values in `calibration.json`. The generation script must produce byte-identical JSON when rerun with the same dependency versions.

Run: `python -m app.algorithms.baseline_v1.calibration --seed 20260713 --samples 50000`

Expected: `calibration.json` contains four named distributions: `4p-dealer`, `4p-nondealer`, `3p-dealer`, `3p-nondealer`.

- [ ] **Step 8: Map accumulated z-score to 0–100**

```python
def score_from_z(z: float) -> float:
    return max(0.0, min(100.0, 50.0 + 15.0 * z))
```

Aggregate raw deltas and variances before converting to a score. Do not average round scores.

- [ ] **Step 9: Add invariance and double-counting tests**

Test that fixed strategies over repeated seeded shuffles average near score 50, red dora is counted once, a player decision does not alter the already-recorded draw delta, three-player removed tiles have zero draw probability, and identical inputs return identical JSON.

- [ ] **Step 10: Run algorithm tests**

Run: `python -m pytest backend/tests/algorithms -v`

Expected: all baseline algorithm tests PASS.

- [ ] **Step 11: Commit the first algorithm**

```bash
git add backend/app/domain/analysis.py backend/app/algorithms backend/tests/algorithms
git commit -m "feat: calculate baseline opportunity luck scores"
```

### Task 9: Add import, analysis, cache, and API orchestration

**Files:**
- Create: `backend/app/services/analysis_service.py`
- Create: `backend/app/api/analyses.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/services/test_analysis_service.py`
- Create: `backend/tests/api/test_analyses_api.py`

**Interfaces:**
- Produces: `AnalysisService.analyze(game_id, algorithm_id, options) -> GameLuckAnalysis`
- Produces: `GET /api/algorithms`, `POST /api/analyses`, and `GET /api/analyses/{id}`.

- [ ] **Step 1: Write a failing cache-key test**

```python
async def test_analysis_is_reused_for_same_game_algorithm_version_and_options(analysis_service, algorithm):
    first = await analysis_service.analyze(GAME_ID, algorithm.id, {"event_details": True})
    second = await analysis_service.analyze(GAME_ID, algorithm.id, {"event_details": True})
    assert first.id == second.id
    assert algorithm.analyze.call_count == 1
```

- [ ] **Step 2: Run service tests and verify failure**

Run: `python -m pytest backend/tests/services/test_analysis_service.py -v`

Expected: FAIL because analysis orchestration does not exist.

- [ ] **Step 3: Implement parsing and analysis state transitions**

Use states `pending`, `parsing`, `analyzing`, `completed`, and `failed`. Persist `error_code` and safe error parameters; never persist a full external response containing account tokens.

- [ ] **Step 4: Implement the analysis cache key**

```python
options_hash = hashlib.sha256(
    json.dumps(options, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
```

Key by canonical game hash, algorithm ID, algorithm version, and options hash.

- [ ] **Step 5: Implement API schemas and routes**

```json
{
  "gameId": "7c09190d-2b74-4bc1-aebe-cb342363587f",
  "algorithmId": "baseline-v1",
  "options": {"eventDetails": true}
}
```

Return a stable result containing players, round summaries, event details, actual score changes, confidence, algorithm metadata, and explanatory component keys.

- [ ] **Step 6: Run API and service tests**

Run: `python -m pytest backend/tests/services backend/tests/api/test_analyses_api.py -v`

Expected: cache, unsupported mode, unknown algorithm, and successful analysis tests PASS.

- [ ] **Step 7: Commit orchestration APIs**

```bash
git add backend/app/services/analysis_service.py backend/app/api/analyses.py backend/app/main.py backend/tests/services backend/tests/api/test_analyses_api.py
git commit -m "feat: expose cached replay analyses over API"
```

### Task 10: Build player search, recent games, and import GUI

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/home-page.tsx`
- Create: `frontend/src/pages/player-page.tsx`
- Create: `frontend/src/components/player-search.tsx`
- Create: `frontend/src/components/game-table.tsx`
- Create: `frontend/src/components/replay-import.tsx`
- Create: `frontend/src/locales/zh-CN/search.json`
- Create: `frontend/src/locales/en/search.json`
- Create: `frontend/src/test/player-search.test.tsx`

**Interfaces:**
- Consumes: source search/list and replay import APIs from Tasks 5 and 6.
- Produces: responsive workflows for username search, mode selection, game listing, locator import, and file upload.

- [ ] **Step 1: Write a failing player-search interaction test**

```tsx
it("searches four-player users and renders the result", async () => {
  server.use(http.get("/api/players/search", () => HttpResponse.json([{ source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p" }])));
  render(<PlayerSearch />);
  await userEvent.type(screen.getByRole("textbox", { name: "playerSearch.name" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "playerSearch.submit" }));
  expect(await screen.findByText("A")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run: `npm --prefix frontend test`

Expected: FAIL because search components do not exist.

- [ ] **Step 3: Implement typed API calls**

```ts
export async function searchPlayers(query: string, mode: "4p" | "3p") {
  const params = new URLSearchParams({ source: "amae-koromo", q: query, mode });
  const response = await fetch(`/api/players/search?${params}`);
  if (!response.ok) throw await ApiError.fromResponse(response);
  return (await response.json()) as RemotePlayer[];
}
```

- [ ] **Step 4: Implement search and recent-game flows**

Use a mode toggle, debounced input, explicit submit, loading state, empty state, source coverage notice, cursor pagination, and local analysis status. Keep player seat colors consistent within each game row.

- [ ] **Step 5: Implement link/ID and file import**

Limit file selection to one 32 MiB file. Render `REPLAY_FETCH_UNAVAILABLE` as a bilingual explanation that anonymous metadata remains available and the user can import a replay file; do not render a login form.

- [ ] **Step 6: Add complete Chinese and English resources**

Include search fields, four/three-player labels, source coverage, table headers, import states, errors, retry, and delete confirmation. Add a test that recursively compares the translation-key trees of `zh-CN` and `en`.

- [ ] **Step 7: Run frontend tests and build**

Run: `npm --prefix frontend test && npm --prefix frontend run build`

Expected: search/import tests PASS and production build succeeds.

- [ ] **Step 8: Commit search and import GUI**

```bash
git add frontend/src/api frontend/src/pages frontend/src/components frontend/src/locales frontend/src/test
git commit -m "feat: add player search games and replay import UI"
```

### Task 11: Build game, round, and event analysis visualizations

**Files:**
- Create: `frontend/src/pages/game-analysis-page.tsx`
- Create: `frontend/src/components/player-luck-comparison.tsx`
- Create: `frontend/src/components/round-luck-chart.tsx`
- Create: `frontend/src/components/component-breakdown.tsx`
- Create: `frontend/src/components/event-timeline.tsx`
- Create: `frontend/src/components/tile.tsx`
- Create: `frontend/src/locales/zh-CN/analysis.json`
- Create: `frontend/src/locales/en/analysis.json`
- Create: `frontend/src/test/game-analysis.test.tsx`

**Interfaces:**
- Consumes: `GameLuckAnalysis` from Task 9.
- Produces: overall player comparison, per-round trend, component breakdown, and detailed event explanations.

- [ ] **Step 1: Write a failing analysis-page test**

```tsx
it("shows luck score separately from actual score change", async () => {
  render(<GameAnalysisPage analysis={fixtureAnalysis} />);
  expect(screen.getByText("72")).toBeInTheDocument();
  expect(screen.getByText("+31,200")).toBeInTheDocument();
  expect(screen.getByText("analysis.resultIsNotLuck")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test and verify failure**

Run: `npm --prefix frontend test -- game-analysis.test.tsx`

Expected: FAIL because analysis components do not exist.

- [ ] **Step 3: Implement accessible tile rendering**

Render tile code, red status, and localized accessible name. Color is not the only red-five indicator. The component must support compact timeline and large starting-hand sizes.

- [ ] **Step 4: Implement player comparison and round charts**

Use teal for positive deviation, orange-red for negative deviation, and blue-gray for neutral. Chart tooltips display score, z-score, raw delta, confidence, and actual points. Player colors remain stable across every chart.

- [ ] **Step 5: Implement the event timeline**

Each row displays sequence, localized event, tile, EV before/after, expected value, random delta, local standard deviation, component, and explanation features such as shanten and ukeire. `opponent_gift` is visually distinct and excluded from the main luck total.

- [ ] **Step 6: Add algorithm selection and reanalysis**

Load `GET /api/algorithms`, show name/description/version/support, submit the chosen ID, and display a warning when an existing result uses an older version.

- [ ] **Step 7: Run visualization tests and build**

Run: `npm --prefix frontend test && npm --prefix frontend run build`

Expected: analysis tests PASS and build succeeds without missing locale keys.

- [ ] **Step 8: Commit analysis GUI**

```bash
git add frontend/src/pages/game-analysis-page.tsx frontend/src/components frontend/src/locales frontend/src/test/game-analysis.test.tsx
git commit -m "feat: visualize game and round luck analysis"
```

### Task 12: Add local launch scripts, end-to-end tests, and user documentation

**Files:**
- Create: `scripts/dev.sh`
- Create: `scripts/start.sh`
- Create: `flake.nix`
- Create: `flake.lock`
- Modify: `backend/app/main.py`
- Create: `frontend/tests/e2e/search-and-analyze.spec.ts`
- Create: `backend/tests/api/test_security.py`
- Create: `README.md`

**Interfaces:**
- Produces: `scripts/start.sh` plus `nix run .#start`, with optional browser opening and headless-safe startup.
- Produces: a complete offline fixture path for deterministic E2E analysis.

- [ ] **Step 1: Write security tests**

```python
def test_remote_import_rejects_private_network_url(client):
    response = client.post("/api/replays/import-locator", json={"locator": "http://127.0.0.1/private"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REPLAY_LOCATOR"


def test_cors_does_not_allow_arbitrary_origins(client):
    response = client.options("/api/health", headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
    assert response.headers.get("access-control-allow-origin") is None
```

- [ ] **Step 2: Write an E2E fixture workflow**

```ts
test("imports a local three-player fixture and displays all players", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("replayImport.file").setInputFiles("backend/tests/fixtures/majsoul/three-player-canonical.json");
  await page.getByRole("button", { name: "replayImport.analyze" }).click();
  await expect(page.getByTestId("player-luck-score")).toHaveCount(3);
  await expect(page.getByText("baseline-v1")).toBeVisible();
});
```

- [ ] **Step 3: Implement development and production launch scripts**

```bash
#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export HAIUN_DATA_DIR="${HAIUN_DATA_DIR:-$root/data}"
exec "$root/.venv/bin/python" -m uvicorn app.main:app --host "${HAIUN_HOST:-0.0.0.0}" --port "${HAIUN_PORT:-8765}"
```

Production startup must serve `frontend/dist` from FastAPI and create the local data directory before opening the browser.

- [ ] **Step 4: Document setup, limitations, and data deletion**

README sections:

```text
Requirements
Development setup
Local production start
Chinese/English language switching
Amae-Koromo coverage and availability
Replay import formats
Why Mahjong Soul credentials are never requested
Meaning of the 0–100 luck score
Three-player rule support
Deleting all local data
Running tests
```

- [ ] **Step 5: Run the complete verification suite**

Run:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
bash -n scripts/dev.sh scripts/start.sh
shellcheck scripts/dev.sh scripts/start.sh
```

Expected: backend, frontend, build, and E2E suites all PASS.

- [ ] **Step 6: Manually verify the local production build**

Run: `nix run .#start` or `scripts/start.sh`

Expected: the browser opens `http://127.0.0.1:8765` when a graphical session is available; headless startup succeeds, Chinese is the initial language, English switching works, an offline four-player fixture shows four scores, and an offline three-player fixture shows three scores including kita events.

- [ ] **Step 7: Commit launch and documentation**

```bash
git add scripts backend/app/main.py backend/tests/api/test_security.py frontend/tests/e2e README.md
git commit -m "docs: finish local launch and verification workflow"
```

---

## Final Acceptance Checklist

- [ ] The application starts with one Bash/Nix command, defaults to `0.0.0.0`, and supports `HAIUN_HOST=127.0.0.1` for loopback-only operation.
- [ ] Chinese and English resource trees contain identical keys, and both workflows pass E2E tests.
- [ ] Amae-Koromo four-player and three-player user search and recent-game listing work through mocked contract tests and an optional live smoke test.
- [ ] Local replay import accepts supported protobuf/decoded/canonical data and rejects oversized or invalid input.
- [ ] No application path requests Mahjong Soul credentials.
- [ ] Standard four-player and three-player events normalize into one canonical model, including kita and multiple winners.
- [ ] Unknown modes and events produce explicit diagnostics rather than silent miscalculation.
- [ ] `baseline-v1` reports per-event, per-round, and per-game opportunity luck for every player.
- [ ] Result points and luck score are displayed separately.
- [ ] Algorithm caching includes replay hash, algorithm ID, version, and options.
- [ ] Raw replay bytes, canonical facts, and derived analysis can be deleted locally.
- [ ] All backend, frontend, build, and E2E verification commands pass.

## Upstream Constraint Gate

Anonymous Amae-Koromo search/list access is part of the MVP. Anonymous acquisition of full Mahjong Soul event bytes is accepted only after a credential-free resolver returns raw data in an integration test. Until that condition is met, the application must keep the metadata workflow usable, expose `REPLAY_FETCH_UNAVAILABLE`, and support direct file/decoded replay imports. It must not weaken the no-login requirement by adding hidden credentials or asking the user to sign in.
