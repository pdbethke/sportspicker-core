"""
Contest budgets.

The rule is a decision, not a mechanism: contests without an explicit budget
each get the same amount, so adding a contest never devalues the ones already
in the group. Splitting a fixed total between them would do exactly that.

What that amount is belongs to the caller. The library used to ship one, and
a value a library picks on its callers' behalf is a value nobody chose; now
``unset_budget`` must be passed, and leaving it out is a TypeError.
"""
from dataclasses import dataclass
from decimal import Decimal

import pytest

import sportspicker_core
from sportspicker_core import resolve_budgets

UNSET = Decimal("1000")


@dataclass(frozen=True)
class Entry:
    contest_id: int
    budget: Decimal | int | str | None


def test_the_amount_for_an_unset_budget_must_be_given():
    with pytest.raises(TypeError, match="unset_budget"):
        resolve_budgets([Entry(1, None)])


def test_it_must_be_given_by_name():
    """A bare positional amount next to a list of entries reads as anything."""
    with pytest.raises(TypeError):
        resolve_budgets([Entry(1, None)], UNSET)


def test_the_library_no_longer_ships_a_budget_of_its_own():
    assert not hasattr(sportspicker_core, "DEFAULT_CONTEST_BUDGET")


def test_an_explicit_budget_is_used_as_given():
    assert resolve_budgets([Entry(1, Decimal("250"))], unset_budget=UNSET) == {1: Decimal("250")}


def test_a_missing_budget_takes_the_amount_the_caller_named():
    assert resolve_budgets([Entry(1, None)], unset_budget="750") == {1: Decimal("750")}


def test_the_named_amount_is_what_is_used_not_some_other_constant():
    """
    Two different amounts must give two different results; a function that
    ignored the argument would return the same for both.
    """
    low = resolve_budgets([Entry(1, None)], unset_budget=10)
    high = resolve_budgets([Entry(1, None)], unset_budget=20)

    assert low == {1: Decimal(10)}
    assert high == {1: Decimal(20)}


def test_a_repeated_contest_takes_its_last_budget_rather_than_their_sum():
    """
    Contest ids are keys, not quantities. Two entries for the same contest are
    a correction or a duplicate row, and the later one wins; adding them
    together would invent a budget nobody set and quietly break the guarantee
    the group rests on.
    """
    resolved = resolve_budgets([Entry(1, 100), Entry(1, 250)], unset_budget=UNSET)

    assert resolved == {1: Decimal(250)}


def test_contests_without_a_budget_are_worth_the_same_as_each_other():
    """Not a split of a fixed total — each gets the whole amount."""
    resolved = resolve_budgets([Entry(1, None), Entry(2, None), Entry(3, None)],
                               unset_budget=UNSET)

    assert set(resolved.values()) == {UNSET}


def test_adding_a_contest_does_not_devalue_the_existing_ones():
    """The property the meta-contest design exists to guarantee."""
    before = resolve_budgets([Entry(1, None), Entry(2, None)], unset_budget=UNSET)
    after = resolve_budgets([Entry(1, None), Entry(2, None), Entry(3, None)],
                            unset_budget=UNSET)

    assert after[1] == before[1]
    assert after[2] == before[2]


def test_explicit_and_unset_budgets_coexist():
    resolved = resolve_budgets([Entry(1, "500"), Entry(2, None)], unset_budget=UNSET)

    assert resolved == {1: Decimal(500), 2: UNSET}


def test_a_zero_budget_is_honoured_rather_than_treated_as_missing():
    """Zero is a deliberate choice — a contest that counts for nothing."""
    assert resolve_budgets([Entry(1, 0)], unset_budget=UNSET) == {1: Decimal(0)}


def test_an_empty_group_resolves_to_nothing():
    assert resolve_budgets([], unset_budget=UNSET) == {}


def test_budgets_are_exact_decimals_in_ten_thousandths():
    """The unit the awards are allocated in, so a budget divides without drift."""
    resolved = resolve_budgets([Entry(1, "1234.5"), Entry(2, None)], unset_budget=UNSET)

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
        resolve_budgets([Entry(1, 250.0)], unset_budget=UNSET)


def test_a_float_unset_budget_is_refused_too():
    with pytest.raises(TypeError, match="unset budget"):
        resolve_budgets([Entry(1, None)], unset_budget=1000.0)


def test_a_none_unset_budget_is_refused_even_when_every_contest_has_one():
    """Checked up front, so a group that later gains an unpriced contest cannot break."""
    with pytest.raises(TypeError, match="unset budget"):
        resolve_budgets([Entry(1, 5)], unset_budget=None)


def test_a_negative_budget_is_refused():
    with pytest.raises(ValueError, match="negative"):
        resolve_budgets([Entry(1, -5)], unset_budget=UNSET)
