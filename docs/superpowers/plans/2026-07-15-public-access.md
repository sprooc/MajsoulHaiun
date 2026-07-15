# Public Guest and Admin Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shareable per-submission result URLs, an administrator-only global Analysis page, hidden password authentication, and one combined backend TOML configuration file.

**Architecture:** Preserve `analyses` as the computation cache and add `analysis_submissions` as the public capability resource created once per Start Analyze action. Protect only enumeration with a server-side admin session, while exact high-entropy `/results/<uuid>` URLs remain shareable. Read Mahjong Soul and administrator settings from one Git-ignored `config/config.toml`.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async ORM, Alembic, SQLite, React 19, React Router 7, TypeScript, Vitest, Testing Library, Playwright, TOML via `tomllib`.

## Global Constraints

- The Chinese product name is **牌运** and English/Chinese terminology must follow the existing locale resources.
- Never request, expose, log, persist in the database, or return Mahjong Soul passwords, OAuth tokens, verification codes, or browser sessions.
- The configured administrator password and raw session tokens must never appear in logs, exceptions, API responses, database records, or object representations.
- Opponents' voluntary discards may remain visible as `opponent_gift` but must not affect the main luck score.
- Preserve three-player rules, including excluding 2–8 manzu and supporting kita.
- Keep recursive `zh-CN` and `en` translation key trees identical.
- Guests may open a result only through its exact shareable capability URL and may not enumerate submissions.
- Every Start Analyze or reanalyze action creates a distinct submission UUID, including cache hits.
- Preserve unrelated work and use test-driven development for every behavior change.

---

## File Structure

- `backend/app/config.py`: operational environment settings and the new `HAIUN_CONFIG` path.
- `backend/app/config_file.py`: combined TOML models, validation, sanitized errors, and loader.
- `backend/app/sources/majsoul/fetch_config.py`: compatibility API that extracts Mahjong Soul settings from the combined loader.
- `backend/app/auth.py`: password verification, rate limiting, cookie/session authentication dependency.
- `backend/app/models/access.py`: `AdminSessionModel` and `AnalysisSubmissionModel` persistence.
- `backend/app/repositories/access_repository.py`: session and submission queries with token hashing at the boundary.
- `backend/app/api/access.py`: role, login, and logout endpoints.
- `backend/app/services/analysis_service.py`: cached analysis creation plus per-request submission envelopes.
- `backend/app/api/analyses.py`: public creation/result capability endpoints and protected administrator list.
- `backend/alembic/versions/0003_public_access.py`: tables, indexes, and backfill of existing analyses.
- `frontend/src/access/access-context.tsx`: shared role state, login, logout, and protected-route helper.
- `frontend/src/pages/admin-access-page.tsx`: unlinked password form.
- Existing frontend routes/pages/client/locales: switch details to `/results`, protect the list, and retain provisional navigation.

---

### Task 1: Combined Configuration File

**Files:**
- Create: `backend/app/config_file.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/sources/majsoul/fetch_config.py`
- Modify: `backend/app/api/replays.py`
- Modify: `backend/tests/sources/majsoul/test_fetch_config.py`
- Modify: `backend/tests/api/test_replays_api.py`
- Modify: `backend/tests/conftest.py`
- Create: `config/config.example.toml`
- Delete: `config/majsoul.example.toml`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Produces: `HaiunFileConfig`, `AdminConfig`, `load_haiun_config(path: Path, *, missing_ok: bool = False) -> HaiunFileConfig`.
- Produces: `Settings.config_path: Path`, overridden by `HAIUN_CONFIG`.
- Preserves: `load_majsoul_fetch_config(path: Path) -> MajsoulFetchConfig` for the fetcher.

- [ ] **Step 1: Write failing combined-config tests**

Add tests that write this exact shape and assert both sections load without secrets in `repr`:

