"""
Sport module resolution.

An unregistered sport raises. It used to fall back to binary scoring, which
produced plausible-looking results for a sport that should score differently,
and that bit twice: a test fixture registering into a dead registry, and every
CLI scoring path before registration moved into the package import. A sport
now has to be registered, with its engine named, before anything can score it.
"""
import pytest

from dataclasses import dataclass

from sportspicker_core import (
    BinaryScoringEngine, FightResult, MmaScoringEngine, SportModule,
    SportModuleRegistry, UnknownSportError, sport_registry,
)


def binary(slug, name=None, **kwargs):
    """A module for a winner-pick sport, as most of these tests need one."""
    return SportModule(slug=slug, display_name=name or slug.title(),
                       engine=BinaryScoringEngine(), **kwargs)


@pytest.fixture
def registry():
    """A registry of our own, so tests never disturb the shipped one."""
    return SportModuleRegistry()


class TestResolution:

    def test_a_registered_module_resolves_to_its_own_engine(self, registry):
        engine = MmaScoringEngine()
        registry.register(SportModule(
            slug="mma", display_name="MMA", engine=engine,
            detail_attr="fight_result", detail_type=FightResult,
        ))

        assert registry.engine_for("mma") is engine
        assert registry.get("mma").detail_attr == "fight_result"
        assert registry.get("mma").detail_type is FightResult

    def test_an_unregistered_sport_is_refused(self, registry):
        """
        No fallback. Binary scoring for a sport nobody registered looks like a
        working table and is wrong for any sport that scores differently.
        """
        with pytest.raises(UnknownSportError, match="underwater-hockey"):
            registry.get("underwater-hockey")

    def test_engine_for_an_unregistered_sport_is_refused_too(self, registry):
        with pytest.raises(UnknownSportError, match="kabaddi"):
            registry.engine_for("kabaddi")

    def test_the_error_is_a_lookup_error(self):
        """So a caller can catch it as the missing key it is."""
        assert issubclass(UnknownSportError, LookupError)

    def test_a_module_must_name_its_engine(self):
        """
        A module without an engine used to score binary by default. Naming
        ``BinaryScoringEngine()`` is one argument; a sport that silently got it
        is what the registry exists to prevent.
        """
        with pytest.raises(TypeError, match="engine"):
            SportModule(slug="nhl", display_name="NHL")

    def test_the_engine_must_be_a_scoring_engine(self):
        with pytest.raises(TypeError, match="engine"):
            SportModule(slug="nhl", display_name="NHL", engine=None)

    def test_a_binary_sport_names_the_binary_engine(self, registry):
        registry.register(binary("nhl", "NHL"))

        assert isinstance(registry.engine_for("nhl"), BinaryScoringEngine)

    def test_registering_a_slug_twice_is_refused(self, registry):
        """
        Two modules for one sport is a wiring mistake: whichever registered
        last would score it. Refusing names the clash where it happens.
        """
        registry.register(SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine()))

        with pytest.raises(ValueError, match="'mma' is already registered"):
            registry.register(SportModule(slug="mma", display_name="MMA",
                                          engine=MmaScoringEngine()))

    def test_replacing_a_module_must_be_asked_for(self, registry):
        first, second = MmaScoringEngine(), MmaScoringEngine()
        registry.register(SportModule(slug="mma", display_name="MMA", engine=first))
        registry.register(SportModule(slug="mma", display_name="MMA", engine=second),
                          replace=True)

        assert registry.engine_for("mma") is second
        assert len([m for m in registry.all() if m.slug == "mma"]) == 1

    def test_replace_is_keyword_only(self, registry):
        with pytest.raises(TypeError):
            registry.register(binary("nhl"), True)

    def test_unregister_returns_what_it_removed(self, registry):
        module = SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine())
        registry.register(module)

        assert registry.unregister("mma") is module
        with pytest.raises(UnknownSportError):
            registry.engine_for("mma")

    def test_unregistering_something_absent_is_not_an_error(self, registry):
        assert registry.unregister("never-registered") is None


class TestDetailDeclaration:
    """
    A sport's detail is declared as a pair: where the caller finds it
    (``detail_attr``) and the plain dataclass the engine receives
    (``detail_type``). Half a declaration would leave the engine with nothing,
    or the caller with nothing to build, so it is refused at registration.
    """

    def test_a_detail_attr_without_a_type_is_refused(self):
        with pytest.raises(ValueError, match="detail_type"):
            SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine(),
                        detail_attr="fight_result")

    def test_a_detail_type_without_an_attr_is_refused(self):
        with pytest.raises(ValueError, match="detail_attr"):
            SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine(),
                        detail_type=FightResult)

    def test_the_detail_type_must_be_a_dataclass(self):
        with pytest.raises(TypeError, match="dataclass"):
            SportModule(slug="mma", display_name="MMA", engine=MmaScoringEngine(),
                        detail_attr="fight_result", detail_type=dict)

    def test_a_sport_may_declare_its_own_detail(self):
        @dataclass(frozen=True)
        class SetScores:
            winner_id: int | None
            sets_won: int

        module = binary("paddleball", detail_attr="set_scores", detail_type=SetScores)

        assert module.detail_type is SetScores


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
        registry.register(binary("alpha"))
        registry.register(binary("beta"))

        assert [m.slug for m in registry.all()] == ["alpha", "beta"]

    def test_unregistering_one_sport_leaves_the_others_alone(self, registry):
        """The obvious way to get this wrong is to clear the map instead."""
        registry.register(binary("keep"))
        registry.register(binary("remove"))

        registry.unregister("remove")

        assert [m.slug for m in registry.all()] == ["keep"]

    def test_the_returned_list_is_a_copy(self, registry):
        """
        Callers iterate this while registering — the parity gate does exactly
        that. Handing out the live collection would make that a mutation during
        iteration, which fails far from the cause.
        """
        registry.register(binary("mma"))

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
        """Without this the engine receives no fight result and cannot score."""
        assert sport_registry.get("mma").detail_attr == "fight_result"
        assert sport_registry.get("mma").detail_type is FightResult

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
