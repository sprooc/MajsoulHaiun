# Public Guest and Admin Access Design

## Goal

Make 牌运 safe to expose as a public website with two access modes:

- Guests can search, import, start analyses, and open a result when they know its exact shareable URL.
- Administrators can additionally open the global Analysis page and see every submitted result.
- No login link appears in the public interface. The operator enters the unlinked `/admin` route and authenticates with a backend-configured password.

The result-link model is deliberately shareable rather than browser-bound. A guest cannot enumerate other results, but anyone who receives a result URL may open it.

## Analysis Storage and Public Result Links

The existing `analyses` table remains the internal computation cache, keyed by game, algorithm version, and options. A new `analysis_submissions` table represents public analysis requests:

- `id`: a random UUID used in the public result URL.
- `analysis_id`: the cached computation used by the submission.
- `created_at`: the time the visitor clicked Start Analyze.

Every Start Analyze or reanalyze action creates a new submission, even when it reuses a completed or in-progress cached computation. Therefore every action receives a distinct `/results/<submission-id>` URL without recomputing identical work.

The migration creates one submission for each existing analysis, reusing the existing analysis UUID as the submission UUID. Existing stored results therefore remain visible in the administrator list and become available at `/results/<old-analysis-id>`.

## API Authorization

Public endpoints:

- Player search and game listing.
- Replay import.
- Algorithm listing.
- `POST /api/analyses`, which creates a new submission and returns its result envelope.
- `GET /api/results/{submission_id}`, which returns one result only when its exact UUID is supplied.
- `GET /api/access`, which reports only whether the current request has an authenticated admin session.

Administrator-only endpoints:

- `GET /api/analyses`, which lists every submission in reverse creation order.

There is no public list, search, sequential identifier, or API response that exposes unrelated submission IDs. Missing results and unknown capability URLs use the existing typed 404 behavior. The backend enforces administrator access; hiding links and routes in React is only presentation.

Internal analysis IDs are not used as new public result identifiers. The background worker continues processing the cached analysis record, while API envelopes expose the submission UUID as `id`.

## Administrator Authentication

`/admin` is an unlinked frontend route with a password form. It is not advertised in navigation, public copy, or generated API documentation.

The login API compares the submitted secret with the configured administrator password using a constant-time comparison. On success it creates a cryptographically random opaque session token, stores only the token hash and expiration in a new `admin_sessions` table, and sets the raw token in an HTTP-only, SameSite=Lax cookie. The cookie is marked Secure when the request is HTTPS. Sessions expire after the configured duration and can be revoked through logout.

Failed login attempts are rate-limited per client address in the running backend process. Authentication errors are generic and never reveal configuration state or the expected password. Passwords and session tokens must not appear in logs, exceptions, database records, API responses, or object representations.

Authenticated administrators see the Analysis navigation entry and a logout control. Guests see neither. Guest navigation to `/analyses` redirects home. The legacy `/analyses/<id>` detail route redirects to `/results/<id>` so old bookmarks remain useful without exposing the list.

## Single Configuration File

The backend default becomes `config/config.toml`, overridable with `HAIUN_CONFIG`. The repository contains `config/config.example.toml`; the real file remains Git ignored and should be mode `0600`.

The existing Mahjong Soul keys stay at the top level so the operator's ignored credential file can be renamed without reading or rewriting its secrets. General settings use their own tables:

```toml
timeout_seconds = 15

[[accounts]]
username = "first-account@example.com"
password = "replace-me"
host = "https://game.maj-soul.com"

[admin]
password = "replace-with-a-long-unique-password"
session_hours = 12
```

`HAIUN_MAJSOUL_CONFIG` and the separate `majsoul.toml` path are removed. Host, port, data directory, and CORS environment overrides remain operational settings because the launch scripts need them independently of application secrets.

The configuration loader validates Mahjong Soul and admin sections independently. A missing admin section leaves all admin-only endpoints locked and login unavailable rather than making them public. Mahjong Soul configuration errors retain sanitized messages and never echo usernames or passwords.

## Frontend Flow

On application startup, the shell requests `/api/access`. The Analysis navigation entry is hidden until an admin role is confirmed.

Starting an analysis preserves the current immediate-navigation behavior:

1. Create a client-side provisional result and navigate to `/results/provisional-<uuid>` immediately.
2. Import and canonicalize the replay.
3. Create the backend submission.
4. Replace only the provisional URL with `/results/<submission-id>`.
5. Poll that exact result endpoint until the cached computation completes or fails.

Starting another analysis or reanalysis creates and navigates to another result URL. Previously created URLs remain valid and are never overwritten.

The administrator Analysis page keeps the existing layout and pending/completed sections, but its cards represent submissions. Completed cards link to `/results/<submission-id>`. The public result page retains the existing game summary, processing state, result visualizations, and reanalysis controls.

Because shared result links must work when opened directly in production, the backend's static frontend serving will fall back to `index.html` for non-API routes that do not match a real asset.

## Error Handling

- Incorrect or rate-limited admin login receives a generic typed error.
- Expired, revoked, or unknown admin sessions are treated as guest access.
- Guest requests to the analysis list receive HTTP 403 even if the frontend route is bypassed.
- Unknown result capabilities receive HTTP 404.
- Missing or invalid application configuration returns sanitized configuration errors without exposing secrets.
- Analysis processing and replay-import errors continue using the existing result-page states and typed backend errors.

## Testing

Backend tests will cover:

- Parsing the combined TOML, environment path override, optional admin configuration, and secret-safe representations/errors.
- A new submission UUID for every create request, including cache hits.
- Multiple submissions sharing one cached analysis computation.
- Backfill and persistence of submissions through migrations.
- Public access to a known result URL and 404 for an unknown URL.
- HTTP 403 for the guest analysis list.
- Admin login success/failure, hashed server-side tokens, expiry, logout, cookie attributes, and rate limiting.
- Admin access to the complete submission list.
- API schemas and errors containing no configured secrets or session tokens.

Frontend tests will cover:

- Guest navigation without an Analysis entry and redirect from `/analyses`.
- Unlinked `/admin` login, authenticated navigation, Analysis page access, and logout.
- Immediate provisional `/results/...` navigation followed by replacement with a permanent URL.
- Unique result URLs for repeated submissions and reanalysis.
- Public loading, polling, and rendering through `/api/results/<id>`.
- Administrator list cards linking to public result URLs.
- Recursive equality of the Chinese and English locale key trees.

The full backend test suite, frontend test suite, production frontend build, end-to-end tests, and relevant shell checks will run before completion.

## Out of Scope

- Named guest accounts or browser-bound ownership.
- Preventing a recipient from opening an intentionally shared result URL.
- Password reset, multiple administrator accounts, roles beyond guest/admin, or third-party OAuth.
- A public or guest-specific analysis history page.
- Moving operational launch settings away from their existing environment variables.
