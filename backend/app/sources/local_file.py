from pathlib import Path

from app.errors import AppError


MAX_REPLAY_BYTES = 32 * 1024 * 1024
BLOCKED_SUFFIXES = {".exe", ".dll", ".msi", ".com", ".bat", ".cmd", ".ps1", ".zip", ".tar", ".gz", ".7z"}


def validate_replay_file(filename: str, payload: bytes) -> None:
    if len(payload) > MAX_REPLAY_BYTES:
        raise AppError("REPLAY_FILE_TOO_LARGE", "Replay files are limited to 32 MiB.", status_code=413)
    if not payload:
        raise AppError("EMPTY_REPLAY_FILE", "Replay file is empty.", status_code=422)
    if Path(filename).suffix.lower() in BLOCKED_SUFFIXES or payload.startswith((b"MZ", b"PK\x03\x04")):
        raise AppError("UNSUPPORTED_REPLAY_FILE", "Executable and archive files are not accepted.", status_code=422)
