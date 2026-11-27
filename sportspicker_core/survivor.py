"""
Survivor: each round a member picks one team to win, never the same team
twice, and the first pick that does not win puts them out. The pool is won
by whoever survives longest.

Three pieces, each free of storage and clocks:

- ``survivor_result`` re-reads an engine's result for a survivor pick. A pick
  survives only by winning outright: a tied game, which the winner engine
  counts right for everyone, eliminates (Peter, 2026-11-27). Like the spread
  and confidence rules it keeps the engine's tiebreaker and refuses an
  engine that pays more than 0 or 1, or a sport whose result has its own
  detail (a fight is decided by its method, not by who outscored whom).
- ``survivor_pick_error`` is the one-team-once rule.
- ``survivor_pool`` reads the rounds in order and says who is alive, how
  many rounds each member survived, and the round that decided the pool.

What a survivor contest pays is not a rule here. It is one pot, the
contest's whole budget, paid once the pool is decided with the rounds
survived as each member's score, through ``award_round`` like any round
(Peter, 2026-11-27: "one pot at the end"). Members who went out together
have the same score, so the strategy treats them as tied; a field that all
went out in the first round is a field where nobody scored, which
``award_round`` already splits evenly. The guarantee needs nothing new.

The caller turns its own rows into verdicts. A cancelled round is not a
round here at all; a pick on a game that will not be played survives it;
a member with no pick once picking has closed is eliminated. Those are the
caller's to decide because they depend on what it stores; this module only
counts.
"""
import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum

from .engines import BaseScoringEngine, MatchOutcome, ScoringResult
from .formats import _check_unit_result


class Verdict(Enum):
    """What one round did to one member still in the pool."""
    #: Their pick won.
    SURVIVED = "survived"
    #: Their pick lost or tied, or they made none in time.
    ELIMINATED = "eliminated"
    #: Not known yet: their game is still to be decided, or they may still pick.
    PENDING = "pending"


SURVIVED, ELIMINATED, PENDING = Verdict.SURVIVED, Verdict.ELIMINATED, Verdict.PENDING


@dataclasses.dataclass(frozen=True)
class SurvivorStanding:
    membership_id: int
    alive: bool
    #: Rounds whose pick won, up to the round that decided the pool.
    rounds_survived: int
    #: Index of the round that put the member out; None while alive.
    eliminated_in: int | None


@dataclasses.dataclass(frozen=True)
class SurvivorPool:
    standings: dict[int, SurvivorStanding]
    #: Index of the round that decided the pool; None while it is open.
    decided_in: int | None


def survivor_result(result: ScoringResult, picked_team_id: int | None,
                    outcome: MatchOutcome) -> ScoringResult:
    """
    The result of a survivor pick on `picked_team_id`: right, paying 1, only
    if that side won outright. A tie, a loss or no side named is wrong and
    pays nothing; so does a game with no result yet. The engine's
    tiebreaker is kept.
    """
    _check_unit_result(result, "survivor picks")
    if not isinstance(outcome, MatchOutcome):
        raise TypeError(f"outcome must be a MatchOutcome, not {type(outcome).__name__}")
    if outcome.detail is not None:
        raise ValueError(
            "a survivor pick needs a side that outscores the other; a sport whose "
            "result has its own detail is decided some other way"
        )
    BaseScoringEngine.check_in_match(picked_team_id, outcome, "the pick")
    won = (outcome.is_scored and picked_team_id is not None
           and outcome.winner_team_id == picked_team_id)
    return dataclasses.replace(result, is_correct=won, points_earned=int(won))


def survivor_pick_error(team_id: int | None, used_team_ids: Iterable[int]) -> str | None:
    """Why `team_id` cannot be a member's survivor pick, given the teams
    their other rounds already used; None if it can."""
    if team_id is None:
        return "a survivor pick names the team to win"
    if team_id in set(used_team_ids):
        return "that team has already been used in this survivor pool; each team once"
    return None


def survivor_pool(entrants: Iterable[int], rounds: Sequence[Mapping[int, Verdict]]) -> SurvivorPool:
    """
    The pool after `rounds`, in order, each mapping every entrant to its
    verdict for that round (an eliminated member's later verdicts are read
    and ignored).

    It is decided in the first complete round that leaves one member alive
    or none, or once every round is complete; never before a round has been
    played, so a pool of one is not won by default. A round is complete when
    nobody still alive in it is PENDING. Rounds after the decision change
    nothing: the pool has been won.
    """
    members = list(entrants)
    entered = set(members)
    survived = {m: 0 for m in members}
    out_in: dict[int, int] = {}
    decided_in = None
    complete_so_far = True

    for index, verdicts in enumerate(rounds):
        stray = set(verdicts) - entered
        if stray:
            raise ValueError(f"members {sorted(stray)} have a verdict but are not an entrant")
        missing = entered - set(verdicts)
        if missing:
            raise ValueError(f"members {sorted(missing)} have no verdict in round {index}")
        for member, verdict in verdicts.items():
            if not isinstance(verdict, Verdict):
                raise ValueError(f"{verdict!r} is not a survivor verdict")

        if decided_in is not None:
            continue
        pending = False
        for member in members:
            if member in out_in:
                continue
            verdict = verdicts[member]
            if verdict is SURVIVED:
                survived[member] += 1
            elif verdict is ELIMINATED:
                out_in[member] = index
            else:
                pending = True
        complete_so_far = complete_so_far and not pending
        if complete_so_far and len(entered) - len(out_in) <= 1:
            decided_in = index

    if decided_in is None and complete_so_far and rounds:
        decided_in = len(rounds) - 1

    standings = {
        m: SurvivorStanding(membership_id=m, alive=m not in out_in,
                            rounds_survived=survived[m], eliminated_in=out_in.get(m))
        for m in members
    }
    return SurvivorPool(standings=standings, decided_in=decided_in)
