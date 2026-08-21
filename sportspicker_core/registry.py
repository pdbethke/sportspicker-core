"""
Sport modules.

A module is a declaration of everything core needs to know about a sport:
which engine scores it, and whether it carries a sport-specific detail
relationship on Match. Core reads these fields instead of naming sports.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .engines import BaseScoringEngine, BinaryScoringEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SportModule:
    slug: str
    display_name: str
    engine: BaseScoringEngine | None = None
    detail_attr: str | None = None
    importer: Callable | None = None


class SportModuleRegistry:

    def __init__(self):
        self._modules: dict[str, SportModule] = {}
        self._default_engine = BinaryScoringEngine()

    def register(self, module: SportModule) -> None:
        if module.slug in self._modules:
            logger.warning("Overwriting sport module '%s'", module.slug)
        self._modules[module.slug] = module
        logger.info("Registered sport module '%s'", module.slug)

    def unregister(self, slug: str) -> SportModule | None:
        """Remove and return the module registered for slug, if any.

        Callers that temporarily swap a module in (tests, mainly) should
        snapshot this return value and `register` it back in teardown,
        rather than reaching into `_modules` directly.
        """
        return self._modules.pop(slug, None)

    def get(self, slug: str) -> SportModule:
        """Unknown sports get a plain module: binary scoring, no detail."""
        return self._modules.get(slug) or SportModule(slug=slug, display_name=slug)

    def engine_for(self, slug: str) -> BaseScoringEngine:
        return self.get(slug).engine or self._default_engine

    def all(self) -> list[SportModule]:
        return list(self._modules.values())


sport_registry = SportModuleRegistry()
