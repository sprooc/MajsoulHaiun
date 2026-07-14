# Authenticated Mahjong Soul Replay Fetch Design

## Goal

Enable 牌运 to import a Mahjong Soul replay link or record ID, fetch the complete replay through configured Mahjong Soul accounts, cache the replay locally, canonicalize it, and run the existing luck analysis without depending on the temporary `majsoul-paipu-fetcher/` directory.

## Configuration

The backend reads an operator-managed TOML file from `config/majsoul.toml` by default. `HAIUN_MAJSOUL_CONFIG` may override the path. The real file is Git ignored; the repository contains only `config/majsoul.example.toml`.

The file contains global fetch settings and an ordered list of accounts:

```toml
timeout_seconds = 15

[[accounts]]
username = "first-account@example.com"
password = "replace-me"
host = "https://game.maj-soul.com"

[[accounts]]
username = "second-account@example.com"
password = "replace-me"
```

`host` defaults to `https://game.maj-soul.com`. Account order is significant. Passwords remain in memory only while the backend reads the configuration and performs login. They must not appear in API schemas, database records, application logs, exception messages, or object representations.

## Fetch Architecture

The implementation may depend on `tensoul` for its core Mahjong Soul RPC channel and session behavior. It must not depend on the temporary `majsoul-paipu-fetcher/` source tree, reuse its Tenhou mlog conversion, or import `tensoul` only to use its exception types.

A Haiun-owned downloader adapter will:

1. Fetch the current Mahjong Soul Unity Web client version.
2. Read the current Mahjong Soul gateway configuration.
3. Discover a WebSocket endpoint through `/api/clientgate/routes`, retaining the legacy route fallback.
4. Connect through the `tensoul` RPC channel.
5. Build and send the username/password login request using the current Web client metadata.
6. Fetch `ResGameRecord` for the requested record UUID.
7. Serialize the response as a protobuf `Wrapper` named `.lq.ResGameRecord` so Haiun's existing `decode_majsoul` binary path can consume it directly.
8. Close the connection in all success and failure paths.

Haiun defines its own exception hierarchy for missing configuration, login failure, replay access failure, gateway/network failure, timeout, and invalid protocol responses. Passwords and access tokens are never included in these exceptions.

## Multi-Account Behavior

Accounts are attempted in TOML order.

- Login rejection for one account continues with the next account.
- Mahjong Soul error `1203` (record missing or inaccessible to the account) continues with the next account.
- A successful fetch stops iteration immediately.
- Configuration errors, gateway discovery failures, protocol failures, and general network failures stop immediately because they are not account-specific.
- If every configured account is rejected or lacks access, the fetcher raises one sanitized `ReplayFetchUnavailable` error.

## Cache and Import Flow

Raw replay identity is `(source, external_id)`, where Mahjong Soul replays use `source="majsoul"` and `external_id=<record UUID>`.

The persistence layer will add a unique constraint and lookup method for this identity. Import flow becomes:

1. Parse and validate the locator.
2. Look up the raw replay by `("majsoul", record_id)`.
3. On a cache hit, return the existing replay without loading credentials, connecting, logging in, or downloading.
4. On a cache miss, fetch the wrapped protobuf payload and save it under the source/external identity.
5. Decode and canonicalize the stored payload through the existing replay API path.
6. Reuse the existing canonical game for the raw replay and current schema version when present; otherwise create it from the cached raw payload.

The repository keeps SHA-256 deduplication as a secondary content-level safeguard. Concurrent inserts for the same source/external identity must resolve to the already stored replay rather than creating duplicates or surfacing an integrity error.

## API and User Experience

The existing `POST /api/replays/import-locator` request shape remains unchanged and never accepts credentials. A successful import returns `replayId` and `gameId`, whether the data was downloaded or served from cache. The frontend can immediately invoke the existing analysis endpoint.

Existing generic import failure handling remains compatible. Backend error codes will distinguish missing/invalid server configuration, unavailable replay access, and remote/network failure without revealing which usernames were attempted.

The README will document local TOML setup, the multi-account order, the Git-ignore guarantee, and the fact that credentials are backend-only.

## Testing

Automated tests will cover:

- TOML parsing, defaults, ordering, empty/malformed account lists, and secret-safe representations.
- Current client version extraction and route selection.
- Successful login and raw `ResGameRecord` wrapping without using mlog conversion.
- Account fallback after login rejection and error `1203`.
- Immediate failure for global gateway/network/protocol errors.
- Guaranteed connection cleanup.
- Cache hit before credential loading or network access.
- Source/external-ID deduplication, including repeated and concurrent imports.
- Cached raw replay canonicalization and reuse of an existing canonical game.
- API import producing a `gameId` that can run `baseline-v1` analysis.

After automated checks pass, a local Git-ignored TOML containing the user-provided credentials will be used for one live validation against the supplied replay link. The validation must confirm download, cache reuse on a second import, canonicalization, and completed analysis. No command output or committed artifact may contain the password or session material.

## Out of Scope

- OAuth, email verification, browser-session import, or frontend credential entry.
- Account health dashboards or automatic account reordering.
- Tenhou mlog output or a second mlog-to-Haiun converter.
- Depending on any file under `majsoul-paipu-fetcher/` at runtime or test time.
