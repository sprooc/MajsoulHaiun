from app.algorithms.base import LuckAlgorithm
from app.errors import AppError


class AlgorithmRegistry:
    def __init__(self) -> None:
        self._algorithms: dict[str, LuckAlgorithm] = {}

    def register(self, algorithm: LuckAlgorithm) -> None:
        self._algorithms[algorithm.id] = algorithm

    def get(self, algorithm_id: str) -> LuckAlgorithm:
        try:
            return self._algorithms[algorithm_id]
        except KeyError as exc:
            raise AppError("UNKNOWN_ALGORITHM", "Unknown luck algorithm.", status_code=404) from exc

    def all(self) -> list[LuckAlgorithm]:
        return list(self._algorithms.values())
