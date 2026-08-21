"""
SportsPicker core — the scoring and aggregation domain.

Given what happened in a match and what a member picked, decide who was right
and what a round is worth. That is the whole of it: no database, no HTTP, no
configuration, no clock.

Having no dependencies is the point, not an accident. Everything here is
deterministic and side-effect free, which is what allows the invariants — pot
exactness above all — to be checked directly rather than inferred from a league
table, and graded without standing anything up.

The library is extracted from a larger application, which keeps the database,
the HTTP API and the command line. Only the scoring domain lives here.
"""
from .awards import Award, award_round, competition_ranks, effective_pot, pot_for
from .budgets import DEFAULT_CONTEST_BUDGET, resolve_budgets
from .engines import (
    BaseScoringEngine, BinaryScoringEngine, MmaScoringEngine, ScoringResult,
)
from .registry import SportModule, SportModuleRegistry, sport_registry
from .strategies import (
    NormalizationStrategy, RoundScore, normalization_registry,
    validate_current_strategy,
)

# Registering the built-in sport modules here — rather than leaving each entry
# point to remember — is deliberate. The app, the CLI and the tests are three
# separate doors into this registry, and an unregistered sport does not fail:
# it silently falls back to binary scoring. That has already bitten twice.
from . import modules  # noqa: E402,F401

__all__ = [
    "Award", "award_round", "competition_ranks", "effective_pot", "pot_for",
    "DEFAULT_CONTEST_BUDGET", "resolve_budgets",
    "BaseScoringEngine", "BinaryScoringEngine", "MmaScoringEngine", "ScoringResult",
    "SportModule", "SportModuleRegistry", "sport_registry",
    "NormalizationStrategy", "RoundScore", "normalization_registry",
    "validate_current_strategy",
]
