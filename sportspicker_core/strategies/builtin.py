from .base import NormalizationStrategy, RoundScore
from .registry import normalization_registry


class RankStrategy(NormalizationStrategy):
    """
    Championship points by finishing position, F1 style.

    Unaffected by an engine's point scale and by how many matches a round
    holds, which is why it is the recommended default.
    """

    slug = "rank"

    def validate_config(self, params: dict) -> None:
        super().validate_config(params)
        table = params.get("points_table")
        if not table or not isinstance(table, list):
            raise ValueError("points_table must be a non-empty list")
        if any(not isinstance(v, (int, float)) or v < 0 for v in table):
            raise ValueError("points_table values must be non-negative numbers")

    def weigh_round(self, scores: list[RoundScore], params: dict) -> dict[int, float]:
        table = params["points_table"]
        tail = float(params.get("tail_value", 0))

        def value_at(position: int) -> float:
            return float(table[position]) if position < len(table) else tail

        ordered = sorted(scores, key=lambda s: s.raw_points, reverse=True)
        weights: dict[int, float] = {}

        position = 0
        while position < len(ordered):
            tied = [s for s in ordered if s.raw_points == ordered[position].raw_points]
            # Tied members share the combined value of the positions they occupy.
            pot = sum(value_at(position + offset) for offset in range(len(tied)))
            for score in tied:
                weights[score.membership_id] = pot / len(tied)
            position += len(tied)

        return weights


class ShareStrategy(NormalizationStrategy):
    """Weight is the raw score, so margin of victory survives."""

    slug = "share"

    def weigh_round(self, scores: list[RoundScore], params: dict) -> dict[int, float]:
        return {s.membership_id: float(s.raw_points) for s in scores}


class EqualStrategy(NormalizationStrategy):
    """Every member who scored at all splits the pot evenly."""

    slug = "equal"

    def weigh_round(self, scores: list[RoundScore], params: dict) -> dict[int, float]:
        return {s.membership_id: (1.0 if s.raw_points > 0 else 0.0) for s in scores}


class RawStrategy(NormalizationStrategy):
    """
    Baseline only — the unnormalised behaviour the design replaces.

    Weights are raw points, but the aggregator skips budget scaling for a
    baseline strategy, so a contest does NOT contribute its budget. That is
    precisely the defect being measured, which is why it may never be a
    group's current strategy.
    """

    slug = "raw"
    is_baseline = True

    def weigh_round(self, scores: list[RoundScore], params: dict) -> dict[int, float]:
        return {s.membership_id: float(s.raw_points) for s in scores}


for _strategy in (RankStrategy(), ShareStrategy(), EqualStrategy(), RawStrategy()):
    normalization_registry.register(_strategy)
