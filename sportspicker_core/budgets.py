"""
How much each contest contributes to a group.

Pure, and separated because the rule is a decision rather than a mechanism:
every contest carries its own budget, an amount rather than a share of a fixed
total, so adding a contest never devalues the ones already in the group.
Splitting a fixed total between them would do exactly that, which is what the
meta-contest design exists to prevent.

There is no amount for a contest without a budget. The library does not pick
one, and a caller that kept a constant for it would only be picking one too;
a missing budget is refused, naming the contest.

Budgets are exact amounts (see ``awards.to_amount``): ``Decimal`` in
ten-thousandths of a point, given as an int, str or Decimal. A float budget is
refused rather than converted, because the decimal it was meant to be is
already lost and the pot arithmetic downstream is exact.
"""
from decimal import Decimal

from .awards import to_amount


def resolve_budgets(entries) -> dict[int, Decimal]:
    """
    Map contest id to budget.

    `entries` need only carry `contest_id` and `budget`. Every entry must have
    a budget: an exact non-negative amount, an int, str or Decimal with at
    most four places. A missing one raises ValueError naming the contest; a
    float raises TypeError naming it. A contest listed twice takes its last
    budget.
    """
    resolved = {}
    for entry in entries:
        if entry.budget is None:
            raise ValueError(
                f"contest {entry.contest_id} has no budget; every contest in a "
                f"group needs one (an int, str or Decimal)"
            )
        resolved[entry.contest_id] = to_amount(
            entry.budget, f"the budget of contest {entry.contest_id}"
        )
    return resolved
