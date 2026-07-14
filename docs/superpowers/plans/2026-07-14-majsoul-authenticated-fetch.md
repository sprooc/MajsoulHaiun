# Authenticated Mahjong Soul Replay Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a Mahjong Soul replay link through ordered backend-only account credentials, cache it by Mahjong Soul record ID, canonicalize it, and run the existing luck analysis.

**Architecture:** Add a TOML configuration loader with secret-safe account models, a Mahjong Soul RPC client that uses `ms-api` directly for generated protobuf/RPC types, and an ordered-account fetcher that returns a wrapped raw `ResGameRecord`. Move replay identity caching into the repository/import service so cache hits occur before configuration loading or network access, while the existing decoder and canonicalizer remain the only replay-to-domain conversion path.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy async, httpx, `ms-api`, protobuf, pytest/pytest-asyncio, React/i18next.

## Global Constraints

- Do not depend on any file under `majsoul-paipu-fetcher/` at runtime or test time.
- Do not import `tensoul` only for its exception types; this implementation uses Haiun-owned exceptions and `ms-api` RPC/protobuf primitives directly.
- Credentials exist only in the Git-ignored operator TOML and process memory; never expose them through API schemas, logs, database rows, exception strings, or object representations.
- Try configured accounts in TOML order; continue only for account-specific login rejection or replay error `1203`.
- A cache hit for `(source="majsoul", external_id=<record UUID>)` must occur before credential loading and network access.
- Preserve three-player rules, including excluded 2–8 manzu tiles and kita support.
- Opponents' voluntary discards may remain `opponent_gift` details but must not affect the main luck score.
- Keep the recursive `zh-CN` and `en` translation key trees identical.
- Preserve unrelated changes in `AGENTS.md`, `flake.nix`, the temporary reference directory, and other user-owned files.

---

### Task 1: Secret-safe Mahjong Soul TOML configuration

**Files:**
- Create: `backend/app/sources/majsoul/fetch_config.py`
- Create: `backend/tests/sources/majsoul/test_fetch_config.py`
- Modify: `backend/app/config.py`

**Interfaces:**
- Produces: `MajsoulAccount`, `MajsoulFetchConfig`, `MajsoulConfigError`, and `load_majsoul_fetch_config(path: Path) -> MajsoulFetchConfig`.
- Produces: `Settings.majsoul_config_path: Path`, defaulting to `<repository>/config/majsoul.toml` and overridable by `HAIUN_MAJSOUL_CONFIG`.

- [ ] **Step 1: Write failing configuration tests**

```python
from pathlib import Path

import pytest

from app.config import Settings
from app.sources.majsoul.fetch_config import MajsoulConfigError, load_majsoul_fetch_config


def test_loads_ordered_accounts_and_defaults_host(tmp_path: Path):
    path = tmp_path / "majsoul.toml"
    path.write_text(
        'timeout_seconds = 12\n'
        '[[accounts]]\nusername = "first"\npassword = "secret-one"\n'
        '[[accounts]]\nusername = "second"\npassword = "secret-two"\n'
        'host = "https://game.maj-soul.com"\n',
        encoding="utf-8",
    )
    config = load_majsoul_fetch_config(path)
    assert config.timeout_seconds == 12
    assert [account.username for account in config.accounts] == ["first", "second"]
    assert all(account.host == "https://game.maj-soul.com" for account in config.accounts)
    assert "secret-one" not in repr(config)


@pytest.mark.parametrize("text", ["", "timeout_seconds = 0", "[[accounts]]\nusername='x'"])
def test_rejects_missing_or_invalid_accounts(tmp_path: Path, text: str):
    path = tmp_path / "majsoul.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(MajsoulConfigError):
        load_majsoul_fetch_config(path)


def test_settings_accepts_majsoul_config_environment_path(tmp_path: Path, monkeypatch):
    path = tmp_path / "accounts.toml"
    monkeypatch.setenv("HAIUN_MAJSOUL_CONFIG", str(path))
    assert Settings().majsoul_config_path == path
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetch_config.py -v`

Expected: collection fails because `app.sources.majsoul.fetch_config` does not exist.

