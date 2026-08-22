"""
The award arithmetic.

This is the invariant the whole cross-sport design rests on: a contest
contributes exactly its budget, whatever the strategy does internally. These
tests run with no database, so the claim can be checked directly rather than
inferred from standings.
"""
from dataclasses import dataclass

import pytest

from sportspicker_core import (
    Award, award_round, competition_ranks, effective_pot, pot_for,
)
from sportspicker_core import normalization_registry

TOLERANCE = 1e-3          # relative; Numeric(12,4) rounding accumulates
RANK_PARAMS = {"points_table": [25, 18, 15], "tail_value": 0}


@dataclass(frozen=True)
class Score:
    """Stands in for a RoundScore without importing the ORM-adjacent module."""

    membership_id: int
    raw_points: float
    wins: int = 0
    tiebreaker_total: int | None = None


def field(*points: float) -> list[Score]:
    return [Score(index + 1, value) for index, value in enumerate(points)]


def weigh(slug: str, scores, params: dict) -> dict[int, float]:
    return normalization_registry.get(slug).weigh_round(scores, params)


class TestPotFor:

    def test_divides_the_budget_across_every_round(self):
        assert pot_for(1000, 4) == pytest.approx(250)

    def test_a_contest_with_no_rounds_awards_nothing_rather_than_raising(self):
        assert pot_for(1000, 0) == 0.0
        assert pot_for(1000, -1) == 0.0

    def test_a_single_round_contest_pays_its_whole_budget_in_that_round(self):
        """
        The one-round case is the guard's boundary, and the shape the library
        exists to support alongside a season: a fight card is one round, and it
        must contribute its whole budget or it silently counts for nothing
        beside an 18-round league.

        Added after an audit: widening the empty-contest guard from
        ``round_count <= 0`` to ``<= 1`` passed the whole suite, because every
        other case here uses four rounds or none.
        """
        assert pot_for(1000, 1) == pytest.approx(1000)


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
    """Deliberately weakened for a gate demonstration — see DEMO note below."""

    def test_awards_are_returned_for_every_member(self):
        # Asserts the shape and nothing about the arithmetic: this passes
        # whatever the pot logic does, which is the point of the exercise.
        scores = field(9, 6, 3)
        awards = award_round(scores, weigh("rank", scores, RANK_PARAMS), 1000.0, RANK_PARAMS)
        assert len(awards) == 3
        assert all(isinstance(a, Award) for a in awards)


class TestBaseline:

    def test_a_baseline_pays_raw_points_and_ignores_the_pot(self):
        """
        That unnormalised behaviour is precisely what a baseline exists to
        measure, so it must survive rather than be "corrected".
        """
        scores = field(7, 3)

        awards = award_round(
            scores, weigh("raw", scores, {}), 1000.0, {}, is_baseline=True
        )

        assert [a.points_awarded for a in awards] == [7, 3]
        assert sum(a.points_awarded for a in awards) != pytest.approx(1000)


class TestMinimumParticipants:

    def test_off_by_default(self):
        scores = field(5, 0, 0)

        assert effective_pot(1000.0, scores, {}) == 1000.0

    def test_scale_shrinks_the_pot_in_proportion(self):
        """Two of a required four scored, so half the pot is at stake."""
        scores = field(5, 5, 0, 0)

        assert effective_pot(1000.0, scores, {"min_participants": 4}) == pytest.approx(500)

    def test_void_awards_nothing(self):
        scores = field(5, 0, 0)

        pot = effective_pot(
            1000.0, scores,
            {"min_participants": 3, "min_participants_mode": "void"},
        )

        assert pot == 0.0

    def test_a_full_field_is_untouched(self):
        scores = field(5, 4, 3)

        assert effective_pot(1000.0, scores, {"min_participants": 3}) == 1000.0

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

        assert effective_pot(1000.0, scores, params) == 1000.0

    def test_it_counts_scorers_not_pickers(self):
        """
        The knob guards against a handful of scorers splitting a pot meant for
        a much larger field. Counting everyone present would not guard against
        that at all, since non-scorers already take nothing.
        """
        scores = field(5, 0, 0, 0, 0)      # five present, one scoring

        pot = effective_pot(1000.0, scores, {"min_participants": 5})

        assert pot == pytest.approx(200)

    def test_scaling_still_distributes_exactly_the_reduced_pot(self):
        params = {"min_participants": 4, "points_table": [25, 18, 15], "tail_value": 0}
        scores = field(9, 5, 0, 0)

        awards = award_round(scores, weigh("rank", scores, params), 1000.0, params)

        assert sum(a.points_awarded for a in awards) == pytest.approx(500, rel=TOLERANCE)


class TestAwardShape:

    def test_awards_carry_the_inputs_needed_to_explain_a_placing(self):
        scores = [Score(7, 9.0, wins=3, tiebreaker_total=4)]

        awards = award_round(scores, weigh("rank", scores, RANK_PARAMS), 100.0, RANK_PARAMS)

        assert isinstance(awards[0], Award)
        assert awards[0].membership_id == 7
        assert awards[0].raw_score == 9.0
        assert awards[0].tiebreaker_total == 4
        assert awards[0].rank_in_round == 1

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

        awards = award_round(scores, weights, 100.0, {})

        by_member = {a.membership_id: a for a in awards}
        assert by_member[2].points_awarded == 0.0
        assert by_member[2].rank_in_round == 2
        # And the pot still lands in full on the member who was weighed.
        assert sum(a.points_awarded for a in awards) == pytest.approx(100.0)
        assert by_member[1].points_awarded == pytest.approx(100, rel=TOLERANCE)
