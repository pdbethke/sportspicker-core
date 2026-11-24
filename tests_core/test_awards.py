"""
The award arithmetic.

This is the invariant the whole cross-sport design rests on: a contest
contributes exactly its budget, whatever the strategy does internally. These
tests run with no database, so the claim can be checked directly rather than
inferred from standings.

"Exactly" means exactly. Amounts are ``Decimal`` in ten-thousandths, the unit
the application stores, and every sum below is compared with ``==``. There is
no tolerance anywhere in this file, and there must never be one: a tolerance
is a statement that some of the budget may go missing.
"""
import random
from dataclasses import dataclass
from decimal import Decimal

import pytest

from sportspicker_core import (
    Award, award_round, competition_ranks, effective_pot, pot_for, round_pots,
    to_amount,
)
from sportspicker_core import normalization_registry

RANK_PARAMS = {"points_table": [25, 18, 15], "tail_value": 0}
D = Decimal


@dataclass(frozen=True)
class Score:
    """Stands in for a RoundScore: award_round reads only these attributes."""

    membership_id: int
    raw_points: float
    wins: int = 0
    tiebreaker_total: int | None = None


def field(*points: float) -> list[Score]:
    return [Score(index + 1, value) for index, value in enumerate(points)]


def weigh(slug: str, scores, params: dict) -> dict[int, float]:
    return normalization_registry.get(slug).weigh_round(scores, params)


def total(awards) -> Decimal:
    return sum((a.points_awarded for a in awards), D(0))


class TestAmounts:
    """What counts as an amount of points: exact, in ten-thousandths."""

    def test_ints_strings_and_decimals_are_accepted(self):
        assert to_amount(1000, "budget") == D("1000.0000")
        assert to_amount("12.5", "budget") == D("12.5000")
        assert to_amount(D("0.0001"), "budget") == D("0.0001")

    def test_an_amount_always_carries_four_places(self):
        assert to_amount(7, "pot").as_tuple().exponent == -4

    def test_a_float_is_refused_rather_than_guessed_at(self):
        """
        A float has already lost the value its author typed: 0.1 is not one
        tenth. Converting it would decide, silently, which nearby decimal they
        meant, so the caller is told to pass a str or a Decimal instead.
        """
        with pytest.raises(TypeError, match="str or Decimal"):
            to_amount(1000.0, "budget")

    def test_a_bool_is_not_a_number_of_points(self):
        with pytest.raises(TypeError):
            to_amount(True, "budget")

    def test_more_precision_than_a_ten_thousandth_is_refused(self):
        """Rounding it away would make 'exactly its budget' a different number."""
        with pytest.raises(ValueError, match="ten-thousandth"):
            to_amount("0.00005", "budget")

    def test_a_negative_amount_is_refused(self):
        with pytest.raises(ValueError, match="negative"):
            to_amount(-1, "budget")

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_a_non_finite_amount_is_refused(self, value):
        with pytest.raises(ValueError):
            to_amount(value, "budget")

    def test_the_error_names_what_was_wrong(self):
        with pytest.raises(TypeError, match="budget"):
            to_amount(1.5, "budget")