- [ ] **Step 3: Implement the TOML loader and settings path**

Implement frozen Pydantic models using `SecretStr` for passwords, an HTTPS-host validator limited to the existing Mahjong Soul allowlist, `timeout_seconds` constrained to `(0, 120]`, and `tomllib.load`. Convert missing files, TOML parse errors, validation errors, empty account lists, blank usernames, and blank passwords into sanitized `MajsoulConfigError` messages that contain only the configuration path and field category.

Add to `Settings`:

```python
majsoul_config_path: Path = REPOSITORY_ROOT / "config" / "majsoul.toml"
```

- [ ] **Step 4: Run the configuration tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetch_config.py backend/tests/api/test_health.py -v`

Expected: all selected tests pass and secret strings are absent from failure output.

### Task 2: Current Mahjong Soul Web RPC client returning raw protobuf

**Files:**
- Create: `backend/app/sources/majsoul/client.py`
- Create: `backend/tests/sources/majsoul/test_client.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `extract_client_version(index_html: str) -> str`.
- Produces: `MajsoulClient.fetch_record(record_id: str, username: str, password: str) -> bytes`.
- Produces local errors: `MajsoulClientError`, `MajsoulLoginRejected`, `MajsoulRecordUnavailable`, `MajsoulGatewayError`, and `MajsoulProtocolError`.

- [ ] **Step 1: Write failing version, route, login, wrapping, timeout, and cleanup tests**

Tests must use fake `httpx.AsyncClient`, channel, and lobby objects. Cover these assertions:

```python
def test_extracts_current_unity_product_version():
    assert extract_client_version('productVersion: "4.0.45"') == "4.0.45"


async def test_fetch_record_returns_wrapped_res_game_record():
    payload = await client.fetch_record(RECORD_ID, "account", "password")
    wrapper = pb.Wrapper.FromString(payload)
    assert wrapper.name == ".lq.ResGameRecord"
    response = pb.ResGameRecord.FromString(wrapper.data)
    assert response.head.uuid == RECORD_ID
    assert fake_channel.closed is True


async def test_login_request_hashes_password_and_never_keeps_plaintext_in_messages():
    await client.fetch_record(RECORD_ID, "account", "plain-secret")
    request = fake_lobby.login_request
    assert request.password == hmac.new(b"lailai", b"plain-secret", hashlib.sha256).hexdigest()
    assert request.password != "plain-secret"
    assert request.client_version_string == "web-4.0.45"


async def test_record_error_1203_is_account_specific():
    with pytest.raises(MajsoulRecordUnavailable):
        await client.fetch_record(RECORD_ID, "account", "password")


async def test_connection_is_closed_when_login_fails():
    with pytest.raises(MajsoulLoginRejected):
        await client.fetch_record(RECORD_ID, "account", "password")
    assert fake_channel.closed is True
```

- [ ] **Step 2: Run client tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_client.py -v`

Expected: collection fails because `app.sources.majsoul.client` does not exist.

- [ ] **Step 3: Add the direct RPC dependency**

Add `"ms-api>=0.11.100,<0.12"` to project dependencies and run `nix develop -c uv lock` so `uv.lock` records `ms-api`, `aiohttp`, `websockets`, and their transitive dependencies. Do not add `tensoul`.

- [ ] **Step 4: Implement the current Web client and raw response wrapper**

Use the reference implementation's two client-version regexes, `/1/version.json` plus `/1/v<version>/config.json`, `/api/clientgate/routes`, and legacy region fallback. Use `httpx.AsyncClient` for HTTP and `ms.base.MSRPCChannel`, `ms.rpc.Lobby`, and `ms.protocol_pb2` for WebSocket RPC/protobuf.

The method sequence is:

```python
async def fetch_record(self, record_id: str, username: str, password: str) -> bytes:
    try:
        await self._connect()
        await self._login(username, password)
        return await self._download(record_id)
    finally:
        await self._close_safely()
