from abc import ABC, abstractmethod

from app.domain.analysis import AnalysisOptions, GameLuckAnalysis
from app.domain.game import CanonicalGame
from app.domain.rules import RuleSet


class LuckAlgorithm(ABC):
    id: str
    version: str
    name_key: str
    description_key: str

    @abstractmethod
    def supports(self, rules: RuleSet) -> bool: ...

    @abstractmethod
    def analyze(self, game: CanonicalGame, options: AnalysisOptions) -> GameLuckAnalysis: ...
