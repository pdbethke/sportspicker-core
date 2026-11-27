"""
Survivor: one pick a round, a team at most once, and a loss puts you out.

Three things are defended here.

The verdict: a pick survives only by winning outright. A tied game, which
the winner engine counts right for everyone, eliminates in a survivor pool
(Peter, 2026-11-27).

The pool: who is still alive, how many rounds each member survived, and
the round that decided it (one member left, or none, or no rounds left).
Members who go out together tie, so they share whatever the pool pays.

The guarantee: a decided pool, paid as one pot through `award_round`, pays
exactly that pot under every live strategy, a field where everyone went out
in round one included.
"""
from decimal import Decimal

import pytest

from sportspicker_core import (
    ELIMINATED, PENDING, SURVIVED, FightResult, MatchOutcome, RoundScore, ScoringResult, Side,
    award_round, normalization_registry, survivor_pick_error, survivor_pool, survivor_result,
)

AWAY, HOME = 1, 2


def _game(away, home, detail=None) -> MatchOutcome:
    return MatchOutcome(away=Side(AWAY, away), home=Side(HOME, home), detail=detail)


def _engine(correct=False, points=0, tiebreaker=None) -> ScoringResult:
    return ScoringResult(is_correct=correct, points_earned=points, tiebreaker_score=tiebreaker)


class TestTheVerdict:
    def test_a_win_survives(self):
        result = survivor_result(_engine(True, 1), HOME, _game(10, 24))
        assert (result.is_correct, result.points_earned) == (True, 1)

    def test_a_loss_eliminates(self):
        result = survivor_result(_engine(False, 0), HOME, _game(24, 10))
        assert (result.is_correct, result.points_earned) == (False, 0)

    def test_a_tie_eliminates_although_the_engine_calls_it_right(self):
        result = survivor_result(_engine(True, 1), HOME, _game(17, 17))
        assert (result.is_correct, result.points_earned) == (False, 0)

    def test_no_side_named_eliminates(self):
        assert survivor_result(_engine(), None, _game(10, 24)).is_correct is False

    def test_a_game_without_a_result_pays_nothing(self):
        result = survivor_result(_engine(), HOME, _game(None, None))
        assert (result.is_correct, result.points_earned) == (False, 0)

    def test_the_tiebreaker_passes_through(self):
        assert survivor_result(_engine(True, 1, tiebreaker=5), HOME, _game(10, 24)).tiebreaker_score == 5

    @pytest.mark.parametrize("paid", [2, 5])
    def test_a_weighted_engine_is_refused(self, paid):
        with pytest.raises(ValueError, match="0 or 1"):
            survivor_result(_engine(True, paid), HOME, _game(10, 24))

    def test_a_fight_is_refused(self):
        fight = _game(0, 1, detail=FightResult(winner_id=HOME, method="ko", round=1,
                                               total_fight_time_seconds=60))
        with pytest.raises(ValueError, match="detail"):
            survivor_result(_engine(True, 1), HOME, fight)

    def test_a_side_not_in_the_match_is_refused(self):
        with pytest.raises(ValueError, match="not in this match"):
            survivor_result(_engine(), 99, _game(10, 24))

    def test_an_outcome_that_is_not_a_match_outcome_is_refused(self):
        with pytest.raises(TypeError, match="MatchOutcome"):
            survivor_result(_engine(), HOME, object())


class TestTheTeamRule:
    def test_a_fresh_team_is_allowed(self):
        assert survivor_pick_error(7, {3, 4}) is None

    def test_a_used_team_is_named(self):
        assert "already" in survivor_pick_error(3, {3, 4})

    def test_no_team_is_refused(self):
        assert survivor_pick_error(None, set()) is not None