```

Wrap each connect/login/download await with `asyncio.wait_for(..., timeout=self.timeout_seconds)`. Inspect protobuf `response.error.code` directly and raise Haiun-owned exceptions. Build the result with:

```python
wrapper = pb.Wrapper(name=".lq.ResGameRecord", data=response.SerializeToString())
return wrapper.SerializeToString()
```

Never log request protobufs, responses, usernames, passwords, access tokens, or configuration model representations.

- [ ] **Step 5: Run client tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_client.py -v`

Expected: all client tests pass.

### Task 3: Ordered multi-account replay fetcher

**Files:**
- Modify: `backend/app/sources/majsoul/fetcher.py`
- Create: `backend/tests/sources/majsoul/test_fetcher.py`

**Interfaces:**
- `MajsoulReplayFetcher(config_path: Path, http_client: httpx.AsyncClient, client_factory: Callable = MajsoulClient)`.
- `fetch(locator: MajsoulLocator) -> bytes` loads configuration lazily and tries accounts in order.
- Public errors: `ReplayFetchConfigurationError`, `ReplayFetchUnavailable`, and `ReplayFetchRemoteError`.

- [ ] **Step 1: Write failing ordered-account tests**

```python
async def test_tries_accounts_in_toml_order_after_login_rejection(fetcher, client_factory):
    client_factory.results = [MajsoulLoginRejected(), b"wrapped-replay"]
    assert await fetcher.fetch(locator) == b"wrapped-replay"
    assert client_factory.usernames == ["first", "second"]


async def test_tries_next_account_after_record_1203(fetcher, client_factory):
    client_factory.results = [MajsoulRecordUnavailable(), b"wrapped-replay"]
    assert await fetcher.fetch(locator) == b"wrapped-replay"


async def test_stops_on_gateway_failure(fetcher, client_factory):
    client_factory.results = [MajsoulGatewayError("gateway unavailable"), b"must-not-run"]
    with pytest.raises(ReplayFetchRemoteError):
        await fetcher.fetch(locator)
    assert client_factory.usernames == ["first"]


async def test_all_accounts_rejected_returns_sanitized_unavailable(fetcher):
    with pytest.raises(ReplayFetchUnavailable) as error:
        await fetcher.fetch(locator)
    assert "first" not in str(error.value)
    assert "second" not in str(error.value)
```

- [ ] **Step 2: Run fetcher tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetcher.py -v`

Expected: tests fail because the stub fetcher has no configuration or account iteration.

- [ ] **Step 3: Implement lazy configuration and error mapping**

Load TOML only inside `fetch`. Construct one client per account using the account host, global timeout, shared backend HTTP client, and injected factory. Continue for `MajsoulLoginRejected` and `MajsoulRecordUnavailable`; map `MajsoulConfigError` to `ReplayFetchConfigurationError`; map all other `MajsoulClientError` instances to `ReplayFetchRemoteError`; after exhausting accounts raise sanitized `ReplayFetchUnavailable`.

- [ ] **Step 4: Run fetcher tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetcher.py -v`

Expected: all ordered-account tests pass.

### Task 4: Replay identity cache and concurrency-safe persistence

**Files:**
- Modify: `backend/app/models/replay.py`
- Modify: `backend/app/repositories/replay_repository.py`
- Modify: `backend/app/services/import_service.py`
- Create: `backend/alembic/versions/0002_cache_raw_replay_identity.py`
- Modify: `backend/tests/repositories/test_replay_repository.py`
- Modify: `backend/tests/services/test_import_service.py`

**Interfaces:**
- Produces: `ReplayRepository.get_by_source_external_id(source: str, external_id: str) -> RawReplayRecord | None`.
- Produces: `ReplayRepository.get_game_id_for_replay(replay_id: UUID, schema_version: str) -> UUID | None`.
- `ImportService.import_remote` checks the source/external cache before invoking the fetcher.

- [ ] **Step 1: Write failing repository identity-cache tests**

