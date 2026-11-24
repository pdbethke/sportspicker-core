"""
The award arithmetic — the pot, the shares, the ranks.

Pure by design, and deliberately so. This is the code the whole cross-sport
design rests on: a contest contributes exactly its budget, whatever the
strategy does internally. Keeping it free of the database means the invariant
can be checked directly, and adversarially, without standing anything up.

"Exactly" is meant literally. Every amount is a ``Decimal`` with four places,
and the arithmetic runs in whole ten-thousandths of a point (the unit the
application stores, ``Numeric(12,4)``). Wherever a division does not come out
even — a budget over its rounds, a pot over its field — the leftover units are
handed out one at a time by the largest-remainder method, with a fixed
tie-break, so the parts always add back up to the whole and the same inputs
always produce the same split. A float share would lose a ten-thousandth here
and there, and "within tolerance" is a statement that some of the budget may
go missing.

Nothing here imports SQLAlchemy or touches a session. The service supplies
already-loaded scores and persists what comes back.
"""
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction

#: Amounts are whole multiples of this: one ten-thousandth of a point.
UNITS_PER_POINT = 10_000


@dataclass(frozen=True)
class Award:
    """One member's outcome for one round."""

    membership_id: int
    raw_score: float
    tiebreaker_total: int | None
    rank_in_round: int
    points_awarded: Decimal


def to_amount(value, what: str) -> Decimal:
    """
    An exact, non-negative amount of points, as a Decimal with four places.

    Accepts an ``int``, a ``str`` or a ``Decimal``. A ``float`` is refused
    rather than converted: by the time a value is a float, the decimal its
    author meant is already gone (0.1 is not one tenth), and choosing which
    nearby decimal to substitute is a guess this library will not make on a
    caller's behalf. Pass a str or a Decimal. ``what`` names the value in the
    error, so the message says which input was wrong.
    """
    return _from_units(_to_units(value, what))


def _to_units(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise TypeError(
            f"{what} must be an int, str or Decimal amount, not "
            f"{type(value).__name__} {value!r}; a float has already lost its "
            f"decimal value, so pass it as a str or Decimal"
        )
    try:
        exact = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{what} is not a number: {value!r}") from None
    if not exact.is_finite():
        raise ValueError(f"{what} must be finite, not {value!r}")
    if exact < 0:
        raise ValueError(f"{what} must not be negative, not {value!r}")
    units = exact * UNITS_PER_POINT
    if units != units.to_integral_value():
        raise ValueError(
            f"{what} is {value!r}, finer than a ten-thousandth of a point; "
            f"amounts are exact in ten-thousandths, so round it before passing it"
        )
    return int(units)


def _from_units(units: int) -> Decimal:
    return Decimal(units).scaleb(-4)


def _apportion(units: int, weights: dict[int, Fraction]) -> dict[int, int]:
    """
    Split ``units`` whole units across ``weights`` exactly (largest remainder).

    Each key's exact quota is ``units * weight / total``. Every key first takes
    the floor of its quota; the units left over (always fewer than the number
    of keys) go one each to the keys whose quotas were cut the most. Keys with
    equal remainders are served in ascending order — the lowest id first, the
    same final tie-break the standings use — so the split is a pure function of
    its inputs, never of the order they arrived in.

    The parts always sum to ``units``. A zero weight's quota is zero with no
    remainder, so it never receives a leftover unit.
    """
    total = sum(weights.values())
    quotas = {key: units * weight / total for key, weight in weights.items()}
    shares = {key: math.floor(quota) for key, quota in quotas.items()}
    leftover = units - sum(shares.values())
    by_remainder = sorted(quotas, key=lambda key: (-(quotas[key] - shares[key]), key))
    for key in by_remainder[:leftover]:
        shares[key] += 1
    return shares


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


def effective_pot(pot, scores, params: dict) -> Decimal:
    """
    Shrink or void the pot when too few members scored.

    ``min_participants`` counts members who *scored*, not members who merely
    played. Because weights are normalised, a non-scorer already takes nothing
    from the pot, so the risk this guards against is a tiny handful of scorers
    splitting a pot meant for a much larger field — two of forty, say.
    Counting pickers would not guard against that at all.

    A scaled pot is ``pot * scoring / minimum`` rounded half-even to a
    ten-thousandth; that rounded amount is the round's pot from then on, and
    the field is paid exactly it.
    """
    units = _to_units(pot, "pot")
    minimum = int(params.get("min_participants", 0))
    if not minimum:
        return _from_units(units)

    scoring = sum(1 for s in scores if s.raw_points > 0)
    if scoring >= minimum:
        return _from_units(units)

    mode = params.get("min_participants_mode", "scale")
    if mode == "void":
        return _from_units(0)
    return _from_units(round(Fraction(units * scoring, minimum)))


def _weight(value, membership_id: int) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, Fraction)):
        raise TypeError(
            f"the weight for member {membership_id} must be a number, not "
            f"{type(value).__name__} {value!r}"
        )
    if isinstance(value, (float, Decimal)) and not math.isfinite(value):
        raise ValueError(f"the weight for member {membership_id} must be finite, not {value!r}")
    if value < 0:
        raise ValueError(
            f"the weight for member {membership_id} is negative ({value!r}); a "
            f"weight is a relative share of the pot and cannot take from it"
        )
    return Fraction(value)


