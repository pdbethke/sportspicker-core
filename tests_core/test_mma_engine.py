"""
MMA scoring engine.

Unit-level only — the end-to-end pipeline lives with the application.

Scoring model:
    winner                      1
    winner + method             2
    winner + round              2
    winner + method + round     5   (jackpot)
    wrong winner                0
    draw / no contest           1   (everyone)
"""
import pytest

from sportspicker_core import (
    FightResult, MatchOutcome, MmaScoringEngine, PickInput, Side,
)

FIGHTER, OPPONENT = 1, 2


def make_pick(picked_team=None, method=None, round=None, fight_time=None):
    return PickInput(
        picked_team_id=picked_team,
        predicted_method=method,
        predicted_round=round,
        predicted_home_score=fight_time,
        predicted_away_score=None,
    )


def make_match(winner=None, method="ko", round=2, fight_time=300):
    return MatchOutcome(
        away=Side(team_id=FIGHTER, score=None),
        home=Side(team_id=OPPONENT, score=None),
        detail=FightResult(
            winner_id=winner,
            method=method,
            round=round,
            total_fight_time_seconds=fight_time,
        ),
    )


@pytest.fixture
def engine():
    return MmaScoringEngine()


class TestMmaScoringEngine:

    def test_correct_winner_only(self, engine):
        result = engine.score_pick(make_pick(FIGHTER), make_match(winner=FIGHTER))

        assert result.is_correct
        assert result.points_earned == 1

    def test_wrong_winner(self, engine):
        result = engine.score_pick(make_pick(OPPONENT), make_match(winner=FIGHTER))

        assert not result.is_correct
        assert result.points_earned == 0

    def test_correct_winner_and_method(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, method="ko"), make_match(winner=FIGHTER, method="ko"),
        )

        assert result.points_earned == 2

    def test_correct_winner_and_round(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, round=2), make_match(winner=FIGHTER, round=2),
        )

        assert result.points_earned == 2

    def test_jackpot(self, engine):
        """Winner + method + round pays 5, not 3."""
        result = engine.score_pick(
            make_pick(FIGHTER, method="submission", round=3),
            make_match(winner=FIGHTER, method="submission", round=3),
        )

        assert result.points_earned == 5

    def test_correct_winner_wrong_method_wrong_round(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, method="ko", round=1),
            make_match(winner=FIGHTER, method="decision", round=None),
        )

        assert result.points_earned == 1

    def test_draw(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER), make_match(winner=None, method="draw"),
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_no_contest(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER), make_match(winner=None, method="no_contest"),
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_tko_equals_ko(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, method="tko"), make_match(winner=FIGHTER, method="ko"),
        )

        assert result.points_earned == 2

    def test_sub_equals_submission(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, method="sub"),
            make_match(winner=FIGHTER, method="submission"),
        )

        assert result.points_earned == 2

    def test_an_empty_method_is_no_prediction(self, engine):
        """Storage may hold "" for "not predicted"; it must not match anything."""
        result = engine.score_pick(
            make_pick(FIGHTER, method=""), make_match(winner=FIGHTER, method=""),
        )

        assert result.points_earned == 1

    def test_tiebreaker(self, engine):
        """predicted_home_score is total fight time in seconds."""
        result = engine.score_pick(
            make_pick(FIGHTER, fight_time=350), make_match(winner=FIGHTER, fight_time=300),
        )

        assert result.tiebreaker_score == 50

    def test_tiebreaker_perfect(self, engine):
        result = engine.score_pick(
            make_pick(FIGHTER, fight_time=300), make_match(winner=FIGHTER, fight_time=300),
        )

        assert result.tiebreaker_score == 0

    def test_no_pick(self, engine):
        result = engine.score_pick(make_pick(None), make_match(winner=FIGHTER))

        assert not result.is_correct
        assert result.points_earned == 0


class TestMalformedInputRaises:
    """
    A fight with no result, or a result naming someone who was not in it, is
    a bug upstream. It used to score a quiet zero for everyone, which reads
    as a card where nobody picked right; now it raises.
    """

    def test_a_fight_without_a_result_raises(self, engine):
        match = MatchOutcome(
            away=Side(team_id=FIGHTER, score=None),
            home=Side(team_id=OPPONENT, score=None),
            detail=None,
        )

        with pytest.raises(ValueError, match="FightResult"):
            engine.score_pick(make_pick(FIGHTER), match)

    def test_a_detail_of_the_wrong_type_raises(self, engine):
        match = MatchOutcome(
            away=Side(team_id=FIGHTER, score=None),
            home=Side(team_id=OPPONENT, score=None),
            detail={"winner_id": FIGHTER, "method": "ko"},
        )

        with pytest.raises(ValueError, match="FightResult"):
            engine.score_pick(make_pick(FIGHTER), match)

    def test_a_winner_who_was_not_in_the_fight_raises(self, engine):
        with pytest.raises(ValueError, match="not in this match"):
            engine.score_pick(make_pick(FIGHTER), make_match(winner=99))

    def test_a_pick_for_someone_not_in_the_fight_raises(self, engine):
        with pytest.raises(ValueError, match="not in this match"):
            engine.score_pick(make_pick(99), make_match(winner=FIGHTER))
