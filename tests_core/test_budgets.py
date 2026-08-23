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


def test_a_defaulted_contest_is_worth_something():
    """
    The default has to be a real amount, and no other test here says so.

    Every assertion in this file compares against ``DEFAULT_CONTEST_BUDGET``
    rather than pinning what it is, so the whole suite passes just as happily
    with the default set to zero — at which point every contest nobody gave a
    budget contributes nothing to the championship, silently, and
    "adding a contest never devalues the others" becomes true in the emptiest
    possible way.

    Added after an audit, which set the default to zero and watched the suite
    agree.
    """
    assert DEFAULT_CONTEST_BUDGET > 0

    resolved = resolve_budgets([Entry(1, None)])

    assert resolved[1] > 0


def test_an_explicit_default_overrides_the_module_one():
    """
    ``default`` is a parameter, and nothing here ever passed it.

    Every other test in this file leans on the module constant, so the
    parameter could be ignored entirely — the function reading
    DEFAULT_CONTEST_BUDGET regardless of what a caller asked for — and the
    suite would not notice. A group that deliberately prices its contests
    differently would silently get the shipped default instead.

    Added after an audit ignored the argument and watched the suite agree.
    """
    custom = DEFAULT_CONTEST_BUDGET + 500.0

    resolved = resolve_budgets([Entry(1, None)], default=custom)

    assert resolved == {1: custom}


def test_a_repeated_contest_takes_its_last_budget_rather_than_their_sum():
    """
    Contest ids are keys, not quantities. Two entries for the same contest are
    a correction or a duplicate row, and the later one wins; adding them
    together would invent a budget nobody set and quietly break the guarantee
    the group rests on.
    """
    resolved = resolve_budgets([Entry(1, 100.0), Entry(1, 250.0)])

    assert resolved == {1: 250.0}


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
