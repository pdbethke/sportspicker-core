# Changelog

Versions follow [semantic versioning](https://semver.org/); before 1.0, a
minor version may break the API, and each one that does says so. Releases are
tagged `vX.Y.Z` on this repository. The package is not published to PyPI;
depend on a tag's archive, for example
`sportspicker-core @ https://github.com/pdbethke/sportspicker-core/archive/refs/tags/v0.3.0.tar.gz`.

## 0.3.0 — breaking

Values the library used to choose on its callers' behalf must now be given.

- An unregistered sport raises `UnknownSportError` (a `LookupError`) from
  `sport_registry.get()` and `engine_for()`. It used to score as binary.
- `SportModule(engine=...)` is required and must be a scoring engine; a
  winner-pick sport passes `BinaryScoringEngine()`. The unused `importer`
  field is gone.
- `SportModuleRegistry.register(module, *, replace=False)`: registering a slug
  that is already registered raises `ValueError` unless `replace=True`. It
  used to log a warning and replace.
- `resolve_budgets(entries)`: every entry must carry a budget; a missing one
  raises `ValueError` naming the contest. `DEFAULT_CONTEST_BUDGET` is removed,
  and so is the `default=` parameter.
- A `min_participants` greater than zero needs `min_participants_mode`
  (`"scale"` or `"void"`). `effective_pot`, `award_round` and strategy
  validation raise `ValueError` without it; it used to mean `"scale"`.
  `min_participants_mode(params)` is exported. An absent or zero
  `min_participants` still means no minimum.
- The `rank` strategy requires `tail_value` in its params, at validation and
  when weighing. It used to mean `0`.
- `ScoringResult.tiebreaker_score` has no default; pass `None` for no
  tiebreaker.
- The boundary tests find the package from the test file rather than the
  working directory, fail if they find no source files, and refuse any read
  of the clock in the library.

## 0.2.0 — breaking

- Awards and pots are exact `Decimal`s in ten-thousandths, apportioned by
  largest remainder (ties to the lowest membership id; leftover budget units
  to the earliest rounds). `Award.points_awarded`, `effective_pot`,
  `resolve_budgets` and `DEFAULT_CONTEST_BUDGET` are `Decimal` (were `float`).
- `round_pots(budget, round_count)` is new; `pot_for` now takes the round's
  index, `pot_for(budget, round_count, round_index)`, because the leftover
  units make a round's pot depend on its position. A negative round count is
  refused.
- `to_amount(value, what)` is new: amounts are an int, str or `Decimal`; a
  float, a negative or a value finer than a ten-thousandth is refused.
- `award_round(..., *, is_baseline)` is keyword-only with no default, and it
  refuses weights for members outside the field, negative or non-finite
  weights, and repeated members. The rank strategy refuses a negative
  `tail_value`.
- Engines take `score_pick(PickInput, MatchOutcome)`: frozen dataclasses
  (`Side`, `MatchOutcome`, `PickInput`, and MMA's `FightResult`) in place of
  objects shaped like a Django model. The `get_match_winner`,
  `get_match_scores`, `get_home_team` and `get_away_team` helpers are gone;
  `MatchOutcome` answers those itself. A malformed input raises instead of
  scoring zero.
- `SportModule` gains `detail_type`, the dataclass a sport's detail is passed
  as; it must be declared together with `detail_attr`.

## 0.1.0

The first version: scoring engines for winner picks and MMA, the `rank`,
`share`, `equal` and `raw` normalization strategies, the award arithmetic
that makes a contest contribute exactly its budget, contest budgets with a
shared default, and the sport module registry. No dependencies outside the
standard library, enforced by a test.

Changes made while the version stayed at 0.1.0 include: tests for the two
faults an audit found (a single-round contest paying nothing, and a field
exactly on `min_participants` read as short of it); tests that the budget
default is worth something and that the `default` parameter is used; tests for
the registry's `all()`; and CI that runs the suite and the mutation dry run.