class TestRoundPots:

    def test_divides_the_budget_across_every_round(self):
        assert round_pots(1000, 4) == (D("250"),) * 4

    def test_a_budget_that_does_not_divide_evenly_still_sums_to_itself(self):
        """
        1000 over three rounds is 333.3333... A per-round float drops a
        ten-thousandth of a point somewhere in the contest. The remainder is
        given out a ten-thousandth at a time, to the earliest rounds, so the
        rounds add back up to the budget to the last place.
        """
        pots = round_pots(1000, 3)

        assert pots == (D("333.3334"), D("333.3333"), D("333.3333"))
        assert sum(pots) == D(1000)

    def test_a_budget_smaller_than_one_unit_per_round(self):
        assert round_pots(D("0.0002"), 3) == (D("0.0001"), D("0.0001"), D("0"))

    def test_a_contest_with_no_rounds_awards_nothing_rather_than_raising(self):
        assert round_pots(1000, 0) == ()

    def test_a_negative_round_count_is_refused(self):
        """There is no such contest; quietly paying nothing would hide the bug upstream."""
        with pytest.raises(ValueError, match="round_count"):
            round_pots(1000, -1)

    def test_a_single_round_contest_pays_its_whole_budget_in_that_round(self):
        """
        The one-round case is the guard's boundary, and the shape the library
        exists to support alongside a season: a fight card is one round, and it
        must contribute its whole budget or it silently counts for nothing
        beside an 18-round league.

        Added after an audit: widening the empty-contest guard from
        ``round_count <= 0`` to ``<= 1`` passed the whole suite, because every
        other case here used four rounds or none.
        """
        assert round_pots(1000, 1) == (D(1000),)

    def test_a_float_budget_is_refused(self):
        with pytest.raises(TypeError):
            round_pots(1000.0, 4)

    def test_round_pots_always_sum_exactly_to_the_budget(self):
        """Property: many budgets and round counts, seeded so a failure replays."""
        rng = random.Random(20261124)
        for _ in range(1000):
            budget = D(rng.randrange(0, 10**9)).scaleb(-4)
            rounds = rng.randrange(1, 60)

            pots = round_pots(budget, rounds)

            assert len(pots) == rounds
            assert sum(pots) == budget, (budget, rounds)
            assert max(pots) - min(pots) <= D("0.0001")


class TestPotFor:

    def test_is_that_round_of_round_pots(self):
        assert [pot_for(1000, 3, i) for i in range(3)] == list(round_pots(1000, 3))

    def test_a_single_round_contest_pays_its_whole_budget_in_that_round(self):
        assert pot_for(1000, 1, 0) == D(1000)

    def test_a_round_outside_the_contest_is_refused(self):
        with pytest.raises(ValueError, match="round_index"):
            pot_for(1000, 3, 3)
        with pytest.raises(ValueError, match="round_index"):
            pot_for(1000, 3, -1)

    def test_a_contest_with_no_rounds_has_no_round_to_price(self):
        with pytest.raises(ValueError, match="round_index"):
            pot_for(1000, 0, 0)


class TestCompetitionRanks:

    def test_distinct_scores_rank_in_order(self):
        assert competition_ranks(field(9, 5, 1)) == {1: 1, 2: 2, 3: 3}

    def test_a_tie_shares_a_rank_and_skips_the_next(self):
        """Competition ranking: 1-2-2-4, never 1-2-3-4 for tied members."""
        assert competition_ranks(field(9, 5, 5, 1)) == {1: 1, 2: 2, 3: 2, 4: 4}

    def test_a_three_way_tie_at_the_top(self):
        assert competition_ranks(field(7, 7, 7, 2)) == {1: 1, 2: 1, 3: 1, 4: 4}

    def test_everyone_tied_shares_first(self):
        assert competition_ranks(field(3, 3, 3)) == {1: 1, 2: 1, 3: 1}


