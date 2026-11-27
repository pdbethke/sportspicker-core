"""
Against the spread: a pick is right when the side it named covers the line.

The line is the home side's handicap: -3.5 means home is favoured by 3.5
and covers only by winning by 4 or more; +3.5 means home covers by losing
by 3 or fewer, or by winning. A game landing exactly on a whole-number line
is a push, and a push is right for everyone, the rule a tied game already
follows in the winner engine (Peter, 2026-11-27).

Defended here: the arithmetic on both sides of the line and on it, the
refusals (a weighted engine, a sport with its own result detail, a line that
is not a Decimal in half points), and that the engine's tiebreaker passes
through. The championship needs no test of its own: a spread pick still pays
0 or 1, the same range a straight round's totals already cover.
"""
from decimal import Decimal

import pytest

from sportspicker_core import (
    FightResult, MatchOutcome, ScoringResult, Side, against_the_spread,
)

AWAY, HOME = 1, 2


def _game(away: int | None, home: int | None, detail=None) -> MatchOutcome:
    return MatchOutcome(away=Side(AWAY, away), home=Side(HOME, home), detail=detail)


def _engine(correct=False, points=0, tiebreaker=None) -> ScoringResult:
    """What the sport's engine said; the spread decides correctness itself."""
    return ScoringResult(is_correct=correct, points_earned=points, tiebreaker_score=tiebreaker)


def _ats(picked, away, home, line, result=None):
    return against_the_spread(result or _engine(), picked, _game(away, home), Decimal(line))


class TestTheFavourite:
    def test_a_favourite_that_wins_by_more_than_the_line_covers(self):
        assert _ats(HOME, 20, 24, "-3.5").is_correct is True

    def test_a_favourite_that_wins_by_less_than_the_line_does_not(self):
        assert _ats(HOME, 21, 24, "-3.5").is_correct is False

    def test_the_underdog_covers_when_the_favourite_falls_short(self):
        assert _ats(AWAY, 21, 24, "-3.5").is_correct is True

    def test_the_underdog_covers_by_winning_outright(self):
        assert _ats(AWAY, 27, 24, "-3.5").is_correct is True


class TestTheUnderdogAtHome:
    def test_a_home_underdog_covers_by_losing_by_less_than_the_line(self):
        assert _ats(HOME, 24, 21, "+3.5").is_correct is True

    def test_a_home_underdog_that_loses_by_more_does_not(self):
        assert _ats(HOME, 28, 21, "+3.5").is_correct is False

    def test_the_away_favourite_covers_by_winning_by_more(self):
        assert _ats(AWAY, 28, 21, "+3.5").is_correct is True


class TestAPick:
    def test_a_line_of_zero_is_the_winner(self):
        assert _ats(HOME, 20, 21, "0").is_correct is True
        assert _ats(AWAY, 20, 21, "0").is_correct is False

    def test_a_cover_pays_one_and_a_miss_pays_nothing(self):
        assert _ats(HOME, 20, 24, "-3.5").points_earned == 1
        assert _ats(AWAY, 20, 24, "-3.5").points_earned == 0

    def test_the_engines_tiebreaker_passes_through(self):
        result = _ats(HOME, 20, 24, "-3.5", result=_engine(True, 1, tiebreaker=6))
        assert result.tiebreaker_score == 6

    def test_the_engines_verdict_does_not_decide(self):
        """The engine said the home winner was right; the line says it did not cover."""
        result = _ats(HOME, 21, 24, "-3.5", result=_engine(True, 1))
        assert (result.is_correct, result.points_earned) == (False, 0)

    def test_no_side_named_is_wrong(self):
        assert _ats(None, 20, 24, "-3.5").is_correct is False

    def test_a_game_without_a_result_pays_nothing(self):
        result = _ats(HOME, None, None, "-3.5")
        assert (result.is_correct, result.points_earned) == (False, 0)

    def test_the_input_result_is_not_changed(self):
        original = _engine(True, 1)
        _ats(AWAY, 20, 24, "-3.5", result=original)
        assert (original.is_correct, original.points_earned) == (True, 1)


