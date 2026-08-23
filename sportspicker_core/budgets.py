"""
    Budgets are the contest's side of the guarantee: what it is worth in total,
    before any round divides it.

How much each contest contributes to a group.

Pure, and separated because the rule is a decision rather than a mechanism:
contests without an explicit budget each receive the same default, so they are
worth the same as one another and adding a contest never devalues the ones
already in the group. Splitting a fixed total between them would do exactly
that, which is what the meta-contest design exists to prevent.
"""

#: What a contest is worth when no budget was set for it.
DEFAULT_CONTEST_BUDGET = 1000.0


def resolve_budgets(entries, default: float = DEFAULT_CONTEST_BUDGET) -> dict[int, float]:
    """
    Map contest id to budget.

    `entries` need only carry `contest_id` and `budget`; an explicit budget
    wins, and None means the shared default.
    """
    resolved = {}
    for entry in entries:
        resolved[entry.contest_id] = (
            float(entry.budget) if entry.budget is not None else float(default)
        )
    return resolved
