"""
Contest budgets.

Every contest in a group carries its own budget, and the library uses it as
given. There is no amount for "no budget": a library that filled one in would
be choosing a value on its callers' behalf, and so would an application that
kept a constant for it. A missing budget is refused, naming the contest.

What makes groups fair is unchanged: budgets are amounts, not shares of a
fixed total, so adding a contest never devalues the ones already there.
"""
from dataclasses import dataclass
from decimal import Decimal

import pytest

import sportspicker_core
from sportspicker_core import resolve_budgets


@dataclass(frozen=True)
class Entry:
    contest_id: int
    budget: Decimal | int | str | None


def test_a_contest_without_a_budget_is_refused_by_name():
    with pytest.raises(ValueError, match="contest 7 has no budget"):
        resolve_budgets([Entry(1, 100), Entry(7, None)])


def test_there_is_no_amount_for_a_missing_budget_to_fall_back_to():
    assert not hasattr(sportspicker_core, "DEFAULT_CONTEST_BUDGET")
    with pytest.raises(TypeError):
        resolve_budgets([Entry(1, 100)], unset_budget=Decimal("1000"))


def test_an_explicit_budget_is_used_as_given():
    assert resolve_budgets([Entry(1, Decimal("250"))]) == {1: Decimal("250")}


def test_a_repeated_contest_takes_its_last_budget_rather_than_their_sum():
    """
    Contest ids are keys, not quantities. Two entries for the same contest are
    a correction or a duplicate row, and the later one wins; adding them
    together would invent a budget nobody set and quietly break the guarantee
    the group rests on.
    """
    assert resolve_budgets([Entry(1, 100), Entry(1, 250)]) == {1: Decimal(250)}


def test_adding_a_contest_does_not_devalue_the_existing_ones():
    """The property the meta-contest design exists to guarantee."""
    before = resolve_budgets([Entry(1, 1000), Entry(2, 500)])
    after = resolve_budgets([Entry(1, 1000), Entry(2, 500), Entry(3, 1000)])

    assert after[1] == before[1]
    assert after[2] == before[2]


def test_a_zero_budget_is_honoured_rather_than_treated_as_missing():
    """Zero is a deliberate choice: a contest that counts for nothing."""
    assert resolve_budgets([Entry(1, 0)]) == {1: Decimal(0)}


def test_an_empty_group_resolves_to_nothing():
    assert resolve_budgets([]) == {}


def test_budgets_are_exact_decimals_in_ten_thousandths():
    """The unit the awards are allocated in, so a budget divides without drift."""
    resolved = resolve_budgets([Entry(1, "1234.5"), Entry(2, 1000)])

    assert all(isinstance(v, Decimal) for v in resolved.values())
    assert resolved[1] == Decimal("1234.5000")
    assert resolved[1].as_tuple().exponent == -4
    assert resolved[2].as_tuple().exponent == -4


def test_a_float_budget_is_refused_rather_than_guessed_at():
    """
    A float budget has already lost the value somebody set; refusing it names
    the problem where it starts, instead of a ten-thousandth going missing in
    a championship later.
    """
    with pytest.raises(TypeError, match="budget"):
        resolve_budgets([Entry(1, 250.0)])


def test_a_negative_budget_is_refused():
    with pytest.raises(ValueError, match="negative"):
        resolve_budgets([Entry(1, -5)])