```python
path.write_text(
    "timeout_seconds = 12\n"
    "[[accounts]]\nusername = 'first'\npassword = 'secret-one'\n"
    "[admin]\npassword = 'admin-secret'\nsession_hours = 12\n",
    encoding="utf-8",
)
config = load_haiun_config(path)
assert config.admin is not None
assert config.admin.password.get_secret_value() == "admin-secret"
assert config.majsoul.accounts[0].username == "first"
assert "admin-secret" not in repr(config)
assert "secret-one" not in repr(config)
```

Also assert `HAIUN_CONFIG` overrides the default and a missing file with `missing_ok=True` produces locked admin plus unconfigured Mahjong Soul state.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetch_config.py backend/tests/api/test_replays_api.py -v`

Expected: failures because `config_file.py`, `Settings.config_path`, and combined parsing do not exist.

- [ ] **Step 3: Implement the combined loader and settings path**

Use frozen Pydantic models with `SecretStr`:

```python
class AdminConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    password: SecretStr = Field(repr=False, min_length=12)
    session_hours: int = Field(default=12, ge=1, le=24 * 30)

class HaiunFileConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    accounts: tuple[MajsoulAccount, ...] = ()
    admin: AdminConfig | None = None

    @property
    def majsoul(self) -> MajsoulFetchConfig:
        return MajsoulFetchConfig(timeout_seconds=self.timeout_seconds, accounts=self.accounts)
```

Convert all file and validation failures into a sanitized `HaiunConfigError` containing the path but no raw values. Make `load_majsoul_fetch_config` call the combined loader and map empty accounts to the existing sanitized Mahjong Soul error.

- [ ] **Step 4: Rename repository configuration artifacts**

Create `config/config.example.toml` with top-level Mahjong Soul keys and an `[admin]` section, update `.gitignore` to `/config/config.toml`, update README commands to copy/chmod the single file, and remove all documentation of `HAIUN_MAJSOUL_CONFIG`.

Rename the ignored real file without printing it:

```bash
if [ -f config/majsoul.toml ] && [ ! -e config/config.toml ]; then mv config/majsoul.toml config/config.toml; fi
```

Do not add, inspect, or rewrite the ignored file. The operator will add the `[admin]` section locally.

- [ ] **Step 5: Run focused tests and commit**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/sources/majsoul/test_fetch_config.py backend/tests/sources/majsoul/test_fetcher.py backend/tests/api/test_replays_api.py -v`

Expected: PASS.

Commit: `git commit -m "feat: unify backend configuration"`

---

### Task 2: Administrator Sessions and Protected Access API

**Files:**
- Create: `backend/app/models/access.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/repositories/access_repository.py`
- Create: `backend/app/auth.py`
- Create: `backend/app/api/access.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/0003_public_access.py`
- Create: `backend/tests/api/test_access_api.py`
- Modify: `backend/tests/api/test_security.py`
- Modify: `backend/tests/repositories/test_migrations.py`

**Interfaces:**
- Produces: `require_admin(request: Request) -> None` FastAPI dependency.
- Produces: `GET /api/access`, `POST /api/admin/session`, and `DELETE /api/admin/session`.
- Produces: `AccessRepository.create_admin_session(expires_at) -> str`, `is_admin_token(raw_token) -> bool`, and `revoke_admin_token(raw_token) -> None`.

- [ ] **Step 1: Write failing authentication and migration tests**

Cover guest role, unavailable login with no `[admin]`, incorrect password, successful password, authenticated role, logout, expired token, database storing only SHA-256 token hashes, generic error payloads, and five failed attempts followed by HTTP 429.

Use a fixture configuration containing a test-only admin password of at least 12 characters. Assert the response cookie includes `HttpOnly` and `SameSite=lax`; use an HTTPS base URL in one test to assert `Secure`.

Extend the migration test to assert `admin_sessions` and `analysis_submissions` exist after upgrading to head.

