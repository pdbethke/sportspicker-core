"""
MMA Scoring Engine.

Scoring model:
  - Correct winner:                    1 point
  - Correct winner + correct method:   2 points  (1 + 1 bonus)
  - Correct winner + correct round:    2 points  (1 + 1 bonus)
  - Correct winner + method + round:   5 points  (jackpot)
  - Wrong winner:                      0 points
  - Draw/no-contest:                   1 point for everyone (like ties in team sports)

Tiebreaker:
  If the pick has predicted_home_score set, it's interpreted as a total fight time
  prediction in seconds. Tiebreaker score = |predicted - actual| (lower is better).

A fight with no FightResult, or a result or pick naming someone who was not in
the fight, raises rather than scoring zero for everyone.
"""
from .base import BaseScoringEngine, ScoringResult
from .inputs import FightResult, MatchOutcome, PickInput


class MmaScoringEngine(BaseScoringEngine):

    engine_name = "mma"

    def score_pick(self, pick: PickInput, match: MatchOutcome) -> ScoringResult:
        self.check_inputs(pick, match)
        result = match.detail
        if not isinstance(result, FightResult):
            raise ValueError(
                f"an MMA match needs a FightResult as its detail to be scored, "
                f"not {type(result).__name__}"
            )
        self.check_in_match(result.winner_id, match, "the fight result")
        self.check_in_match(pick.picked_team_id, match, "the pick")

        # Draw / no-contest — everyone gets credit
        if result.method in ("draw", "no_contest") or result.winner_id is None:
            return ScoringResult(is_correct=True, points_earned=1, tiebreaker_score=None)

        # Check winner
        if pick.picked_team_id != result.winner_id:
            return ScoringResult(is_correct=False, points_earned=0, tiebreaker_score=None)

        # Winner is correct — calculate bonus points
        correct_method = bool(
            pick.predicted_method
            and self._normalize_method(pick.predicted_method) == self._normalize_method(result.method)
        )
        correct_round = (
            pick.predicted_round is not None
            and pick.predicted_round == result.round
        )

        if correct_method and correct_round:
            points = 5  # Jackpot
        elif correct_method or correct_round:
            points = 2  # Winner + one bonus
        else:
            points = 1  # Winner only

        # Tiebreaker: fight time prediction
        tiebreaker_score = None
        if pick.predicted_home_score is not None and result.total_fight_time_seconds is not None:
            tiebreaker_score = abs(pick.predicted_home_score - result.total_fight_time_seconds)

        return ScoringResult(
            is_correct=True,
            points_earned=points,
            tiebreaker_score=tiebreaker_score,
        )

    @staticmethod
    def _normalize_method(method: str) -> str:
        """Normalize method strings for comparison."""
        method = method.lower().strip()
        # Treat KO and TKO as the same
        if method in ("ko", "tko", "ko/tko"):
            return "ko"
        # Normalize decision variants
        if method in ("decision", "unanimous", "split", "majority"):
            return "decision"
        if method in ("sub", "submission"):
            return "submission"
        if method in ("dq", "disqualification"):
            return "dq"
        return method
