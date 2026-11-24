"""
What a scoring engine is given: plain, frozen, standard-library dataclasses.

An engine never sees a storage object. The caller — whatever holds matches and
picks, a database or a file — builds these from its own rows, and the engine
reads nothing else. That keeps the contract readable on its own, and it means a
row which merely happens to have similarly named attributes cannot be passed
off as an input: the engines check the type.

No field has a default. "Not predicted" or "no score yet" is said with an
explicit ``None``; leaving a field out is a TypeError rather than an assumption.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Side:
    """One competitor in a match: a team (or fighter) and the score it posted."""

    team_id: int
    #: None until the match has a result.
    score: int | None


@dataclass(frozen=True)
class MatchOutcome:
    """
    What happened in a match.

    ``away`` and ``home`` follow the usual listing order, away first. Sports
    without a home side (a fight) still name two sides; which is which only
    matters to a predicted score.

    ``detail`` is the sport's own result detail — an MMA ``FightResult``, say —
    or None for a sport that declares none. Its type is the ``detail_type`` the
    sport's module declares, so an engine knows exactly what it will receive.
    """

    away: Side
    home: Side
    detail: object | None

    def __post_init__(self):
        for name in ("away", "home"):
            if not isinstance(getattr(self, name), Side):
                raise TypeError(
                    f"MatchOutcome.{name} must be a Side, not "
                    f"{type(getattr(self, name)).__name__}"
                )
        if self.away.team_id == self.home.team_id:
            raise ValueError(
                f"team {self.home.team_id} is on both sides of the match"
            )

    @property
    def team_ids(self) -> tuple[int, int]:
        return (self.away.team_id, self.home.team_id)

    @property
    def is_scored(self) -> bool:
        return self.away.score is not None and self.home.score is not None

    @property
    def winner_team_id(self) -> int | None:
        """The higher-scoring side's team; None for a draw or an unscored match."""
        if not self.is_scored or self.away.score == self.home.score:
            return None
        return self.home.team_id if self.home.score > self.away.score else self.away.team_id


@dataclass(frozen=True)
class FightResult:
    """How a fight ended: the MMA sport's result detail."""

    #: None for a draw or a no contest.
    winner_id: int | None
    #: ko, tko, submission, decision, dq, draw, no_contest, or a variant.
    method: str
    round: int | None
    total_fight_time_seconds: int | None


@dataclass(frozen=True)
class PickInput:
    """
    What a member predicted for one match.

    ``picked_team_id`` names a side outright. ``predicted_home_score`` and
    ``predicted_away_score`` are a predicted final score; for MMA,
    ``predicted_home_score`` carries the predicted total fight time in seconds
    and is the tiebreaker. ``predicted_method`` and ``predicted_round`` are the
    MMA bonuses; an empty or None method means none was predicted.
    """

    picked_team_id: int | None
    predicted_home_score: int | None
    predicted_away_score: int | None
    predicted_method: str | None
    predicted_round: int | None
