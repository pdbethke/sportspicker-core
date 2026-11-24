"""Built-in sport modules. Import for side effects at app startup."""
from .engines import FightResult, MmaScoringEngine
from .registry import SportModule, sport_registry

sport_registry.register(SportModule(
    slug="mma",
    display_name="MMA",
    engine=MmaScoringEngine(),
    detail_attr="fight_result",
    detail_type=FightResult,
))

sport_registry.register(SportModule(slug="football", display_name="Football"))
sport_registry.register(SportModule(slug="basketball", display_name="Basketball"))
