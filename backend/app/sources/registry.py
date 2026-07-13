from app.errors import AppError
from app.sources.base import ReplaySource


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, ReplaySource] = {}

    def register(self, source: ReplaySource) -> None:
        self._sources[source.id] = source

    def get(self, source_id: str) -> ReplaySource:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise AppError("UNKNOWN_SOURCE", "Unknown replay source.", status_code=404) from exc

    def all(self) -> list[ReplaySource]:
        return list(self._sources.values())
