"""
Sport modules.

A module is a declaration of everything core needs to know about a sport:
which engine scores it, and whether its results carry a sport-specific detail.
Core reads these fields instead of naming sports.

Every sport names its engine, a winner-pick sport included
(``BinaryScoringEngine()``), and a sport nobody registered is refused with
``UnknownSportError``. There is no fallback engine: scoring an unknown sport
as binary produced plausible tables for sports that score differently.

A detail is declared as a pair. ``detail_attr`` names where the caller keeps
it (for the application, a relationship on its match row), and ``detail_type``
is the frozen dataclass the engine receives as ``MatchOutcome.detail``. The
caller builds a ``detail_type`` from what it found under ``detail_attr``; the
engine never sees the caller's own object.
"""
import dataclasses
import logging
from dataclasses import dataclass

from .engines import BaseScoringEngine

logger = logging.getLogger(__name__)


class UnknownSportError(LookupError):
    """No module is registered for the sport asked about."""


@dataclass(frozen=True)
class SportModule:
    """
    ``detail_attr`` and ``detail_type`` are left out by a sport whose results
    carry no detail; that is a fact about the sport, not a value chosen for it.
    """

    slug: str
    display_name: str
    engine: BaseScoringEngine
    detail_attr: str | None = None
    detail_type: type | None = None

    def __post_init__(self):
        if not isinstance(self.engine, BaseScoringEngine):
            raise TypeError(
                f"sport '{self.slug}': engine must be a scoring engine, not "
                f"{self.engine!r}; a winner-pick sport passes BinaryScoringEngine()"
            )
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

    def register(self, module: SportModule, *, replace: bool = False) -> None:
        """
        Add a sport. A slug already registered is refused unless ``replace``
        is passed: two modules for one sport is a wiring mistake, and the one
        registered last would quietly score it.
        """
        if module.slug in self._modules and not replace:
            raise ValueError(
                f"sport '{module.slug}' is already registered; pass replace=True "
                f"to swap its module, or unregister it first"
            )
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
        """The module registered for ``slug``; UnknownSportError if there is none."""
        try:
            return self._modules[slug]
        except KeyError:
            known = ", ".join(sorted(self._modules)) or "none"
            raise UnknownSportError(
                f"no sport module is registered for '{slug}' (registered: {known}); "
                f"register one with sport_registry.register(SportModule(...))"
            ) from None

    def engine_for(self, slug: str) -> BaseScoringEngine:
        return self.get(slug).engine

    def all(self) -> list[SportModule]:
        return list(self._modules.values())


sport_registry = SportModuleRegistry()
