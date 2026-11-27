"""
Against the spread: a pick is right when the side it named covers the line.

The line handicaps the home side. ``home_spread`` is added to the home
side's score and the sum is compared with the away side's: -3.5 means home
is favoured by 3.5 and covers only by winning by 4 or more, and +3.5 means
home covers by losing by 3 or fewer, or by winning. One number says it all,
so the line is given once and never per side.

A game that lands exactly on a whole-number line is a **push**, and a push
is right for everyone, picked or not. That is the rule a tied game already
follows in the winner engine, so the library has one answer to "this game
decided nothing" whatever the contest is scored on (Peter, 2026-11-27).

Like confidence points, this re-reads an engine's result rather than
replacing the engine: the engine has already checked the pick and worked
out the tiebreaker, and both pass through. It changes only who was right.
That makes the two compose: the engine, then the spread, then the stake.

What it refuses:

- An engine that pays more than 0 or 1 a pick (MMA's 2 and 5). A line
  handicaps a winner, not a method or a round.
- A sport whose result has its own detail (a fight). A line is a points
  margin, and a fight's two "scores" are not one.
- A line that is not a ``Decimal`` in whole or half points. A float line is
  a rounding bug waiting (-3.5 is exact in binary, -3.3 is not), and a
  quarter-point line is not one any book posts.

The line comes from whoever runs the contest, never from the pick: a member
who could send their own line would choose one that covers.
"""
import dataclasses
from decimal import Decimal

from .engines import BaseScoringEngine, MatchOutcome, ScoringResult
from .formats import _check_unit_result

_HALF = Decimal("0.5")


def check_line(home_spread) -> None:
    """
    Refuse a line scoring would refuse: TypeError if it is not a Decimal,
    ValueError if it is not finite or not a whole or half point. Whoever
    stores a line checks it with this, so a line that was accepted is one
    the scoring will take.
    """
    if isinstance(home_spread, bool) or not isinstance(home_spread, Decimal):
        raise TypeError(
            f"a line must be a Decimal, not {type(home_spread).__name__}"
        )
    if not home_spread.is_finite():
        raise ValueError(f"a line must be a number, not {home_spread}")
    if home_spread % _HALF != 0:
        raise ValueError(
            f"a line moves in half points; {home_spread} is not a whole or half point"
        )


def against_the_spread(
    result: ScoringResult,
    picked_team_id: int | None,
    outcome: MatchOutcome,
    home_spread: Decimal,
) -> ScoringResult:
    """
    The result of a pick on `picked_team_id` against the line `home_spread`.

    `result` is what the sport's engine said about the same pick; its
    tiebreaker is kept and its verdict is replaced. A cover pays 1, a miss
    0, a push 1 to everyone. A game with no result yet pays nothing.
    """
    _check_unit_result(result, "picks against the spread")
    if not isinstance(outcome, MatchOutcome):
        raise TypeError(f"outcome must be a MatchOutcome, not {type(outcome).__name__}")
    check_line(home_spread)
    if outcome.detail is not None:
        raise ValueError(
            "a line is a points margin; a sport whose result has its own "
            "detail has no margin to handicap"
        )
    BaseScoringEngine.check_in_match(picked_team_id, outcome, "the pick")

    if not outcome.is_scored:
        return dataclasses.replace(result, is_correct=False, points_earned=0)

    margin = outcome.home.score + home_spread - outcome.away.score
    if margin == 0:
        is_correct = True
    elif picked_team_id is None:
        is_correct = False
    else:
        covered = outcome.home.team_id if margin > 0 else outcome.away.team_id
        is_correct = picked_team_id == covered
    return dataclasses.replace(result, is_correct=is_correct, points_earned=int(is_correct))