- [ ] **Step 2: Run tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_access_api.py backend/tests/api/test_security.py backend/tests/repositories/test_migrations.py -v`

Expected: failures because the models, migration, repository, and endpoints do not exist.

- [ ] **Step 3: Implement server-side session persistence**

Define `AdminSessionModel` with UUID primary key, unique indexed `token_hash`, timezone-aware `expires_at`, and `created_at`. Generate tokens with `secrets.token_urlsafe(32)` and persist only `hashlib.sha256(token.encode()).hexdigest()`.

Repository validation must reject missing, unknown, or expired hashes and delete expired matching rows before returning guest status.

- [ ] **Step 4: Implement password verification and rate limiting**

In `auth.py`, compare UTF-8 password bytes with `secrets.compare_digest`. Add an in-memory limiter keyed by `request.client.host`, allowing five failures in 300 seconds and resetting on success. Never include submitted/configured values in exceptions.

Set cookie name `haiun_admin_session`, `httponly=True`, `samesite="lax"`, `secure=request.url.scheme == "https"`, `max_age=session_hours * 3600`, and `path="/"`.

Mark login/logout routes `include_in_schema=False`. Return only `{ "role": "admin" | "guest" }` from the access endpoint.

- [ ] **Step 5: Wire configuration and router into the app**

Load the combined file once in `create_app`, store it as `app.state.file_config`, initialize the limiter in app state, and include the access router before the static frontend mount.

- [ ] **Step 6: Run focused tests and commit**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_access_api.py backend/tests/api/test_security.py backend/tests/repositories/test_migrations.py -v`

Expected: PASS with no configured password or raw token in output.

Commit: `git commit -m "feat: add hidden administrator sessions"`

---

### Task 3: Per-Action Analysis Submissions and Shareable Results

**Files:**
- Modify: `backend/app/models/access.py`
- Modify: `backend/app/repositories/access_repository.py`
- Modify: `backend/app/services/analysis_service.py`
- Modify: `backend/app/api/analyses.py`
- Modify: `backend/tests/services/test_analysis_service.py`
- Modify: `backend/tests/api/test_analyses_api.py`
- Modify: `backend/tests/api/test_replays_api.py`
- Modify: `backend/tests/repositories/test_migrations.py`

**Interfaces:**
- Produces: `AnalysisService.submit(...) -> AnalysisEnvelope`, where envelope `id` is the submission UUID.
- Produces: `AnalysisService.get_submission(submission_id) -> AnalysisEnvelope`.
- Produces: `AnalysisService.list_submissions() -> list[AnalysisEnvelope]`.
- Produces: public `GET /api/results/{submission_id}` and administrator-only `GET /api/analyses`.

- [ ] **Step 1: Write failing submission tests**

Assert two identical `POST /api/analyses` requests return different IDs, both `GET /api/results/<id>` calls resolve, only one cached `AnalysisModel` exists, and two `AnalysisSubmissionModel` rows exist.

Assert guest `GET /api/analyses` is 403, authenticated admin listing returns both submissions, and unknown result IDs return typed `ANALYSIS_NOT_FOUND` 404.

Assert the migration backfills one submission per existing analysis using the same UUID and timestamp.

- [ ] **Step 2: Run tests and verify RED**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/services/test_analysis_service.py backend/tests/api/test_analyses_api.py backend/tests/api/test_replays_api.py backend/tests/repositories/test_migrations.py -v`

Expected: failures because create still returns cached analysis IDs and the public result endpoint is absent.

- [ ] **Step 3: Implement submission persistence and envelopes**

Define `AnalysisSubmissionModel` with UUID primary key, indexed analysis foreign key, relationship, and creation timestamp. Add repository methods:

```python
async def add_submission(self, analysis_id: UUID) -> AnalysisSubmissionModel
async def get_submission(self, submission_id: UUID) -> AnalysisSubmissionModel | None
async def list_submissions(self) -> list[AnalysisSubmissionModel]
```

Refactor `AnalysisService` so cached computation lookup/creation remains internal. `submit` always inserts a new submission after resolving the cached analysis. Envelope construction receives both models, exposes submission `id`/`created_at`, and derives status/result from the linked analysis.

- [ ] **Step 4: Refactor background processing and API authorization**

`POST /api/analyses` schedules processing with the internal analysis UUID but returns the submission envelope. `GET /api/results/{submission_id}` is public. `GET /api/analyses` adds `Depends(require_admin)`. Remove the public internal-ID detail route.

Handle concurrent cache insertion through the existing unique cache key by re-querying after `IntegrityError`, without returning duplicate computation failures.

- [ ] **Step 5: Run focused tests and commit**

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/services/test_analysis_service.py backend/tests/api/test_analyses_api.py backend/tests/api/test_replays_api.py backend/tests/repositories/test_migrations.py -v`

