"""
The award arithmetic — the pot, the shares, the ranks.

Pure by design, and deliberately so. This is the code the whole cross-sport
design rests on: a contest contributes exactly its budget, whatever the
strategy does internally. Keeping it free of the database means the invariant
can be checked directly, and adversarially, without standing anything up.

Nothing here imports SQLAlchemy or touches a session. The service supplies
already-loaded scores and persists what comes back.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Award:
    """One member's outcome for one round."""

    membership_id: int
    raw_score: float
    tiebreaker_total: int | None
    rank_in_round: int
    points_awarded: float


def competition_ranks(scores) -> dict[int, int]:
    """
    Rank members by raw score, ties sharing a rank.

    Competition ranking ("1224"): two members tied for first both place
    first and the next places third. Assigning them distinct ranks would
    contradict the tie-splitting the strategies deliberately perform.
    """
    ordered = sorted(scores, key=lambda s: s.raw_points, reverse=True)
    positions: dict[int, int] = {}
    rank = 0
    previous = None
    for index, score in enumerate(ordered):
        if score.raw_points != previous:
            rank = index + 1
            previous = score.raw_points
        positions[score.membership_id] = rank
    return positions


def effective_pot(pot: float, scores, params: dict) -> float:
    """
    Shrink or void the pot when too few members scored.

    ``min_participants`` counts members who *scored*, not members who merely
    played. Because weights are normalised, a non-scorer already takes nothing
    from the pot, so the risk this guards against is a tiny handful of scorers
    splitting a pot meant for a much larger field — two of forty, say.
    Counting pickers would not guard against that at all.
    """
    minimum = int(params.get("min_participants", 0))
    if not minimum:
        return pot

    scoring = len(scores)
    if scoring >= minimum:
        return pot

    mode = params.get("min_participants_mode", "scale")
    return 0.0 if mode == "void" else pot * (scoring / minimum)


def award_round(scores, weights: dict[int, float], pot: float, params: dict,
                is_baseline: bool = False) -> list[Award]:
    """
    Turn one round's scores and strategy weights into awards.

    Weights are relative; they are normalised into shares of the pot here, so
    a contest contributes exactly its budget no matter what scale a strategy
    emits. Two behaviours carry most of the subtlety:

    * When every weight is zero — an all-zero-scoring field under ``share`` or
      ``equal`` — nothing differentiates the members, so the pot is split
      evenly rather than silently going unawarded. A non-baseline strategy
      must always contribute its full (possibly scaled) pot to a non-empty
      field. That is the pot-exactness invariant.
    * A baseline strategy bypasses budget scaling entirely and pays raw
      points. That unnormalised behaviour is precisely what it exists to
      measure, so it must not be "fixed".
    """
    if not scores:
        return []

    total_weight = sum(weights.values())
    pot_after_minimum = effective_pot(pot, scores, params)
    positions = competition_ranks(scores)
    even_split = pot_after_minimum / len(scores)

    awards = []
    for score in scores:
        weight = weights.get(score.membership_id, 0.0)
        if is_baseline:
            points = score.raw_points
        elif total_weight > 0:
            points = (weight / total_weight) * pot_after_minimum
        else:
            points = even_split

        awards.append(Award(
            membership_id=score.membership_id,
            raw_score=score.raw_points,
            tiebreaker_total=score.tiebreaker_total,
            rank_in_round=positions[score.membership_id],
            points_awarded=points,
        ))
    return awards


def pot_for(budget: float, round_count: int) -> float:
    """
    A round's share of its contest's budget.

    The divisor is every round in the contest, not merely the played ones, so
    a round's value is knowable in advance and never repriced mid-season.
    Unplayed rounds simply award nothing, and the contest reaches its full
    budget once they have all been played.
    """
    if round_count <= 0:
        return 0.0
    return float(budget) / round_count
