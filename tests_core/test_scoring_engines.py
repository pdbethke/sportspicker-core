"""
Binary scoring engine.

The engines take plain frozen dataclasses — a ``MatchOutcome`` and a
``PickInput`` — so these are pure unit tests with nothing standing in for a
database. Building the inputs is the caller's job, from whatever storage it
has.
"""
import pytest

from sportspicker_core import (
    BinaryScoringEngine, FightResult, MatchOutcome, PickInput, Side,
)

HOME, AWAY = 1, 2


def make_match(home_score, away_score):
    """Away is listed first, matching the convention the outcome names."""
    return MatchOutcome(
        away=Side(team_id=AWAY, score=away_score),
        home=Side(team_id=HOME, score=home_score),
        detail=None,
    )


def make_pick(picked_team=None, predicted_home=None, predicted_away=None):
    return PickInput(
        picked_team_id=picked_team,
        predicted_home_score=predicted_home,
        predicted_away_score=predicted_away,
        predicted_method=None,
        predicted_round=None,
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
        result = engine.score_pick(make_pick(picked_team=HOME), make_match(28, 14))

        assert result.is_correct
        assert result.points_earned == 1
        assert result.tiebreaker_score is None

    def test_incorrect_binary_pick(self, engine):
        result = engine.score_pick(make_pick(picked_team=AWAY), make_match(28, 14))

        assert not result.is_correct
        assert result.points_earned == 0

    def test_tie_game_counts_as_correct(self, engine):
        """A drawn match credits everyone."""
        result = engine.score_pick(make_pick(picked_team=HOME), make_match(21, 21))

        assert result.is_correct
        assert result.points_earned == 1

    def test_tiebreaker_pick_with_scores(self, engine):
        """Score predictions imply a winner and carry a distance."""
        result = engine.score_pick(
            make_pick(predicted_home=30, predicted_away=10), make_match(28, 14)
        )

        # Predicted home higher → picks home → home won → correct.
        assert result.is_correct
        assert result.points_earned == 1
        # |30-28| + |10-14| = 6
        assert result.tiebreaker_score == 6

    def test_tiebreaker_perfect_score(self, engine):
        result = engine.score_pick(
            make_pick(predicted_home=28, predicted_away=14), make_match(28, 14)
        )

        assert result.is_correct
        assert result.tiebreaker_score == 0

    def test_unscored_match_returns_zero(self, engine):
        result = engine.score_pick(make_pick(picked_team=HOME), make_match(None, None))

        assert not result.is_correct
        assert result.points_earned == 0

    def test_no_pick_made(self, engine):
        result = engine.score_pick(make_pick(), make_match(28, 14))

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
        result = engine_for().score_pick(
            make_pick(predicted_home=10, predicted_away=30), make_match(14, 28)
        )

        assert result.is_correct
        assert result.points_earned == 1

    def test_equal_predicted_scores_name_no_winner(self):
        """A predicted draw cannot imply a pick, so it cannot be correct."""
        result = engine_for().score_pick(
            make_pick(predicted_home=20, predicted_away=20), make_match(28, 14)
        )

        assert not result.is_correct
        assert result.points_earned == 0

    def test_an_explicit_team_wins_over_predicted_scores(self):
        """Both present: the named team decides, the scores only tiebreak."""
        result = engine_for().score_pick(
            make_pick(picked_team=HOME, predicted_home=0, predicted_away=99),
            make_match(28, 14),
        )

        assert result.is_correct
        assert result.tiebreaker_score == abs(0 - 28) + abs(99 - 14)

    def test_one_missing_side_score_makes_the_match_unscored(self):
        for home_score, away_score in ((28, None), (None, 14)):
            result = engine_for().score_pick(
                make_pick(picked_team=HOME), make_match(home_score, away_score)
            )

            assert not result.is_correct
            assert result.points_earned == 0

    def test_a_tie_credits_a_member_who_named_no_team_at_all(self):
        """Ties credit everyone — including someone with no pick to be wrong."""
        result = engine_for().score_pick(make_pick(), make_match(21, 21))

        assert result.is_correct
        assert result.points_earned == 1

    def test_a_tiebreaker_needs_both_predictions_to_be_scored(self):
        match = make_match(28, 14)

        only_home = engine_for().score_pick(
            make_pick(picked_team=HOME, predicted_home=28), match
        )
        only_away = engine_for().score_pick(
            make_pick(picked_team=HOME, predicted_away=14), match
        )

        assert only_home.tiebreaker_score is None
        assert only_away.tiebreaker_score is None

    def test_the_tiebreaker_is_a_distance_so_direction_does_not_matter(self):
        match = make_match(28, 14)

        over = engine_for().score_pick(
            make_pick(picked_team=HOME, predicted_home=31, predicted_away=14), match
        )
        under = engine_for().score_pick(
            make_pick(picked_team=HOME, predicted_home=25, predicted_away=14), match
        )

        assert over.tiebreaker_score == under.tiebreaker_score == 3


class TestMalformedInputRaises:
    """
    A malformed input is a bug upstream. Scoring it as a quiet zero would
    hand a member a plausible wrong result and hide the bug, so it raises.
    """

    def test_a_pick_for_a_team_not_in_the_match_is_refused(self):
        with pytest.raises(ValueError, match="not in this match"):
            engine_for().score_pick(make_pick(picked_team=99), make_match(28, 14))

    def test_an_object_shaped_like_a_pick_is_not_a_pick(self):
        """
        Duck-typing would let a storage row through — one that happens to have
        the right attribute names, with whatever meaning its own layer gave
        them. The contract is the dataclass.
        """
        class RowLike:
            picked_team_id = HOME
            predicted_home_score = None
            predicted_away_score = None
            predicted_method = None
            predicted_round = None

        with pytest.raises(TypeError, match="PickInput"):
            engine_for().score_pick(RowLike(), make_match(28, 14))

    def test_an_object_shaped_like_an_outcome_is_not_an_outcome(self):
        class RowLike:
            away = Side(team_id=AWAY, score=14)
            home = Side(team_id=HOME, score=28)
            detail = None

        with pytest.raises(TypeError, match="MatchOutcome"):
            engine_for().score_pick(make_pick(picked_team=HOME), RowLike())


class TestInputTypes:

    def test_the_inputs_are_frozen(self):
        match = make_match(28, 14)

        with pytest.raises(AttributeError):
            match.home = Side(team_id=3, score=0)

    def test_an_outcome_needs_two_sides(self):
        with pytest.raises(TypeError, match="Side"):
            MatchOutcome(away=(AWAY, 14), home=Side(team_id=HOME, score=28), detail=None)

    def test_a_team_cannot_play_itself(self):
        with pytest.raises(ValueError, match="both sides"):
            MatchOutcome(away=Side(team_id=HOME, score=1),
                         home=Side(team_id=HOME, score=2), detail=None)

    def test_every_field_must_be_given(self):
        """No field has a default: absence is said with None, never assumed."""
        with pytest.raises(TypeError):
            PickInput(picked_team_id=HOME)
        with pytest.raises(TypeError):
            Side(team_id=HOME)
        with pytest.raises(TypeError):
            FightResult(winner_id=HOME, method="ko")

    def test_winner_follows_the_scores(self):
        assert make_match(28, 14).winner_team_id == HOME
        assert make_match(14, 28).winner_team_id == AWAY
        assert make_match(21, 21).winner_team_id is None
        assert make_match(None, 21).winner_team_id is None
