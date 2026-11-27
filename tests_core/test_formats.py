"""
Confidence points: a member ranks a round's picks 1..N and a correct pick
earns its rank.

Two things are defended here. The arithmetic: a right pick pays exactly its
value, a wrong one nothing, and an engine that already weights its picks is
refused rather than multiplied. And the slate: the values a member stakes on
a round are distinct and each within 1..N, because a duplicated 16 is two
bets on the same stake and a 17 in a 16-game round is a stake nobody else
could make.
"""
import pytest

from sportspicker_core import ScoringResult, confidence_points, confidence_slate_error


def _result(correct: bool, points: int, tiebreaker=None) -> ScoringResult:
    return ScoringResult(is_correct=correct, points_earned=points, tiebreaker_score=tiebreaker)


class TestConfidencePoints:
    def test_a_correct_pick_earns_its_value(self):
        assert confidence_points(_result(True, 1), 7).points_earned == 7

    def test_a_wrong_pick_earns_nothing_whatever_its_value(self):
        assert confidence_points(_result(False, 0), 16).points_earned == 0

    def test_the_lowest_value_still_pays_one(self):
        assert confidence_points(_result(True, 1), 1).points_earned == 1

    def test_correctness_and_tiebreaker_pass_through(self):
        weighed = confidence_points(_result(True, 1, tiebreaker=4), 3)
        assert weighed.is_correct is True
        assert weighed.tiebreaker_score == 4

    def test_a_wrong_pick_keeps_its_tiebreaker(self):
        assert confidence_points(_result(False, 0, tiebreaker=9), 3).tiebreaker_score == 9

    def test_the_input_result_is_not_changed(self):
        original = _result(True, 1)
        confidence_points(original, 5)
        assert original.points_earned == 1

    @pytest.mark.parametrize("paid", [2, 5, -1])
    def test_an_engine_that_weights_its_picks_is_refused(self, paid):
        # MMA pays 1, 2 or 5. Multiplying that by a confidence value is not a
        # rule anyone plays; it must fail loudly, not score.
        with pytest.raises(ValueError, match="0 or 1"):
            confidence_points(_result(True, paid), 3)

    def test_a_correct_result_that_paid_nothing_is_refused(self):
        with pytest.raises(ValueError, match="disagrees"):
            confidence_points(_result(True, 0), 3)

    def test_a_wrong_result_that_paid_is_refused(self):
        with pytest.raises(ValueError, match="disagrees"):
            confidence_points(_result(False, 1), 3)

    @pytest.mark.parametrize("value", [0, -2])
    def test_a_value_below_one_is_refused(self, value):
        with pytest.raises(ValueError, match="at least 1"):
            confidence_points(_result(True, 1), value)

    @pytest.mark.parametrize("value", [True, 2.0, "3", None])
    def test_a_value_that_is_not_an_integer_is_refused(self, value):
        with pytest.raises(TypeError):
            confidence_points(_result(True, 1), value)

    def test_a_result_that_is_not_a_scoring_result_is_refused(self):
        with pytest.raises(TypeError):
            confidence_points({"is_correct": True, "points_earned": 1}, 3)


class TestConfidenceSlate:
    def test_a_full_slate_is_valid(self):
        assert confidence_slate_error([3, 1, 2], 3) is None

    def test_a_partial_slate_is_valid(self):
        # A member may save as they go; an unpicked game simply scores nothing.
        assert confidence_slate_error([16, 15], 16) is None

    def test_an_empty_slate_is_valid(self):
        assert confidence_slate_error([], 16) is None

    def test_a_duplicate_is_named(self):
        error = confidence_slate_error([4, 2, 4], 5)
        assert error is not None and "4" in error and "more than once" in error

    def test_a_value_above_the_game_count_is_named(self):
        error = confidence_slate_error([1, 17], 16)
        assert error is not None and "17" in error and "1 to 16" in error

    def test_the_game_count_itself_is_allowed(self):
        assert confidence_slate_error([16], 16) is None

    def test_zero_is_refused(self):
        error = confidence_slate_error([0, 1], 4)
        assert error is not None and "0" in error

    def test_a_negative_value_is_refused(self):
        assert confidence_slate_error([-1], 4) is not None

    def test_more_values_than_games_is_refused(self):
        # Implied by distinct-and-in-range, but said on its own so the message
        # is about the round, not one value.
        assert confidence_slate_error([1, 2, 3], 2) is not None

    @pytest.mark.parametrize("values", [[1, True], [1, 2.0], [None]])
    def test_a_value_that_is_not_an_integer_is_refused(self, values):
        with pytest.raises(TypeError):
            confidence_slate_error(values, 4)

    @pytest.mark.parametrize("count", [-1, True, 2.5])
    def test_a_bad_game_count_is_refused(self, count):
        with pytest.raises((TypeError, ValueError)):
            confidence_slate_error([1], count)


class TestTheGuaranteeHolds:
    """
    A round scored with confidence points still pays exactly its pot.

    Nothing in the format touches awards; this pins that it never needs to.
    Confidence totals run to 136 in a 16-game round where straight scoring
    tops out at 16, and every live strategy must still normalise that into
    the same pot.
    """

    PARAMS = {
        "rank": {"points_table": [25, 18, 15], "tail_value": 0},
        "share": {},
        "equal": {},
    }

    @pytest.mark.parametrize("slug", ["rank", "share", "equal"])
    def test_a_confidence_round_pays_exactly_its_pot(self, slug):
        from decimal import Decimal
        from sportspicker_core import RoundScore, award_round, normalization_registry

        strategy = normalization_registry.get(slug)
        # Three members' confidence totals for one 16-game round: one near
        # the 136 ceiling, one middling, one who got nothing right.
        scores = [
            RoundScore(membership_id=1, raw_points=121, wins=14),
            RoundScore(membership_id=2, raw_points=58, wins=9),
            RoundScore(membership_id=3, raw_points=0, wins=0),
        ]
        params = self.PARAMS[slug]
        weights = strategy.weigh_round(scores, params)
        awards = award_round(scores, weights, Decimal("250"), params,
                             is_baseline=strategy.is_baseline)
        assert sum(a.points_awarded for a in awards) == Decimal("250")
