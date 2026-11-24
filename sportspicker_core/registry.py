"""
Sport modules.

A module is a declaration of everything core needs to know about a sport:
which engine scores it, and whether its results carry a sport-specific detail.
Core reads these fields instead of naming sports.

A detail is declared as a pair. ``detail_attr`` names where the caller keeps
it (for the application, a relationship on its match row), and ``detail_type``
is the frozen dataclass the engine receives as ``MatchOutcome.detail``. The
caller builds a ``detail_type`` from what it found under ``detail_attr``; the
engine never sees the caller's own object.
"""
import dataclasses
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
    detail_type: type | None = None
    importer: Callable | None = None

    def __post_init__(self):
        if self.detail_attr is not None and self.detail_type is None:
            raise ValueError(
                f"sport '{self.slug}' declares detail_attr={self.detail_attr!r} "
                f"but no detail_type; pass the dataclass its engine receives"
            )
        if self.detail_type is not None and self.detail_attr is None:
            raise ValueError(
                f"sport '{self.slug}' declares detail_type="
                f"{self.detail_type.__name__} but no detail_attr; pass where "
                f"the caller finds the detail"
            )
        if self.detail_type is not None and not (
            isinstance(self.detail_type, type) and dataclasses.is_dataclass(self.detail_type)
        ):
            raise TypeError(
                f"sport '{self.slug}': detail_type must be a dataclass, not {self.detail_type!r}"
            )


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
