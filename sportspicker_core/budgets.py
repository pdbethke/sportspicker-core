"""
How much each contest contributes to a group.

Pure, and separated because the rule is a decision rather than a mechanism:
contests without an explicit budget each receive the same amount, so they are
worth the same as one another and adding a contest never devalues the ones
already in the group. Splitting a fixed total between them would do exactly
that, which is what the meta-contest design exists to prevent.

What that amount is, is the caller's to say (``unset_budget``). The library
does not pick one.

Budgets are exact amounts (see ``awards.to_amount``): ``Decimal`` in
ten-thousandths of a point, given as an int, str or Decimal. A float budget is
refused rather than converted, because the decimal it was meant to be is
already lost and the pot arithmetic downstream is exact.
"""
from decimal import Decimal

from .awards import to_amount


def resolve_budgets(entries, *, unset_budget) -> dict[int, Decimal]:
    """
    Map contest id to budget.

    `entries` need only carry `contest_id` and `budget`; an explicit budget
    wins, and None means `unset_budget`, the amount the caller gives every
    contest that has none. Every budget, including `unset_budget`, must be an
    exact non-negative amount: an int, str or Decimal with at most four
    places. A float raises TypeError naming the contest. `unset_budget` is
    checked even when every entry has a budget, so a group cannot work until
    the day it gains one that does not.
    """
    fallback = to_amount(unset_budget, "the unset budget")
    resolved = {}
    for entry in entries:
        resolved[entry.contest_id] = (
            to_amount(entry.budget, f"the budget of contest {entry.contest_id}")
            if entry.budget is not None else fallback
        )
    return resolved
