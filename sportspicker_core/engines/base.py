import abc
from dataclasses import dataclass
from typing import Optional

from .inputs import MatchOutcome, PickInput


@dataclass
class ScoringResult:
    """Result of scoring a single pick against a match outcome."""

    is_correct: bool
    points_earned: int
    tiebreaker_score: Optional[int] = None

    def __str__(self):
        tb = f" (tiebreaker: {self.tiebreaker_score})" if self.tiebreaker_score is not None else ""
        return f"{'Correct' if self.is_correct else 'Incorrect'}: {self.points_earned}pts{tb}"


class BaseScoringEngine(abc.ABC):
    """
    Abstract base class for scoring engines.

    An engine turns one ``PickInput`` and one ``MatchOutcome`` into a
    ``ScoringResult``. Both are plain frozen dataclasses (see ``inputs``); an
    engine reads nothing else, and in particular never a storage object.
    Sport modules register engines with the sport registry, and the library
    ships ``BinaryScoringEngine`` for winner picks.

    A malformed input — the wrong type, a pick or a result naming a team that
    was not in the match, a missing sport detail — raises. Scoring it as zero
    would look like a member who picked wrong and hide the bug that produced
    it.
    """

    engine_name: str = "base"

    @abc.abstractmethod
    def score_pick(self, pick: PickInput, match: MatchOutcome) -> ScoringResult:
        """
        Score a single pick against a completed match.

        Returns a ScoringResult with correctness, points, and an optional
        tiebreaker score (lower is closer).
        """
        ...

    @staticmethod
    def check_inputs(pick, match) -> None:
        """Refuse anything that is not the input contract's own types."""
        if not isinstance(pick, PickInput):
            raise TypeError(f"pick must be a PickInput, not {type(pick).__name__}")
        if not isinstance(match, MatchOutcome):
            raise TypeError(f"match must be a MatchOutcome, not {type(match).__name__}")

    @staticmethod
    def check_in_match(team_id, match: MatchOutcome, what: str) -> None:
        """A team a pick or result names must be one of the match's two sides."""
        if team_id is not None and team_id not in match.team_ids:
            raise ValueError(
                f"{what} names team {team_id}, which is not in this match "
                f"(teams {match.team_ids})"
            )
