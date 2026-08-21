import abc
from dataclasses import dataclass
from typing import Optional


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

    Sport modules register concrete implementations at AppConfig.ready() time.
    The core system provides BinaryScoringEngine as the default, which ports
    the proven algorithm from legacypickem.
    """

    engine_name: str = "base"

    @abc.abstractmethod
    def score_pick(self, pick, match) -> ScoringResult:
        """
        Score a single pick against a completed match.

        Args:
            pick: A contests.Pick instance
            match: A sports.Match instance (must have MatchTeam entries with scores)

        Returns:
            ScoringResult with correctness, points, and optional tiebreaker score
        """
        ...

    def get_match_winner(self, match) -> Optional[object]:
        """
        Determine the winner of a match from MatchTeam entries.

        Returns the winning Team, or None for a draw/tie.
        Convention: MatchTeam.order=0 is away, order=1 is home.
        """
        match_teams = list(match.matchteam_set.all().order_by("order"))
        if len(match_teams) != 2:
            return None

        away, home = match_teams[0], match_teams[1]

        if home.score is not None and away.score is not None:
            if home.score > away.score:
                return home.team
            elif away.score > home.score:
                return away.team
        return None

    def get_match_scores(self, match) -> tuple:
        """
        Return (away_score, home_score) tuple from MatchTeam entries.

        Convention: order=0 is away, order=1 is home.
        """
        match_teams = list(match.matchteam_set.all().order_by("order"))
        if len(match_teams) != 2:
            return (None, None)

        return (match_teams[0].score, match_teams[1].score)

    def get_home_team(self, match) -> Optional[object]:
        """Return the home team (order=1) for this match."""
        try:
            return match.matchteam_set.get(order=1).team
        except Exception:
            return None

    def get_away_team(self, match) -> Optional[object]:
        """Return the away team (order=0) for this match."""
        try:
            return match.matchteam_set.get(order=0).team
        except Exception:
            return None
