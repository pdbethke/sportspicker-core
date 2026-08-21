from .base import NormalizationStrategy, RoundScore
from .registry import NormalizationRegistry, normalization_registry
from . import builtin  # noqa: F401  (registers the built-in strategies)
from .validation import validate_current_strategy