```python
async def test_raw_replays_are_deduplicated_by_source_and_external_id(replay_repository):
    first = await replay_repository.put_bytes("majsoul", "record-1", b"first")
    second = await replay_repository.put_bytes("majsoul", "record-1", b"second")
    assert first == second
    stored = await replay_repository.get(first)
    assert stored is not None and stored.payload == b"first"


async def test_can_lookup_raw_replay_by_source_and_external_id(replay_repository):
    replay_id = await replay_repository.put_bytes("majsoul", "record-1", b"payload")
    stored = await replay_repository.get_by_source_external_id("majsoul", "record-1")
    assert stored is not None and stored.id == replay_id
```

- [ ] **Step 2: Write failing import-service cache-before-network test**

```python
async def test_remote_import_returns_cached_replay_without_fetching(import_service, repository, replay_fetcher):
    cached = RawReplayRecord(
        id=uuid4(), source="majsoul", external_id=RECORD_ID,
        payload=b"cached", sha256="digest", filename=None, content_type=None,
    )
    repository.get_by_source_external_id.return_value = cached
    replay_id = await import_service.import_remote(RECORD_ID)
    assert replay_id == cached.id
    replay_fetcher.fetch.assert_not_awaited()
```

- [ ] **Step 3: Run cache tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/repositories/test_replay_repository.py backend/tests/services/test_import_service.py -v`

Expected: failures report missing identity lookup and a fetch occurring on cache hit.

- [ ] **Step 4: Implement model constraint, migration, repository race recovery, and cache-first import**

Add `UniqueConstraint("source", "external_id", name="uq_raw_replays_source_external")` alongside the SHA-256 constraint. The migration must remove pre-existing duplicate source/external rows deterministically by retaining the oldest row before creating the constraint.

In `put_bytes`, query source/external identity first, then SHA-256. On `IntegrityError`, roll back and query both keys again so concurrent inserts return the winner's UUID. In `ImportService.import_remote`, return a cached UUID before calling `fetch`.

- [ ] **Step 5: Run cache tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/repositories/test_replay_repository.py backend/tests/services/test_import_service.py -v`

Expected: all selected tests pass.

### Task 5: API wiring, canonical-game reuse, and sanitized error codes

**Files:**
- Modify: `backend/app/api/replays.py`
- Modify: `backend/app/services/import_service.py`
- Modify: `backend/app/repositories/replay_repository.py`
- Modify: `backend/tests/api/test_replays_api.py`
- Modify: `backend/tests/api/test_security.py`

**Interfaces:**
- `_service` creates `MajsoulReplayFetcher(settings.majsoul_config_path, app.state.http_client)`.
- `_store_canonical_game` returns an existing canonical game ID for replay/schema `1.0.0` without decoding again.
- Import errors map to `REPLAY_FETCH_NOT_CONFIGURED`, `REPLAY_FETCH_UNAVAILABLE`, or `REPLAY_FETCH_FAILED` without credential details.

- [ ] **Step 1: Write failing API cache and canonical reuse tests**

```python
def test_second_locator_import_uses_cached_raw_and_canonical_game(client, monkeypatch):
    calls = 0

    async def fetch_fixture(_self, _locator):
        nonlocal calls
        calls += 1
        return FIXTURE.read_bytes()

    monkeypatch.setattr(MajsoulReplayFetcher, "fetch", fetch_fixture)
    first = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})
    second = client.post("/api/replays/import-locator", json={"locator": RECORD_ID})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1


def test_openapi_and_errors_do_not_expose_credential_fields(client):
    schema = client.get("/openapi.json").text.lower()
    for forbidden in ("password", "oauth_token", "email_code", "browser_session", "access_token"):
        assert forbidden not in schema
```

- [ ] **Step 2: Run API tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_replays_api.py backend/tests/api/test_security.py -v`

Expected: the second import calls the fetcher again and/or constructor wiring lacks the configuration path.

- [ ] **Step 3: Wire settings and reuse canonical rows**

Pass the app's settings path and HTTP client into the fetcher. Before decoding in `_store_canonical_game`, call `get_game_id_for_replay(replay_id, CanonicalGame.model_fields["schema_version"].default)` and return that ID when present. Extend `ImportService` error mapping with sanitized messages and only the public `recordId` parameter.

- [ ] **Step 4: Run API tests and verify GREEN**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_replays_api.py backend/tests/api/test_security.py -v`

