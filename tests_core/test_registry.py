"""
Sport module resolution.

The failure this guards is silent by construction: an unregistered sport does
not raise, it falls back to binary scoring and produces plausible-looking
results for a sport that should score differently. That has bitten twice — a
test fixture registering into a dead registry, and every CLI scoring path
before registration moved into the package import.
"""
import pytest

from sportspicker_core import (
    BinaryScoringEngine, MmaScoringEngine, SportModule, SportModuleRegistry,
    sport_registry,
)


@pytest.fixture
def registry():
    """A registry of our own, so tests never disturb the shipped one."""
    return SportModuleRegistry()


class TestResolution:

    def test_a_registered_module_resolves_to_its_own_engine(self, registry):
        engine = MmaScoringEngine()
        registry.register(SportModule(
            slug="mma", display_name="MMA", engine=engine, detail_attr="fight_result"
        ))

        assert registry.engine_for("mma") is engine
        assert registry.get("mma").detail_attr == "fight_result"

    def test_an_unregistered_sport_falls_back_to_binary(self, registry):
        """
        The fallback must exist and must be binary. Returning None instead
        would push the failure into the caller, where it would surface as an
        AttributeError deep inside scoring rather than a sensible default.
        """
        assert isinstance(registry.engine_for("underwater-hockey"), BinaryScoringEngine)

    def test_a_module_registered_without_an_engine_also_scores_binary(self, registry):
        """Most sports need no special engine; declaring one must be optional."""
        registry.register(SportModule(slug="nhl", display_name="NHL"))

        assert isinstance(registry.engine_for("nhl"), BinaryScoringEngine)

    def test_an_unregistered_sport_yields_a_usable_module_not_none(self, registry):
        module = registry.get("kabaddi")

        assert module.slug == "kabaddi"
        assert module.engine is None
        assert module.detail_attr is None

    def test_registering_twice_replaces_rather_than_duplicates(self, registry):
        first, second = MmaScoringEngine(), MmaScoringEngine()
        registry.register(SportModule(slug="mma", display_name="MMA", engine=first))
        registry.register(SportModule(slug="mma", display_name="MMA", engine=second))

        assert registry.engine_for("mma") is second
        assert len([m for m in registry.all() if m.slug == "mma"]) == 1

    def test_unregister_returns_what_it_removed(self, registry):
        module = SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine())
        registry.register(module)

        assert registry.unregister("mma") is module
        assert isinstance(registry.engine_for("mma"), BinaryScoringEngine)

    def test_unregistering_something_absent_is_not_an_error(self, registry):
        assert registry.unregister("never-registered") is None


class TestAll:
    """
    ``all()`` is how anything enumerates the registered sports — the parity
    gate, the CLI listing, the shipped-registry checks below. Every other test
    in this file uses it only in passing, filtering for one slug or asking
    whether a set is a superset, so it could return a fixed list, drop an entry
    or reorder them and none of them would notice.

    Added after an audit demonstrated all three.
    """

    def test_a_new_registry_is_empty(self, registry):
        assert registry.all() == []

    def test_it_returns_every_registered_module_in_registration_order(self, registry):
        registry.register(SportModule(slug="alpha", display_name="Alpha"))
        registry.register(SportModule(slug="beta", display_name="Beta"))

        assert [m.slug for m in registry.all()] == ["alpha", "beta"]

    def test_unregistering_one_sport_leaves_the_others_alone(self, registry):
        """The obvious way to get this wrong is to clear the map instead."""
        registry.register(SportModule(slug="keep", display_name="Keep"))
        registry.register(SportModule(slug="remove", display_name="Remove"))

        registry.unregister("remove")

        assert [m.slug for m in registry.all()] == ["keep"]

    def test_the_returned_list_is_a_copy(self, registry):
        """
        Callers iterate this while registering — the parity gate does exactly
        that. Handing out the live collection would make that a mutation during
        iteration, which fails far from the cause.
        """
        registry.register(SportModule(slug="mma", display_name="MMA"))

        registry.all().clear()

        assert [m.slug for m in registry.all()] == ["mma"]


class TestShippedRegistry:
    """
    The registry this package actually ships. A typo in the built-in module
    list would ship green otherwise, because every test above builds its own.
    """

    def test_mma_is_wired_to_the_mma_engine(self):
        assert isinstance(sport_registry.engine_for("mma"), MmaScoringEngine)

    def test_mma_declares_the_detail_relationship_scoring_needs(self):
        """Without this the engine receives no fight result and scores zero."""
        assert sport_registry.get("mma").detail_attr == "fight_result"

    def test_the_binary_sports_are_registered_and_score_binary(self):
        for slug in ("football", "basketball"):
            assert isinstance(sport_registry.engine_for(slug), BinaryScoringEngine)
            assert slug in {module.slug for module in sport_registry.all()}

    def test_importing_the_package_is_enough_to_register(self):
        """
        Registration happens on package import rather than being left to each
        entry point to remember — the app, the CLI and the tests are three
        separate doors, and forgetting one degrades scoring silently.
        """
        assert {m.slug for m in sport_registry.all()} >= {"mma", "football", "basketball"}
