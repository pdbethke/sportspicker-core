import pytest

from sportspicker_core import (
    RoundScore, normalization_registry,
)

RANK_PARAMS = {"points_table": [25, 18, 15], "tail_value": 0}


def scores(*pairs):
    return [RoundScore(membership_id=m, raw_points=p, wins=int(p), tiebreaker_total=None)
            for m, p in pairs]


def test_rank_awards_by_position():
    strategy = normalization_registry.get("rank")

    weights = strategy.weigh_round(scores((1, 10), (2, 8), (3, 3)), RANK_PARAMS)

    assert weights == {1: 25.0, 2: 18.0, 3: 15.0}


def test_rank_ties_split_combined_weight():
    """Two tied for first share 25+18; third place still gets 15."""
    strategy = normalization_registry.get("rank")

    weights = strategy.weigh_round(scores((1, 10), (2, 10), (3, 3)), RANK_PARAMS)

    assert weights[1] == weights[2] == pytest.approx(21.5)
    assert weights[3] == pytest.approx(15.0)


def test_rank_beyond_table_gets_tail_value():
    strategy = normalization_registry.get("rank")

    weights = strategy.weigh_round(scores((1, 9), (2, 7), (3, 5), (4, 1)), RANK_PARAMS)

    assert weights[4] == 0.0


def test_share_weights_by_raw_points():
    strategy = normalization_registry.get("share")

    weights = strategy.weigh_round(scores((1, 6), (2, 2)), {})

    assert weights == {1: 6.0, 2: 2.0}


def test_equal_weights_only_scoring_members():
    strategy = normalization_registry.get("equal")

    weights = strategy.weigh_round(scores((1, 5), (2, 0)), {})

    assert weights == {1: 1.0, 2: 0.0}


def test_rank_rejects_empty_points_table():
    strategy = normalization_registry.get("rank")

    with pytest.raises(ValueError):
        strategy.validate_config({"points_table": []})


def test_nonzero_drop_worst_n_is_rejected_as_unimplemented():
    """
    The knob is declared in the spec but not built. Accepting it and then
    scoring as if it were 0 would ship a silently wrong table, so it must
    be refused until it is real.
    """
    for slug, params in (
        ("rank", {"points_table": [25, 18], "drop_worst_n": 2}),
        ("share", {"drop_worst_n": 1}),
        ("equal", {"drop_worst_n": 1}),
    ):
        strategy = normalization_registry.get(slug)
        with pytest.raises(ValueError, match="not yet implemented"):
            strategy.validate_config(params)


def test_drop_worst_n_zero_is_still_accepted():
    strategy = normalization_registry.get("share")

    strategy.validate_config({"drop_worst_n": 0})
