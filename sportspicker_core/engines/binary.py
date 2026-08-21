from .base import BaseScoringEngine, ScoringResult


class BinaryScoringEngine(BaseScoringEngine):
    """
    Default scoring engine ported from legacypickem.

    Scoring rules:
    - Binary picks: +1 point if picked winner matches actual winner.
      Ties (actual) count as correct for everyone.
    - Tiebreaker picks: Also scored as binary win/loss, plus a tiebreaker
      score = |predicted_home - actual_home| + |predicted_away - actual_away|.
      Lower tiebreaker is better.
    """

    engine_name = "binary"

    def score_pick(self, pick, match) -> ScoringResult:
        away_score, home_score = self.get_match_scores(match)
        if away_score is None or home_score is None:
            return ScoringResult(is_correct=False, points_earned=0)

        actual_winner = self.get_match_winner(match)
        is_tie = actual_winner is None and away_score == home_score

        # Determine picked winner
        picked_winner = self._resolve_picked_winner(pick, match)

        # Check correctness
        if is_tie:
            # Ties count as correct for everyone (legacy behavior: actual_winner_id = 99999999)
            is_correct = True
        elif picked_winner is not None and actual_winner is not None:
            is_correct = picked_winner.id == actual_winner.id
        else:
            is_correct = False

        points = 1 if is_correct else 0

        # Calculate tiebreaker score if this is a tiebreaker pick
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

    def _resolve_picked_winner(self, pick, match):
        """
        Determine the user's picked winner.

        Priority (matching legacypickem logic):
        1. If picked_team is set directly, use it
        2. If predicted scores are set, derive winner from scores
        3. Otherwise, None
        """
        if pick.picked_team_id:
            return pick.picked_team

        if pick.predicted_home_score is not None and pick.predicted_away_score is not None:
            if pick.predicted_home_score > pick.predicted_away_score:
                return self.get_home_team(match)
            elif pick.predicted_away_score > pick.predicted_home_score:
                return self.get_away_team(match)

        return None