Expected: all selected tests pass; repeated import has identical IDs and only one fetch.

### Task 6: Operator files, documentation, bilingual messaging, and live validation

**Files:**
- Create: `config/majsoul.example.toml`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `frontend/src/locales/zh-CN/search.json`
- Modify: `frontend/src/locales/en/search.json`
- Modify: `frontend/src/test/home-page.test.tsx`
- Create: `backend/tests/integration/test_majsoul_live.py`

**Interfaces:**
- Documents the default TOML path, ordered accounts, environment override, cache behavior, and backend-only credential boundary.
- Provides an opt-in live test gated by `HAIUN_RUN_MAJSOUL_LIVE=1` and a real ignored configuration file.

- [ ] **Step 1: Write the skipped-by-default live integration test**

```python
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


RECORD_LINK = "https://game.maj-soul.com/1/?paipu=260714-ec4c890c-abec-4758-9337-2bce7085dbe6_a215808906"


@pytest.mark.skipif(os.getenv("HAIUN_RUN_MAJSOUL_LIVE") != "1", reason="live Mahjong Soul test disabled")
def test_live_import_cache_and_analysis(tmp_path: Path):
    config_path = Path(os.environ["HAIUN_MAJSOUL_CONFIG"])
    settings = Settings(data_dir=tmp_path / "data", majsoul_config_path=config_path)
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/replays/import-locator", json={"locator": RECORD_LINK})
        assert first.status_code == 200, first.text
        imported = first.json()
        assert imported.get("gameId")
        analysis = client.post(
            "/api/analyses",
            json={"gameId": imported["gameId"], "algorithmId": "baseline-v1", "options": {"eventDetails": True}},
        )
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["status"] == "completed"
        second = client.post("/api/replays/import-locator", json={"locator": RECORD_LINK})
        assert second.json() == imported
```

- [ ] **Step 2: Add example config, ignore rule, README instructions, and locale text**

Track only placeholder credentials in `config/majsoul.example.toml`. Add `/config/majsoul.toml` to `.gitignore`. Replace README statements claiming authenticated fetch is unsupported with the approved backend-only TOML behavior. Update both locale files without changing their key trees; replace the old anonymous-fetch wording with messages referring to configured Mahjong Soul accounts.

- [ ] **Step 3: Run all automated checks**

Run:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
bash -n scripts/dev.sh scripts/start.sh
shellcheck scripts/dev.sh scripts/start.sh
```

Expected: backend and frontend suites pass, the live test is skipped by default, frontend build succeeds, and shell checks are clean.

- [ ] **Step 4: Create the ignored live configuration without exposing it**

Create `config/majsoul.toml` locally with mode `0600`, containing the supplied account as the first `[[accounts]]` entry. Verify `git check-ignore -v config/majsoul.toml` reports the repository ignore rule and `git status --short` never lists the file. Do not print or inspect the file through command output after creation.

- [ ] **Step 5: Run the live import/cache/analysis validation**

Run:

```bash
HAIUN_RUN_MAJSOUL_LIVE=1 HAIUN_MAJSOUL_CONFIG="$PWD/config/majsoul.toml" \
  nix develop -c .venv/bin/python -m pytest backend/tests/integration/test_majsoul_live.py -v
```

Expected: one live test passes, including first download, canonicalization, completed `baseline-v1` analysis, and identical second-import IDs from cache.

- [ ] **Step 6: Remove the local real-credential file after validation**

Delete only `config/majsoul.toml`, keep `config/majsoul.example.toml`, and verify the real file is absent. This prevents credentials from remaining in the shared workspace after the requested live validation.

- [ ] **Step 7: Review the final diff for secret and temporary-directory references**

Run:

```bash
git diff --check
rg -n "majsoul-paipu-fetcher|access_token|plain-secret" backend/app backend/tests config README.md pyproject.toml frontend/src
git status --short
```

Expected: no runtime/test dependency on the temporary directory, no real credentials, no access-token logging, and only focused project changes plus the user's pre-existing unrelated modifications.
