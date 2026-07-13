# Linux and NixOS Runtime Design

## Goal

Make the Haiun implementation plan work on NixOS and conventional Linux distributions without retaining Windows or PowerShell assumptions.

## Runtime environments

The repository will support two Linux workflows:

- NixOS and other Nix-enabled systems use a checked-in `flake.nix` and `flake.lock`. The flake provides a development shell plus `dev` and `start` apps.
- Conventional Linux systems use POSIX-compatible Bash scripts and install Python 3.11+, Node.js, npm, and required browser libraries through their distribution.

Both workflows call the same scripts and use the same environment variables so their behavior does not drift.

## Network access

The application listens on `0.0.0.0:8765` by default so other devices on the local network can reach it. `HAIUN_HOST` and `HAIUN_PORT` override the binding. Setting `HAIUN_HOST=127.0.0.1` restores local-only operation.

CORS remains deny-by-default for unrelated origins. `HAIUN_ALLOWED_ORIGINS` accepts an explicit comma-separated allowlist for deployments whose frontend and API use different origins. Same-origin production access does not require permissive CORS.

Because the MVP has no authentication, documentation must warn against exposing it directly to the public Internet. Public deployment requires a TLS-enabled reverse proxy with authentication and appropriate firewall rules.

## Project-local data

Runtime state defaults to `<repository>/data`, independent of the caller's current working directory. The directory contains the SQLite database, raw replay files, canonical data, cached analyses, and other generated state. It is created automatically and ignored by Git.

`HAIUN_DATA_DIR` can override the default for packaged or administered deployments. Deleting `data/` removes all default local state, and copying it backs that state up.

## Launch behavior

`scripts/dev.sh` starts the backend and frontend development servers, forwards termination signals, and cleans up both child processes. The Vite development server also binds to a configurable address so LAN clients can load it.

`scripts/start.sh` verifies or builds the frontend production assets, creates the data directory, starts FastAPI serving the frontend and API, and prints loopback and discoverable LAN URLs. It uses `xdg-open` only when a graphical session and the command are available; headless startup remains successful.

The scripts resolve the repository root from their own path and therefore work from any current directory.

## Verification

Tests cover default and overridden host, port, data directory, CORS allowlists, and rejection of arbitrary origins. Shell scripts are syntax-checked with `bash -n` and, when available, ShellCheck. The complete backend, frontend, build, and Playwright suites run from Bash and from the Nix development shell.

Acceptance requires that no PowerShell files, commands, or Windows-specific paths remain in the implementation plan.
