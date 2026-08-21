"""
Contest budgets.

The rule is a decision, not a mechanism: contests without an explicit budget
each get the same default, so adding a contest never devalues the ones already
in the group. Splitting a fixed total between them would do exactly that.
"""
from dataclasses import dataclass

from sportspicker_core import (
    DEFAULT_CONTEST_BUDGET, resolve_budgets,
)


@dataclass(frozen=True)
class Entry:
    contest_id: int
    budget: float | None


def test_an_explicit_budget_is_used_as_given():
    assert resolve_budgets([Entry(1, 250.0)]) == {1: 250.0}


def test_a_missing_budget_falls_back_to_the_default():
    assert resolve_budgets([Entry(1, None)]) == {1: DEFAULT_CONTEST_BUDGET}


def test_implicit_contests_are_worth_the_same_as_each_other():
    """Not a split of a fixed total — each gets the whole default."""
    resolved = resolve_budgets([Entry(1, None), Entry(2, None), Entry(3, None)])

    assert set(resolved.values()) == {DEFAULT_CONTEST_BUDGET}


def test_adding_a_contest_does_not_devalue_the_existing_ones():
    """The property the meta-contest design exists to guarantee."""
    before = resolve_budgets([Entry(1, None), Entry(2, None)])
    after = resolve_budgets([Entry(1, None), Entry(2, None), Entry(3, None)])

    assert after[1] == before[1]
    assert after[2] == before[2]


def test_explicit_and_implicit_budgets_coexist():
    resolved = resolve_budgets([Entry(1, 500.0), Entry(2, None)])

    assert resolved == {1: 500.0, 2: DEFAULT_CONTEST_BUDGET}


def test_a_zero_budget_is_honoured_rather_than_treated_as_missing():
    """Zero is a deliberate choice — a contest that counts for nothing."""
    assert resolve_budgets([Entry(1, 0.0)]) == {1: 0.0}


def test_an_empty_group_resolves_to_nothing():
    assert resolve_budgets([]) == {}