class TestPotExactness:
    """The core invariant, checked directly rather than through standings."""

    @pytest.mark.parametrize("slug,params", [
        ("rank", RANK_PARAMS),
        ("share", {}),
        ("equal", {}),
    ])
    def test_a_contest_contributes_exactly_its_pot(self, slug, params):
        scores = field(9, 5, 1)

        awards = award_round(scores, weigh(slug, scores, params), 1000, params,
                             is_baseline=False)

        assert total(awards) == D(1000)

    @pytest.mark.parametrize("slug,params", [
        ("rank", RANK_PARAMS),
        ("share", {}),
        ("equal", {}),
    ])
    def test_an_all_zero_field_still_receives_the_whole_pot(self, slug, params):
        """
        Nothing separates the members, so the pot is split evenly rather than
        silently going unawarded. `share` and `equal` emit all-zero weights
        here; `rank` ties everyone. All three must still pay out in full.
        """
        scores = field(0, 0, 0)

        awards = award_round(scores, weigh(slug, scores, params), 900, params,
                             is_baseline=False)

        assert total(awards) == D(900)
        assert all(a.points_awarded == D(300) for a in awards)

    def test_an_even_split_that_does_not_divide_still_pays_the_whole_pot(self):
        """
        Three members, nobody scored, a pot of 1000: a third each is not
        representable. The odd ten-thousandth goes to one member — the lowest
        membership id, the same final tiebreak the standings use — rather than
        vanishing.
        """
        scores = field(0, 0, 0)

        awards = award_round(scores, weigh("equal", scores, {}), 1000, {},
                             is_baseline=False)

        assert [a.points_awarded for a in awards] == [
            D("333.3334"), D("333.3333"), D("333.3333"),
        ]
        assert total(awards) == D(1000)

    def test_shares_that_do_not_divide_still_pay_the_whole_pot(self):
        scores = field(1, 1, 1, 4)

        awards = award_round(scores, weigh("share", scores, {}), 1000, {},
                             is_baseline=False)

        assert total(awards) == D(1000)

    def test_the_leftover_goes_to_the_largest_remainder_first(self):
        """
        Weights 1 and 2 over ten units: quotas 3.33 and 6.67 units. Flooring
        gives 3 and 6, one unit left, and it belongs to the member whose quota
        was cut the most — not to whoever happens to have the lowest id.
        """
        scores = field(1, 2)

        awards = award_round(scores, {1: 1, 2: 2}, D("0.0010"), {},
                             is_baseline=False)

        assert [a.points_awarded for a in awards] == [D("0.0003"), D("0.0007")]

    def test_equal_remainders_break_to_the_lowest_membership_id(self):
        scores = [Score(30, 0), Score(10, 0), Score(20, 0)]

        awards = award_round(scores, {30: 1, 10: 1, 20: 1}, D("0.0002"), {},
                             is_baseline=False)

        by_member = {a.membership_id: a.points_awarded for a in awards}
        assert by_member == {10: D("0.0001"), 20: D("0.0001"), 30: D("0")}

    def test_the_result_does_not_depend_on_the_order_scores_arrive_in(self):
        """The same round must award the same points however a query ordered it."""
        scores = field(5, 5, 5, 2, 2, 0, 9)
        weights = weigh("share", scores, {})

        forward = award_round(scores, weights, 1000, {}, is_baseline=False)
        backward = award_round(list(reversed(scores)), weights, 1000, {},
                               is_baseline=False)

        assert ({a.membership_id: a.points_awarded for a in forward}
                == {a.membership_id: a.points_awarded for a in backward})

    def test_every_award_is_in_ten_thousandths(self):
        scores = field(9, 5, 1)

        awards = award_round(scores, weigh("share", scores, {}), 1000, {},
                             is_baseline=False)

        assert all(a.points_awarded.as_tuple().exponent == -4 for a in awards)

    def test_holds_for_a_large_field(self):
        scores = field(*range(50))
        params = {"points_table": list(range(50, 0, -1)), "tail_value": 0}

        awards = award_round(scores, weigh("rank", scores, params), 1000, params,
                             is_baseline=False)

        assert total(awards) == D(1000)

    def test_a_single_member_takes_the_whole_pot(self):
        scores = field(4)

        awards = award_round(scores, weigh("rank", scores, RANK_PARAMS), 500,
                             RANK_PARAMS, is_baseline=False)

        assert awards[0].points_awarded == D(500)

    def test_an_empty_field_awards_nothing_and_does_not_divide_by_zero(self):
        assert award_round([], {}, 1000, {}, is_baseline=False) == []

    def test_any_field_any_strategy_pays_exactly_its_pot(self):
        """
        Property: random fields, budgets, round counts and strategies, seeded
        so a failure replays. Each round pays exactly its (possibly scaled)
        pot, and with no minimum the rounds of a contest pay exactly its
        budget.
        """
        rng = random.Random(1124)
        for _ in range(250):
            size = rng.randrange(1, 40)
            scores = [Score(rng.randrange(1, 10**6) * 64 + i, rng.choice((0, 0, 1, 2, 3, 7.5, 12)))
                      for i in range(size)]
            slug = rng.choice(("rank", "share", "equal"))
            params = {}
            if slug == "rank":
                params = {"points_table": [rng.randrange(0, 30) for _ in range(rng.randrange(1, 8))],
                          "tail_value": rng.choice((0, 1, 2.5))}
            if rng.random() < 0.3:
                params["min_participants"] = rng.randrange(1, 12)
                params["min_participants_mode"] = rng.choice(("scale", "void"))
            budget = D(rng.randrange(0, 10**8)).scaleb(-4)
            rounds = rng.randrange(1, 20)
            weights = weigh(slug, scores, params)

            paid = D(0)
            for pot in round_pots(budget, rounds):
                awards = award_round(scores, weights, pot, params, is_baseline=False)
                expected = effective_pot(pot, scores, params)
                assert total(awards) == expected, (slug, params, pot)
                assert all(a.points_awarded >= 0 for a in awards)
                paid += total(awards)

            if "min_participants" not in params:
                assert paid == budget, (slug, params, budget, rounds)


