"""
Pick formats: how a round weights the picks an engine has already scored.

An engine answers "was this pick right, and what is it worth on its own?".
A format answers a different question, asked across a member's whole slate
for a round. The one format here is **confidence points**, the common
pick'em rule: in a round of N games a member ranks each pick with a distinct
value from 1 to N, and a correct pick earns its value instead of a point.

It sits beside the engines rather than inside them on purpose. An engine
sees one pick and one match; the slate rule (distinct values, each within
1..N) is about every pick a member made in the round, which no engine is
given. Keeping the weight out of `PickInput` also leaves the input contract,
which has no defaults, unchanged for every existing caller.

Confidence applies only to an engine that pays 0 or 1. An engine that already
weights its picks (MMA pays 1, 2 or 5) is refused: multiplying a weight by a
confidence value is not a rule anyone plays, and doing it quietly would be
the kind of silently unfair table this library exists to rule out.

What a format does to a championship needs no rule here. Strategies read a
round's points as relative weights and normalise them into shares of the
pot, so a confidence round still pays exactly its pot.
"""
import dataclasses
from collections import Counter
from collections.abc import Iterable

from .engines import ScoringResult


def _check_int(value, what: str) -> None:
    # bool is an int subclass; True staked as 1 would be a caller's bug.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} must be an integer, not {type(value).__name__}")


def confidence_points(result: ScoringResult, confidence: int) -> ScoringResult:
    """
    The result of a pick staked at `confidence`: its value if it was right,
    nothing if it was wrong.

    `result` is what the sport's engine said. It must have paid 0 or 1 and
    agree with its own verdict; anything else raises, since it means a
    weighted engine or a broken result rather than a pick to score.
    Correctness and the tiebreaker pass through unchanged.
    """
    if not isinstance(result, ScoringResult):
        raise TypeError(f"result must be a ScoringResult, not {type(result).__name__}")
    _check_int(confidence, "a confidence value")
    if confidence < 1:
        raise ValueError(f"a confidence value must be at least 1, not {confidence}")
    if result.points_earned not in (0, 1):
        raise ValueError(
            f"confidence points need an engine that pays 0 or 1 per pick; this "
            f"result paid {result.points_earned}"
        )
    if result.points_earned != int(result.is_correct):
        raise ValueError(
            f"the result disagrees with itself: is_correct={result.is_correct} "
            f"but it paid {result.points_earned}"
        )
    return dataclasses.replace(
        result, points_earned=confidence if result.is_correct else 0
    )


def confidence_slate_error(values: Iterable[int], game_count: int) -> str | None:
    """
    Why a member's confidence values for a round are not a valid slate, or
    None if they are.

    Valid means each value is within 1..`game_count` and none is used twice.
    A partial slate is valid: a member may save as they go, and a game left
    unpicked scores nothing. Non-integers raise rather than being reported,
    since they are a caller's bug, not a member's choice.
    """
    _check_int(game_count, "the game count")
    if game_count < 0:
        raise ValueError(f"the game count cannot be negative, not {game_count}")
    values = list(values)
    for value in values:
        _check_int(value, "a confidence value")

    if len(values) > game_count:
        return (
            f"{len(values)} confidence values for a round of {game_count} "
            f"games; each game takes one"
        )
    outside = sorted({v for v in values if v < 1 or v > game_count})
    if outside:
        listed = ", ".join(str(v) for v in outside)
        return f"confidence values must be 1 to {game_count}; {listed} is outside that"
    repeated = sorted(v for v, n in Counter(values).items() if n > 1)
    if repeated:
        listed = ", ".join(str(v) for v in repeated)
        return f"each confidence value can be used once; {listed} is used more than once"
    return None
