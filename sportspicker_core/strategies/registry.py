import logging

from .base import NormalizationStrategy

logger = logging.getLogger(__name__)


class NormalizationRegistry:

    def __init__(self):
        self._strategies: dict[str, NormalizationStrategy] = {}

    def register(self, strategy: NormalizationStrategy) -> None:
        self._strategies[strategy.slug] = strategy
        logger.info("Registered normalization strategy '%s'", strategy.slug)

    def get(self, slug: str) -> NormalizationStrategy:
        try:
            return self._strategies[slug]
        except KeyError:
            raise ValueError(f"Unknown normalization strategy '{slug}'") from None

    def slugs(self) -> list[str]:
        return sorted(self._strategies)


normalization_registry = NormalizationRegistry()