Expected: PASS.

Commit: `git commit -m "feat: add shareable analysis submissions"`

---

### Task 4: Frontend Access State and Hidden Admin Page

**Files:**
- Create: `frontend/src/access/access-context.tsx`
- Create: `frontend/src/pages/admin-access-page.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/app.tsx`
- Modify: `frontend/src/locales/zh-CN/common.json`
- Modify: `frontend/src/locales/en/common.json`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/test/app.test.tsx`
- Create: `frontend/src/test/admin-access-page.test.tsx`
- Modify: `frontend/src/test/locale-keys.test.ts`

**Interfaces:**
- Produces: `AccessProvider`, `useAccess()`, and `RequireAdmin`.
- Produces client functions `getAccessRole`, `createAdminSession`, and `deleteAdminSession`.
- Produces unlinked frontend route `/admin`.

- [ ] **Step 1: Write failing shell and admin-page tests**

Guest test: `/api/access` returns guest, no Analysis navigation link exists, and entering `/analyses` redirects to `/`.

Admin test: submit the unlinked `/admin` form, mock successful session creation, verify navigation to `/analyses`, verify the Analysis link appears, then logout and verify it disappears.

Assert both locale trees contain identical new access/login/logout/error keys.

- [ ] **Step 2: Run tests and verify RED**

Run: `nix develop -c npm --prefix frontend test -- --run frontend/src/test/app.test.tsx frontend/src/test/admin-access-page.test.tsx frontend/src/test/locale-keys.test.ts`

Expected: failures because access context and admin route do not exist.

- [ ] **Step 3: Implement access context and API client**

Use role state `"checking" | "guest" | "admin"`. Fetch `/api/access` once on mount. Login posts `{ secret }`, refreshes role, and logout deletes the server session then sets guest. Do not store the password or session in browser storage.

`RequireAdmin` renders a small loading state while checking and `<Navigate to="/" replace />` for guests.

- [ ] **Step 4: Implement the unlinked admin page and conditional shell**

Add `/admin` without a navigation link. Use a password input with `autoComplete="current-password"`, generic invalid/rate-limit errors, and navigation to `/analyses` after success.

Render Analysis navigation and logout only for the admin role. Keep the existing language and health controls.

- [ ] **Step 5: Run frontend tests and commit**

Run: `nix develop -c npm --prefix frontend test -- --run frontend/src/test/app.test.tsx frontend/src/test/admin-access-page.test.tsx frontend/src/test/locale-keys.test.ts`

Expected: PASS.

Commit: `git commit -m "feat: add hidden admin access UI"`

---

### Task 5: Public Result Routes and Administrator Analysis List

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/home-page.tsx`
- Modify: `frontend/src/pages/analysis-detail-page.tsx`
- Modify: `frontend/src/pages/analysis-list-page.tsx`
- Modify: `frontend/src/pages/game-analysis-page.tsx`
- Modify: `frontend/src/app.tsx`
- Modify: `frontend/src/test/home-page.test.tsx`
- Modify: `frontend/src/test/analysis-detail-page.test.tsx`
- Modify: `frontend/src/test/analysis-list-page.test.tsx`
- Modify: `frontend/tests/e2e/search-and-analyze.spec.ts`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_frontend_fallback.py`

**Interfaces:**
- Consumes: submission envelope IDs from Task 3.
- Produces: public route `/results/:analysisId`, legacy redirect `/analyses/:analysisId`, and `getAnalysis` backed by `/api/results/<id>`.

- [ ] **Step 1: Write failing route and navigation tests**

Update tests to expect immediate `/results/provisional-...` navigation, permanent `/results/<submission-id>` replacement, administrator cards linking to `/results/<id>`, and reanalysis navigating to a distinct URL without replacing previous history.

Add a backend production-serving test that creates a temporary frontend `dist/index.html` or injects a static directory and verifies a direct non-API `/results/<uuid>` request receives the SPA index while missing `/api/...` remains an API 404.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `nix develop -c npm --prefix frontend test -- --run frontend/src/test/home-page.test.tsx frontend/src/test/analysis-detail-page.test.tsx frontend/src/test/analysis-list-page.test.tsx`

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_frontend_fallback.py -v`