def _validated_weights(scores, weights: dict) -> dict[int, Fraction]:
    ids = [s.membership_id for s in scores]
    if len(set(ids)) != len(ids):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"members {repeated} appear in the field more than once")
    strangers = sorted(set(weights) - set(ids))
    if strangers:
        raise ValueError(
            f"weights were given for members {strangers}, who are not in this "
            f"round's field; their share would be counted against the pot and "
            f"paid to nobody"
        )
    exact = {key: _weight(value, key) for key, value in weights.items()}
    return {member: exact.get(member, Fraction(0)) for member in ids}


def award_round(scores, weights: dict[int, float], pot, params: dict, *,
                is_baseline: bool) -> list[Award]:
    """
    Turn one round's scores and strategy weights into awards.

    Weights are relative; they are normalised into shares of the pot here, so
    a contest contributes exactly its budget no matter what scale a strategy
    emits. The awards sum to the round's effective pot exactly (see
    ``effective_pot``), apportioned in ten-thousandths by largest remainder.

    * ``weights`` may only name members of ``scores``; a weight for anyone else
      would count towards the total while being paid to nobody, so it is
      refused. A member the strategy did not weigh scores nothing. Weights must
      be finite and non-negative.
    * When every weight is zero — an all-zero-scoring field under ``share`` or
      ``equal`` — nothing differentiates the members, so the pot is split
      evenly rather than silently going unawarded. A non-baseline strategy
      must always contribute its full (possibly scaled) pot to a non-empty
      field. That is the pot-exactness invariant.
    * A baseline strategy bypasses budget scaling entirely and pays raw
      points. That unnormalised behaviour is precisely what it exists to
      measure, so it must not be "fixed". ``is_baseline`` has no default: a
      caller that forgot it would quietly normalise the baseline.
    """
    weights = _validated_weights(scores, weights)
    if not scores:
        _to_units(pot, "pot")
        return []

    positions = competition_ranks(scores)
    if is_baseline:
        paid = {s.membership_id: _raw_units(s) for s in scores}
    else:
        units = _to_units(effective_pot(pot, scores, params), "pot")
        if sum(weights.values()) == 0:
            weights = {member: Fraction(1) for member in weights}
        paid = _apportion(units, weights)

    return [
        Award(
            membership_id=score.membership_id,
            raw_score=score.raw_points,
            tiebreaker_total=score.tiebreaker_total,
            rank_in_round=positions[score.membership_id],
            points_awarded=_from_units(paid[score.membership_id]),
        )
        for score in scores
    ]


def _raw_units(score) -> int:
    """A baseline pays raw points, which must still be an exact amount."""
    quota = Fraction(score.raw_points) * UNITS_PER_POINT
    if quota.denominator != 1:
        raise ValueError(
            f"member {score.membership_id} has raw points {score.raw_points!r}, "
            f"finer than a ten-thousandth of a point"
        )
    return int(quota)


def round_pots(budget, round_count: int) -> tuple[Decimal, ...]:
    """
    Every round's share of its contest's budget, in round order.

    The divisor is every round in the contest, not merely the played ones, so
    a round's value is knowable in advance and never repriced mid-season.
    Unplayed rounds simply award nothing, and the contest reaches its full
    budget once they have all been played.

    The pots sum to the budget exactly. When the budget does not divide evenly
    in ten-thousandths, the leftover units go one each to the earliest rounds,
    so no two pots differ by more than a ten-thousandth and the split is
    fixed by the round's position alone.

    Both boundaries carry weight, and neither is an edge case here. A contest
    of one round pays its whole budget in that round: a fight card sits beside
    an eighteen-round season precisely so it can, and a guard that swallowed it
    would make the shorter contest count for nothing. A contest of no rounds
    pays nothing at all rather than dividing by zero. A negative round count
    describes no contest, and is refused.

    ``budget`` follows ``to_amount``: an int, str or Decimal, never a float.
    """
    units = _to_units(budget, "budget")
    if round_count < 0:
        raise ValueError(f"round_count must not be negative, not {round_count}")
    if round_count == 0:
        return ()
    shares = _apportion(units, {index: Fraction(1) for index in range(round_count)})
    return tuple(_from_units(shares[index]) for index in range(round_count))


def pot_for(budget, round_count: int, round_index: int) -> Decimal:
    """
    One round's pot: ``round_pots(budget, round_count)[round_index]``.

    ``round_index`` is the round's zero-based position among the contest's
    counted rounds, in a fixed order the caller chooses and keeps; it decides
    which rounds carry a leftover ten-thousandth. An index outside the
    contest is refused rather than priced at nothing.
    """
    if not 0 <= round_index < max(round_count, 0):
        raise ValueError(
            f"round_index {round_index} is outside a contest of {round_count} rounds"
        )
    return round_pots(budget, round_count)[round_index]
