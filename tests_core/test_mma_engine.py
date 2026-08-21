"""
MMA scoring engine.

Ported from sportspicker-mma/sportspicker_mma/mma/tests.py (Django).
Unit-level only — the end-to-end pipeline lives in test_scoring_service.py.

Scoring model:
    winner                      1
    winner + method             2
    winner + round              2
    winner + method + round     5   (jackpot)
    wrong winner                0
    draw / no contest           1   (everyone)
"""
from unittest.mock import MagicMock

import pytest

from sportspicker_core import MmaScoringEngine


def make_pick(picked_team=None, method="", round=None, fight_time=None):
    return MagicMock(
        picked_team=picked_team,
        predicted_method=method,
        predicted_round=round,
        predicted_home_score=fight_time,
        predicted_away_score=None,
    )


def make_match(winner=None, method="ko", round=2, fight_time=300):
    return MagicMock(
        fight_result=MagicMock(
            winner=winner,
            method=method,
            round=round,
            total_fight_time_seconds=fight_time,
        )
    )


@pytest.fixture
def engine():
    return MmaScoringEngine()


@pytest.fixture
def fighter():
    return MagicMock(id=1)


class TestMmaScoringEngine:

    def test_correct_winner_only(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter), make_match(winner=fighter)
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_wrong_winner(self, engine):
        winner, loser = MagicMock(id=1), MagicMock(id=2)

        result = engine.score_pick(
            make_pick(picked_team=loser), make_match(winner=winner)
        )

        assert not result.is_correct
        assert result.points_earned == 0

    def test_correct_winner_and_method(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, method="ko"),
            make_match(winner=fighter, method="ko"),
        )

        assert result.points_earned == 2

    def test_correct_winner_and_round(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, round=2),
            make_match(winner=fighter, round=2),
        )

        assert result.points_earned == 2

    def test_jackpot(self, engine, fighter):
        """Winner + method + round pays 5, not 3."""
        result = engine.score_pick(
            make_pick(picked_team=fighter, method="submission", round=3),
            make_match(winner=fighter, method="submission", round=3),
        )

        assert result.points_earned == 5

    def test_correct_winner_wrong_method_wrong_round(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, method="ko", round=1),
            make_match(winner=fighter, method="decision", round=None),
        )

        assert result.points_earned == 1

    def test_draw(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter),
            make_match(winner=None, method="draw"),
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_no_contest(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter),
            make_match(winner=None, method="no_contest"),
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_tko_equals_ko(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, method="tko"),
            make_match(winner=fighter, method="ko"),
        )

        assert result.points_earned == 2

    def test_sub_equals_submission(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, method="sub"),
            make_match(winner=fighter, method="submission"),
        )

        assert result.points_earned == 2

    def test_tiebreaker(self, engine, fighter):
        """predicted_home_score is total fight time in seconds."""
        result = engine.score_pick(
            make_pick(picked_team=fighter, fight_time=350),
            make_match(winner=fighter, fight_time=300),
        )

        assert result.tiebreaker_score == 50

    def test_tiebreaker_perfect(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=fighter, fight_time=300),
            make_match(winner=fighter, fight_time=300),
        )

        assert result.tiebreaker_score == 0

    def test_no_pick(self, engine, fighter):
        result = engine.score_pick(
            make_pick(picked_team=None), make_match(winner=fighter)
        )

        assert not result.is_correct
        assert result.points_earned == 0

    def test_no_fight_result(self, engine, fighter):
        """A match without a fight result scores zero rather than raising."""
        match = MagicMock()
        type(match).fight_result = property(
            lambda self: (_ for _ in ()).throw(Exception("no result"))
        )

        result = engine.score_pick(make_pick(picked_team=fighter), match)

        assert not result.is_correct
        assert result.points_earned == 0
