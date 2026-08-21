"""
Binary scoring engine.

Ported from sportspicker/scoring/tests.py (Django). The engines take a
match proxy that mimics Django's ``matchteam_set`` manager, so these stay
pure unit tests with no database.
"""
from unittest.mock import MagicMock

import pytest

from sportspicker_core import BinaryScoringEngine


def make_match(home_score, away_score):
    """A match proxy with two MatchTeam entries. order=0 away, order=1 home."""
    home_team = MagicMock(id=1)
    away_team = MagicMock(id=2)

    away_mt = MagicMock(team=away_team, score=away_score, order=0)
    home_mt = MagicMock(team=home_team, score=home_score, order=1)

    match = MagicMock()
    match_teams = MagicMock()
    match_teams.all.return_value.order_by.return_value = [away_mt, home_mt]
    match_teams.get.side_effect = lambda order: home_mt if order == 1 else away_mt
    match.matchteam_set = match_teams

    return match, home_team, away_team


def make_pick(picked_team=None, predicted_home=None, predicted_away=None):
    return MagicMock(
        picked_team=picked_team,
        picked_team_id=picked_team.id if picked_team else None,
        predicted_home_score=predicted_home,
        predicted_away_score=predicted_away,
    )


def engine_for():
    """A constructor for tests outside the fixture's reach."""
    return BinaryScoringEngine()


@pytest.fixture
def engine():
    return BinaryScoringEngine()


class TestBinaryScoringEngine:

    def test_correct_binary_pick(self, engine):
        """Picking the actual winner earns a point."""
        match, home_team, _ = make_match(home_score=28, away_score=14)

        result = engine.score_pick(make_pick(picked_team=home_team), match)

        assert result.is_correct
        assert result.points_earned == 1
        assert result.tiebreaker_score is None

    def test_incorrect_binary_pick(self, engine):
        match, _, away_team = make_match(home_score=28, away_score=14)

        result = engine.score_pick(make_pick(picked_team=away_team), match)

        assert not result.is_correct
        assert result.points_earned == 0

    def test_tie_game_counts_as_correct(self, engine):
        """Legacy behaviour: a drawn match credits everyone."""
        match, home_team, _ = make_match(home_score=21, away_score=21)

        result = engine.score_pick(make_pick(picked_team=home_team), match)

        assert result.is_correct
        assert result.points_earned == 1

    def test_tiebreaker_pick_with_scores(self, engine):
        """Score predictions imply a winner and carry a distance."""
        match, _, _ = make_match(home_score=28, away_score=14)

        result = engine.score_pick(
            make_pick(predicted_home=30, predicted_away=10), match
        )

        # Predicted home higher → picks home → home won → correct.
        assert result.is_correct
        assert result.points_earned == 1
        # |30-28| + |10-14| = 6
        assert result.tiebreaker_score == 6

    def test_tiebreaker_perfect_score(self, engine):
        match, _, _ = make_match(home_score=28, away_score=14)

        result = engine.score_pick(
            make_pick(predicted_home=28, predicted_away=14), match
        )

        assert result.is_correct
        assert result.tiebreaker_score == 0

    def test_unscored_match_returns_zero(self, engine):
        match, home_team, _ = make_match(home_score=None, away_score=None)

        result = engine.score_pick(make_pick(picked_team=home_team), match)

        assert not result.is_correct
        assert result.points_earned == 0

    def test_no_pick_made(self, engine):
        match, _, _ = make_match(home_score=28, away_score=14)

        result = engine.score_pick(make_pick(), match)

        assert not result.is_correct
        assert result.points_earned == 0


class TestBinaryEngineBranches:
    """
    Coverage aimed at the branches the earlier tests leave untouched. The
    engine has more decision points than it appears: a pick can name a team
    directly or imply one through predicted scores, and either side of the
    match can be missing a score.
    """

    def test_predicted_scores_pick_the_away_side_when_it_is_higher(self):
        """The mirror of the home case, which was the only one covered."""
        match, _home, away = make_match(home_score=14, away_score=28)

        result = engine_for().score_pick(
            make_pick(predicted_home=10, predicted_away=30), match
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_equal_predicted_scores_name_no_winner(self):
        """A predicted draw cannot imply a pick, so it cannot be correct."""
        match, _home, _away = make_match(home_score=28, away_score=14)

        result = engine_for().score_pick(
            make_pick(predicted_home=20, predicted_away=20), match
        )

        assert not result.is_correct
        assert result.points_earned == 0

    def test_an_explicit_team_wins_over_predicted_scores(self):
        """Both present: the named team decides, the scores only tiebreak."""
        match, home, _away = make_match(home_score=28, away_score=14)

        result = engine_for().score_pick(
            make_pick(picked_team=home, predicted_home=0, predicted_away=99), match
        )

        assert result.is_correct
        assert result.tiebreaker_score == abs(0 - 28) + abs(99 - 14)

    def test_one_missing_side_score_makes_the_match_unscored(self):
        for home_score, away_score in ((28, None), (None, 14)):
            match, home, _away = make_match(home_score=home_score, away_score=away_score)

            result = engine_for().score_pick(make_pick(picked_team=home), match)

            assert not result.is_correct
            assert result.points_earned == 0

    def test_a_tie_credits_a_member_who_named_no_team_at_all(self):
        """Ties credit everyone — including someone with no pick to be wrong."""
        match, _home, _away = make_match(home_score=21, away_score=21)

        result = engine_for().score_pick(make_pick(), match)

        assert result.is_correct
        assert result.points_earned == 1

    def test_a_tiebreaker_needs_both_predictions_to_be_scored(self):
        match, home, _away = make_match(home_score=28, away_score=14)

        only_home = engine_for().score_pick(
            make_pick(picked_team=home, predicted_home=28), match
        )
        only_away = engine_for().score_pick(
            make_pick(picked_team=home, predicted_away=14), match
        )

        assert only_home.tiebreaker_score is None
        assert only_away.tiebreaker_score is None

    def test_the_tiebreaker_is_a_distance_so_direction_does_not_matter(self):
        match, home, _away = make_match(home_score=28, away_score=14)

        over = engine_for().score_pick(
            make_pick(picked_team=home, predicted_home=31, predicted_away=14), match
        )
        under = engine_for().score_pick(
            make_pick(picked_team=home, predicted_home=25, predicted_away=14), match
        )

        assert over.tiebreaker_score == under.tiebreaker_score == 3
