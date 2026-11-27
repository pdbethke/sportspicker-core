"""
SportsPicker core — the scoring and aggregation domain.

Given what happened in a match and what a member picked, decide who was right
and what a round is worth. That is the whole of it: no database, no HTTP, no
configuration, no clock.

Having no dependencies is the point, not an accident. Everything here is
deterministic and side-effect free, which is what allows the invariants — pot
exactness above all — to be checked directly rather than inferred from a league
table, and graded without standing anything up.

Scoring and nothing else: no database, no HTTP, no clock. None of that is
arithmetic, and each would cost the property above.
"""
from .awards import (
    Award, award_round, competition_ranks, effective_pot, min_participants_mode,
    pot_for, round_pots, to_amount,
)
from .budgets import resolve_budgets
from .engines import (
    BaseScoringEngine, BinaryScoringEngine, FightResult, MatchOutcome,
    MmaScoringEngine, PickInput, ScoringResult, Side,
)
from .formats import confidence_points, confidence_slate_error
from .spreads import against_the_spread, check_line
from .registry import (
    SportModule, SportModuleRegistry, UnknownSportError, sport_registry,
)
from .strategies import (
    NormalizationStrategy, RoundScore, normalization_registry,
    validate_current_strategy,
)

# Registering the built-in sport modules here — rather than leaving each entry
# point to remember — is deliberate. The app, the CLI and the tests are three
# separate doors into this registry. An unregistered sport now raises
# UnknownSportError; before 0.3.0 it silently scored as binary, which bit twice.
from . import modules  # noqa: E402,F401

__all__ = [
    "Award", "award_round", "competition_ranks", "effective_pot",
    "min_participants_mode", "pot_for", "round_pots", "to_amount",
    "resolve_budgets",
    "BaseScoringEngine", "BinaryScoringEngine", "MmaScoringEngine", "ScoringResult",
    "FightResult", "MatchOutcome", "PickInput", "Side",
    "confidence_points", "confidence_slate_error", "against_the_spread", "check_line",
    "SportModule", "SportModuleRegistry", "UnknownSportError", "sport_registry",
    "NormalizationStrategy", "RoundScore", "normalization_registry",
    "validate_current_strategy",
]
