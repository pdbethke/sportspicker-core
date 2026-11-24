from .base import BaseScoringEngine, ScoringResult
from .inputs import MatchOutcome, PickInput


class BinaryScoringEngine(BaseScoringEngine):
    """
    Scoring engine for winner picks: one point per correct winner.

    Scoring rules:
    - Binary picks: +1 point if picked winner matches actual winner.
      Ties (actual) count as correct for everyone.
    - Tiebreaker picks: Also scored as binary win/loss, plus a tiebreaker
      score = |predicted_home - actual_home| + |predicted_away - actual_away|.
      Lower tiebreaker is better.
    - A match without both scores has no result yet and scores nothing.
    """

    engine_name = "binary"

    def score_pick(self, pick: PickInput, match: MatchOutcome) -> ScoringResult:
        self.check_inputs(pick, match)
        self.check_in_match(pick.picked_team_id, match, "the pick")
        if not match.is_scored:
            return ScoringResult(is_correct=False, points_earned=0)

        home_score, away_score = match.home.score, match.away.score
        actual_winner = match.winner_team_id
        is_tie = actual_winner is None and away_score == home_score

        picked_winner = self._resolve_picked_winner(pick, match)

        if is_tie:
            # A tied game counts as correct for everyone
            is_correct = True
        elif picked_winner is not None and actual_winner is not None:
            is_correct = picked_winner == actual_winner
        else:
            is_correct = False

        points = 1 if is_correct else 0

        tiebreaker_score = None
        if pick.predicted_home_score is not None and pick.predicted_away_score is not None:
            tiebreaker_score = (
                abs(pick.predicted_home_score - home_score)
                + abs(pick.predicted_away_score - away_score)
            )

        return ScoringResult(
            is_correct=is_correct,
            points_earned=points,
            tiebreaker_score=tiebreaker_score,
        )

    @staticmethod
    def _resolve_picked_winner(pick: PickInput, match: MatchOutcome) -> int | None:
        """
        The team the member picked to win.

        Priority:
        1. If picked_team_id is set directly, use it
        2. If predicted scores are set, derive winner from scores
        3. Otherwise, None
        """
        if pick.picked_team_id is not None:
            return pick.picked_team_id

        if pick.predicted_home_score is not None and pick.predicted_away_score is not None:
            if pick.predicted_home_score > pick.predicted_away_score:
                return match.home.team_id
            elif pick.predicted_away_score > pick.predicted_home_score:
                return match.away.team_id

        return None