class TestAPush:
    def test_a_game_landing_on_the_line_is_right_for_both_sides(self):
        assert _ats(HOME, 21, 24, "-3").is_correct is True
        assert _ats(AWAY, 21, 24, "-3").is_correct is True

    def test_a_push_pays_one(self):
        assert _ats(AWAY, 21, 24, "-3").points_earned == 1

    def test_a_push_is_right_even_with_no_side_named(self):
        """As a tied game is in the winner engine: everyone, not every picker."""
        assert _ats(None, 21, 24, "-3").is_correct is True

    def test_a_tie_on_a_line_of_zero_is_a_push(self):
        assert _ats(AWAY, 17, 17, "0").is_correct is True

    def test_one_point_off_a_whole_line_is_not_a_push(self):
        assert _ats(AWAY, 22, 24, "-3").is_correct is True
        assert _ats(HOME, 22, 24, "-3").is_correct is False


class TestRefusals:
    @pytest.mark.parametrize("paid", [2, 5])
    def test_an_engine_that_weights_its_picks_is_refused(self, paid):
        with pytest.raises(ValueError, match="0 or 1"):
            _ats(HOME, 20, 24, "-3.5", result=_engine(True, paid))

    def test_a_result_that_disagrees_with_itself_is_refused(self):
        with pytest.raises(ValueError, match="disagrees"):
            _ats(HOME, 20, 24, "-3.5", result=_engine(False, 1))

    def test_a_sport_with_its_own_result_detail_is_refused(self):
        fight = _game(0, 1, detail=FightResult(winner_id=HOME, method="ko", round=1,
                                               total_fight_time_seconds=60))
        with pytest.raises(ValueError, match="margin"):
            against_the_spread(_engine(), HOME, fight, Decimal("-1.5"))

    @pytest.mark.parametrize("line", [-3.5, 3, "3.5", None, True])
    def test_a_line_that_is_not_a_decimal_is_refused(self, line):
        with pytest.raises(TypeError, match="Decimal"):
            against_the_spread(_engine(), HOME, _game(20, 24), line)

    @pytest.mark.parametrize("line", ["-3.25", "0.1", "7.75"])
    def test_a_line_off_the_half_point_is_refused(self, line):
        with pytest.raises(ValueError, match="half"):
            _ats(HOME, 20, 24, line)

    @pytest.mark.parametrize("line", ["NaN", "Infinity", "-Infinity"])
    def test_a_line_that_is_not_a_number_is_refused(self, line):
        with pytest.raises(ValueError):
            _ats(HOME, 20, 24, line)

    def test_a_side_not_in_the_match_is_refused(self):
        with pytest.raises(ValueError, match="not in this match"):
            _ats(99, 20, 24, "-3.5")

    def test_a_result_that_is_not_a_scoring_result_is_refused(self):
        with pytest.raises(TypeError, match="ScoringResult"):
            against_the_spread(object(), HOME, _game(20, 24), Decimal("-3.5"))

    def test_an_outcome_that_is_not_a_match_outcome_is_refused(self):
        with pytest.raises(TypeError, match="MatchOutcome"):
            against_the_spread(_engine(), HOME, object(), Decimal("-3.5"))


class TestCheckLine:
    """The check a stored line goes through is the one scoring applies."""

    @pytest.mark.parametrize("line", ["-3.5", "0", "7", "+10.5"])
    def test_a_whole_or_half_point_decimal_passes(self, line):
        from sportspicker_core import check_line
        check_line(Decimal(line))

    def test_a_quarter_point_is_refused(self):
        from sportspicker_core import check_line
        with pytest.raises(ValueError, match="half"):
            check_line(Decimal("2.25"))

    def test_a_float_is_refused(self):
        from sportspicker_core import check_line
        with pytest.raises(TypeError, match="Decimal"):
            check_line(2.5)
