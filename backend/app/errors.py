from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.parameters = parameters or {}


class SourceUnavailable(AppError):
    def __init__(self, code: str = "SOURCE_UNAVAILABLE", message: str = "Replay source is unavailable.") -> None:
        super().__init__(code, message, status_code=503)
