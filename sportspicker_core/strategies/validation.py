"""
Validation shared by every write path that sets a group's rules.

Lives here rather than in a route module so the CLI and the HTTP API cannot
drift apart on what counts as a valid current strategy.
"""
from .registry import normalization_registry


def validate_current_strategy(slug: str, params: dict) -> None:
    """
    Validate a strategy + params pair before it becomes a config version.

    Baseline strategies bypass budget scaling, so they exist only for the
    harness and must never be set as a group's current strategy.
    """
    strategy = normalization_registry.get(slug)
    if strategy.is_baseline:
        raise ValueError(f"'{slug}' is a baseline strategy and cannot be made current")
    strategy.validate_config(params)
