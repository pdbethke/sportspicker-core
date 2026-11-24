"""
How much each contest contributes to a group.

Pure, and separated because the rule is a decision rather than a mechanism:
contests without an explicit budget each receive the same default, so they are
worth the same as one another and adding a contest never devalues the ones
already in the group. Splitting a fixed total between them would do exactly
that, which is what the meta-contest design exists to prevent.

Budgets are exact amounts (see ``awards.to_amount``): ``Decimal`` in
ten-thousandths of a point, given as an int, str or Decimal. A float budget is
refused rather than converted, because the decimal it was meant to be is
already lost and the pot arithmetic downstream is exact.
"""
from decimal import Decimal

from .awards import to_amount

#: What a contest is worth when no budget was set for it.
DEFAULT_CONTEST_BUDGET = Decimal("1000.0000")


def resolve_budgets(entries, default=DEFAULT_CONTEST_BUDGET) -> dict[int, Decimal]:
    """
    Map contest id to budget.

    `entries` need only carry `contest_id` and `budget`; an explicit budget
    wins, and None means the shared default. Every budget, including
    `default`, must be an exact non-negative amount: an int, str or Decimal
    with at most four places. A float raises TypeError naming the contest.
    """
    fallback = to_amount(default, "the default contest budget")
    resolved = {}
    for entry in entries:
        resolved[entry.contest_id] = (
            to_amount(entry.budget, f"the budget of contest {entry.contest_id}")
            if entry.budget is not None else fallback
        )
    return resolved