class TestWeightsAreValidated:
    """
    Weights that cannot be shares are refused, not quietly reinterpreted.
    Each of these used to produce a plausible-looking but short or negative
    pot.
    """

    def test_a_weight_for_someone_outside_the_field_is_refused(self):
        """
        It used to count towards the total while being paid to nobody, so
        the field received less than the pot with no error at all.
        """
        scores = field(9, 4)

        with pytest.raises(ValueError, match="99"):
            award_round(scores, {1: 1, 2: 1, 99: 2}, 100, {}, is_baseline=False)

    def test_a_negative_weight_is_refused(self):
        scores = field(9, 4)

        with pytest.raises(ValueError, match="negative"):
            award_round(scores, {1: 3, 2: -1}, 100, {}, is_baseline=False)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), "3", None, True])
    def test_a_weight_that_is_not_a_finite_number_is_refused(self, bad):
        scores = field(9, 4)

        with pytest.raises((TypeError, ValueError)):
            award_round(scores, {1: 3, 2: bad}, 100, {}, is_baseline=False)

    def test_a_member_appearing_twice_in_the_field_is_refused(self):
        scores = [Score(1, 5), Score(1, 3)]

        with pytest.raises(ValueError, match="more than once"):
            award_round(scores, {1: 1}, 100, {}, is_baseline=False)

    def test_a_float_pot_is_refused(self):
        with pytest.raises(TypeError):
            award_round(field(1), {1: 1}, 100.0, {}, is_baseline=False)

    def test_whether_the_strategy_is_a_baseline_must_be_said(self):
        """
        Leaving it to a default would let a caller forget, and the raw
        baseline would then be normalised into a pot it exists to ignore.
        """
        with pytest.raises(TypeError):
            award_round(field(1), {1: 1}, 100, {})


class TestBaseline:

    def test_a_baseline_pays_raw_points_and_ignores_the_pot(self):
        """
        That unnormalised behaviour is precisely what a baseline exists to
        measure, so it must survive rather than be "corrected".
        """
        scores = field(7, 3)

        awards = award_round(
            scores, weigh("raw", scores, {}), 1000, {}, is_baseline=True
        )

        assert [a.points_awarded for a in awards] == [D(7), D(3)]
        assert total(awards) != D(1000)