Expected: failures because routes and endpoints still use `/analyses/<id>` and static serving has no SPA fallback.

- [ ] **Step 3: Switch the result lifecycle to `/results`**

Change provisional creation, resolution, polling, list links, and reanalysis navigation. Only provisional-to-permanent resolution uses `{ replace: true }`; a new reanalysis uses normal navigation so each action remains in history.

Change `getAnalysis(id)` to request `/api/results/${id}`. Keep the existing result rendering, three-player summaries, and all analysis components unchanged.

- [ ] **Step 4: Add production SPA fallback**

Replace the plain static mount with a focused `SPAStaticFiles` implementation that returns `index.html` for missing GET/HEAD non-API frontend paths, while real static assets and all `/api` routes keep normal 404 behavior.

- [ ] **Step 5: Run focused tests and end-to-end test**

Run: `nix develop -c npm --prefix frontend test -- --run frontend/src/test/home-page.test.tsx frontend/src/test/analysis-detail-page.test.tsx frontend/src/test/analysis-list-page.test.tsx frontend/src/test/app.test.tsx`

Run: `nix develop -c .venv/bin/python -m pytest backend/tests/api/test_frontend_fallback.py -v`

Run: `nix develop -c npm --prefix frontend run e2e`

Expected: PASS and the E2E URL matches `/results/<id>`.

Commit: `git commit -m "feat: route analyses through shareable results"`

---

### Task 6: Documentation, Security Review, and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `scripts/start.sh`
- Modify: any tests exposed by full-suite verification, limited to behavior required by this design.

**Interfaces:**
- Produces: operator instructions for single config, hidden admin URL, shareable result URLs, reverse-proxy TLS, and secure file permissions.

- [ ] **Step 1: Update public deployment documentation and startup copy**

Document:

- `cp config/config.example.toml config/config.toml`
- `chmod 600 config/config.toml`
- `[admin]` password/session configuration.
- `/admin` is deliberately unlinked but password-protected.
- Result links are intentionally shareable and must be treated as capability URLs.
- TLS/reverse proxy remains required for public deployment.

Remove the old “no authentication is enabled” warning and replace it with a warning when `[admin]` is absent, without printing the config or password.

- [ ] **Step 2: Run secret and locale scans**

Run:

```bash
rg -n 'HAIUN_MAJSOUL_CONFIG|config/majsoul\.toml|/api/analyses/\{analysis_id\}|/analyses/\$\{.*id' README.md backend frontend scripts config
git diff --check
```

Expected: no stale configuration or result-route references except intentional migration/legacy tests; no whitespace errors.

- [ ] **Step 3: Run all required checks**

Run:

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
bash -n scripts/dev.sh scripts/start.sh
shellcheck scripts/dev.sh scripts/start.sh
```

Expected: all commands exit 0.

- [ ] **Step 4: Review database and API security invariants**

Confirm through tests or read-only inspection that:

- `admin_sessions` contains hashes only.
- the public OpenAPI schema contains no login route or credential field.
- guest analysis-list access is 403.
- known result UUID access is 200 and unknown UUID access is 404.
- repeated identical submissions have different public IDs and one cached analysis.
- no real `config/config.toml` content is staged.

- [ ] **Step 5: Commit final documentation and verification fixes**

Commit: `git commit -m "docs: document public access configuration"`