class TestThePool:
    def test_everyone_alive_before_any_round(self):
        pool = survivor_pool([1, 2], [])
        assert {m: s.alive for m, s in pool.standings.items()} == {1: True, 2: True}
        assert pool.decided_in is None

    def test_a_loss_puts_a_member_out_in_that_round(self):
        pool = survivor_pool([1, 2, 3], [{1: SURVIVED, 2: ELIMINATED, 3: SURVIVED}])
        two = pool.standings[2]
        assert (two.alive, two.rounds_survived, two.eliminated_in) == (False, 0, 0)
        assert pool.standings[1].rounds_survived == 1

    def test_an_eliminated_member_stays_out_whatever_comes_after(self):
        pool = survivor_pool([1, 2, 3], [
            {1: SURVIVED, 2: ELIMINATED, 3: SURVIVED},
            {1: SURVIVED, 2: SURVIVED, 3: SURVIVED},
        ])
        assert (pool.standings[2].alive, pool.standings[2].rounds_survived) == (False, 0)

    def test_the_last_one_standing_decides_it(self):
        pool = survivor_pool([1, 2, 3], [
            {1: SURVIVED, 2: SURVIVED, 3: ELIMINATED},
            {1: SURVIVED, 2: ELIMINATED, 3: ELIMINATED},
            {1: SURVIVED, 2: ELIMINATED, 3: ELIMINATED},
        ])
        assert pool.decided_in == 1
        # Rounds after the decision do not count: the winner has won.
        assert pool.standings[1].rounds_survived == 2

    def test_members_who_go_out_together_tie(self):
        pool = survivor_pool([1, 2, 3], [
            {1: SURVIVED, 2: SURVIVED, 3: ELIMINATED},
            {1: ELIMINATED, 2: ELIMINATED, 3: ELIMINATED},
        ])
        assert pool.decided_in == 1
        assert pool.standings[1].rounds_survived == pool.standings[2].rounds_survived == 1
        assert not pool.standings[1].alive and not pool.standings[2].alive

    def test_a_pending_pick_keeps_a_member_alive_and_the_pool_open(self):
        pool = survivor_pool([1, 2], [{1: SURVIVED, 2: PENDING}])
        assert pool.standings[2].alive is True
        assert pool.standings[2].rounds_survived == 0
        assert pool.decided_in is None

    def test_a_pending_round_holds_the_decision_even_if_one_is_left(self):
        """Two out, one pending: the pending one may still lose and tie the others."""
        pool = survivor_pool([1, 2, 3], [{1: PENDING, 2: ELIMINATED, 3: ELIMINATED}])
        assert pool.decided_in is None

    def test_running_out_of_rounds_decides_it(self):
        pool = survivor_pool([1, 2], [{1: SURVIVED, 2: SURVIVED}, {1: SURVIVED, 2: SURVIVED}])
        assert pool.decided_in == 1
        assert pool.standings[1].alive and pool.standings[2].alive

    def test_a_round_still_pending_at_the_end_is_not_decided(self):
        pool = survivor_pool([1, 2], [{1: SURVIVED, 2: SURVIVED}, {1: SURVIVED, 2: PENDING}])
        assert pool.decided_in is None

    def test_a_pool_of_one_is_decided_only_after_a_round(self):
        assert survivor_pool([1], []).decided_in is None
        assert survivor_pool([1], [{1: SURVIVED}]).decided_in == 0

    def test_every_entrant_needs_a_verdict_in_every_round(self):
        with pytest.raises(ValueError, match="no verdict"):
            survivor_pool([1, 2], [{1: SURVIVED}])

    def test_a_verdict_for_someone_not_entered_is_refused(self):
        with pytest.raises(ValueError, match="not an entrant"):
            survivor_pool([1], [{1: SURVIVED, 9: SURVIVED}])

    def test_an_unknown_verdict_is_refused(self):
        with pytest.raises(ValueError, match="verdict"):
            survivor_pool([1], [{1: "won"}])


class TestTheGuaranteeHolds:
    """
    A decided pool is paid as one pot, the contest's whole budget, with the
    rounds survived as each member's score. Every live strategy must pay
    exactly that pot, including a field that all went out together.
    """

    PARAMS = {
        "rank": {"points_table": [25, 18, 15], "tail_value": 0},
        "share": {},
        "equal": {},
    }

    def _pay(self, pool, slug):
        strategy = normalization_registry.get(slug)
        scores = [RoundScore(membership_id=m, raw_points=s.rounds_survived, wins=s.rounds_survived)
                  for m, s in pool.standings.items()]
        params = self.PARAMS[slug]
        return award_round(scores, strategy.weigh_round(scores, params), Decimal("1000"), params,
                           is_baseline=strategy.is_baseline)

    @pytest.mark.parametrize("slug", ["rank", "share", "equal"])
    def test_a_decided_pool_pays_exactly_its_pot(self, slug):
        pool = survivor_pool([1, 2, 3, 4], [
            {1: SURVIVED, 2: SURVIVED, 3: SURVIVED, 4: ELIMINATED},
            {1: SURVIVED, 2: SURVIVED, 3: ELIMINATED, 4: ELIMINATED},
            {1: SURVIVED, 2: ELIMINATED, 3: ELIMINATED, 4: ELIMINATED},
        ])
        assert pool.decided_in == 2
        assert sum(a.points_awarded for a in self._pay(pool, slug)) == Decimal("1000")

    @pytest.mark.parametrize("slug", ["rank", "share", "equal"])
    def test_a_field_that_all_went_out_in_round_one_still_pays_its_pot(self, slug):
        pool = survivor_pool([1, 2, 3], [{1: ELIMINATED, 2: ELIMINATED, 3: ELIMINATED}])
        assert pool.decided_in == 0
        paid = self._pay(pool, slug)
        assert sum(a.points_awarded for a in paid) == Decimal("1000")
        # Nobody survived a round, so nobody is ahead: an even split.
        assert len({a.points_awarded for a in paid}) <= 2  # 1000/3 leaves one unit over
