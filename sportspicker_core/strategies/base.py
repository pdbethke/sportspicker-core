"""
Normalization strategies.

A strategy never emits points. It emits relative weights for one round;
the aggregator normalises them into shares of that round's pot. This is
what keeps a contest's contribution equal to its budget no matter what
the strategy does internally.
"""
import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class RoundScore:
    membership_id: int
    raw_points: float
    wins: int
    tiebreaker_total: int | None = None


class NormalizationStrategy(abc.ABC):

    slug: str = "base"
    #: A baseline that bypasses budgets may never be a group's current strategy.
    is_baseline: bool = False

    def validate_config(self, params: dict) -> None:
        """Raise ValueError on invalid params. Called before saving a version."""
        min_participants = params.get("min_participants", 0)
        if not isinstance(min_participants, int) or min_participants < 0:
            raise ValueError("min_participants must be a non-negative integer")
        if params.get("min_participants_mode", "scale") not in ("scale", "void"):
            raise ValueError("min_participants_mode must be 'scale' or 'void'")
        drop_worst = params.get("drop_worst_n", 0)
        if not isinstance(drop_worst, int) or drop_worst < 0:
            raise ValueError("drop_worst_n must be a non-negative integer")
        # The knob is declared in the spec but deliberately not built yet.
        # Accepting it with a 200 and then scoring as if it were 0 would be
        # a silently wrong table, so reject it outright until it is real.
        if drop_worst:
            raise ValueError(
                "drop_worst_n is not yet implemented; only 0 is accepted"
            )

    @abc.abstractmethod
    def weigh_round(self, scores: list[RoundScore], params: dict) -> dict[int, float]:
        """membership_id -> relative weight for this round."""