class TestMinimumParticipants:

    def test_off_by_default(self):
        scores = field(5, 0, 0)

        assert effective_pot(1000, scores, {}) == D(1000)

    def test_scale_shrinks_the_pot_in_proportion(self):
        """Two of a required four scored, so half the pot is at stake."""
        scores = field(5, 5, 0, 0)

        assert effective_pot(1000, scores, {"min_participants": 4}) == D(500)

    def test_a_scaled_pot_is_itself_an_exact_amount(self):
        """One of three: a third of 1000, rounded half-even to a ten-thousandth."""
        assert effective_pot(1000, field(5, 0, 0), {"min_participants": 3}) == D("333.3333")
        assert effective_pot(1000, field(5, 5, 0), {"min_participants": 3}) == D("666.6667")

    def test_void_awards_nothing(self):
        scores = field(5, 0, 0)

        pot = effective_pot(
            1000, scores,
            {"min_participants": 3, "min_participants_mode": "void"},
        )

        assert pot == D(0)

    def test_a_full_field_is_untouched(self):
        scores = field(5, 4, 3)

        assert effective_pot(1000, scores, {"min_participants": 3}) == D(1000)

    def test_a_field_exactly_on_the_minimum_is_met_not_missed(self):
        """
        The minimum is a floor to reach, not a bar to clear: a field landing
        exactly on it has met the requirement and keeps the whole pot.

        This has to be asserted in VOID mode. The scale-mode case above also
        sits exactly on the minimum, but scaling by ``scoring / minimum`` is
        1.0 there, so it returns the full pot whether the comparison is ``>=``
        or ``>`` — it reads as coverage of this boundary while discriminating
        nothing. Voiding is where the two answers diverge: the whole pot, or
        none of it.

        Added after an audit, which flipped that comparison and watched the
        suite pass.
        """
        scores = field(5, 4, 3)
        params = {"min_participants": 3, "min_participants_mode": "void"}

        assert effective_pot(1000, scores, params) == D(1000)

    def test_it_counts_scorers_not_pickers(self):
        """
        The knob guards against a handful of scorers splitting a pot meant for
        a much larger field. Counting everyone present would not guard against
        that at all, since non-scorers already take nothing.
        """
        scores = field(5, 0, 0, 0, 0)      # five present, one scoring

        pot = effective_pot(1000, scores, {"min_participants": 5})

        assert pot == D(200)

    def test_scaling_still_distributes_exactly_the_reduced_pot(self):
        params = {"min_participants": 4, "points_table": [25, 18, 15], "tail_value": 0}
        scores = field(9, 5, 0, 0)

        awards = award_round(scores, weigh("rank", scores, params), 1000, params,
                             is_baseline=False)

        assert total(awards) == D(500)


class TestAwardShape:

    def test_awards_carry_the_inputs_needed_to_explain_a_placing(self):
        scores = [Score(7, 9.0, wins=3, tiebreaker_total=4)]

        awards = award_round(scores, weigh("rank", scores, RANK_PARAMS), 100,
                             RANK_PARAMS, is_baseline=False)

        assert isinstance(awards[0], Award)
        assert awards[0].membership_id == 7
        assert awards[0].raw_score == 9.0
        assert awards[0].tiebreaker_total == 4
        assert awards[0].rank_in_round == 1
        assert isinstance(awards[0].points_awarded, Decimal)

    def test_a_member_missing_from_the_weights_scores_nothing_but_stays_ranked(self):
        """
        An enrolled member the strategy did not weigh still appears, on zero
        points, in their rightful place.

        The second member must SCORE for this to prove anything. It used to
        read ``field(9, 0)``, and an audit's critic pointed out the assertion
        could not fail: a member on zero raw points takes nothing from a
        normalised pot regardless of whether absent-from-weights is handled at
        all. Giving them four points makes the claim real — they earned
        something, the strategy left them unweighted, and the award must still
        be zero while the ranking still counts them.
        """
        scores = field(9, 4)
        weights = {1: 25.0}            # the second member has no weight at all

        awards = award_round(scores, weights, 100, {}, is_baseline=False)

        by_member = {a.membership_id: a for a in awards}
        assert by_member[2].points_awarded == D(0)
        assert by_member[2].rank_in_round == 2
        # And the pot still lands in full on the member who was weighed.
        assert total(awards) == D(100)
        assert by_member[1].points_awarded == D(100)
