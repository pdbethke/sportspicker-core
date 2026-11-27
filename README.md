# sportspicker-core

[![tests](https://github.com/pdbethke/sportspicker-core/actions/workflows/tests.yml/badge.svg)](https://github.com/pdbethke/sportspicker-core/actions/workflows/tests.yml)

Scoring and aggregation for sports pick'em contests. Members predict match
results; this library decides who was right and what each round of each contest
is worth.

About 1,000 lines, no dependencies, no database, no HTTP, no clock.

## What this repository is for

Mostly, to be **audited in public**.

It is working code rather than a sample written for the occasion — something
real depends on it — and it is here because it has the three properties that
make an audit legible to a stranger: a single guarantee you can hold in your
head, a suite that finishes well under a second, and no dependencies to install
before you can run it. A repository built to be audited would prove nothing;
this is the arithmetic, audited in the open.

Anyone can clone it and reproduce the numbers published about it, including the
unflattering ones. Four branches exist to be audited: three carry a real,
documented bug **with a green test suite**, and a fourth preserves a suite
exactly as an audit graded it, gaps intact.

You are welcome to depend on it, but you almost certainly do not want to — one
application does, and it is not yours. If you came here looking for a scoring
library, that is not really what this is.

**There is no CLI, no database and no HTTP here**, because none of that is
scoring. Their absence is not an omission: it is what lets this suite run inside
an offline sandbox that mounts the system but not your home directory, so the
audit needs nothing but `pytest` and the claims about it can be checked rather
than believed. A command line over this arithmetic lives in
[sportspicker-cli][cli], which depends on this package and nothing else.

```python
from sportspicker_core import award_round, normalization_registry, round_pots

pots = round_pots(budget="1000", round_count=3)  # 333.3334, 333.3333, 333.3333
scores = [...]                                    # what each member scored
rule = normalization_registry.get("rank")
awards = award_round(scores, rule.weigh_round(scores, params), pots[0], params,
                     is_baseline=rule.is_baseline)

sum(a.points_awarded for a in awards)            # == Decimal("333.3334"), exactly
```

Amounts are `Decimal`s in ten-thousandths of a point. Where a division does not
come out even, the leftover ten-thousandths are handed out by largest remainder
with a fixed tie-break, so the parts always add back up to the whole — exactly,
not within a tolerance. A float budget or pot is refused rather than guessed at;
pass an int, a str or a `Decimal`.

## The guarantee

> A contest contributes exactly its budget to the championship, whatever
> scoring rule is chosen, however many members played, and however they scored.

That is what makes cross-sport aggregation possible. An 18-round football season
and a single fight card can sit in one championship because each is allotted a
budget and each distributes precisely that — no more from the sport with more
fixtures, no less from the one with fewer.

Everything else serves it. A rule emits *relative weights*; the library
normalizes them into shares of the round's pot. A rule can pay 25 points or
25,000 and the championship is unmoved.

"Exactly" is literal. Awards are allocated in whole ten-thousandths, so a
round's awards sum to its pot and a contest's round pots sum to its budget to
the last place, and the tests compare with `==`.

## What's here

| module | what it decides |
|---|---|
| `awards.py` | the pot, the shares, the ranks |
| `budgets.py` | what each contest contributes |
| `strategies/` | how each rule weighs a round |
| `engines/` | who was right — binary sports and MMA, from plain `PickInput` / `MatchOutcome` dataclasses |
| `formats.py` | how a round weights its scored picks — confidence points (a correct pick earns its 1..N stake) and the slate rule (distinct, in range) |
| `spreads.py` | against the spread — whether the picked side covered the home line; a push is right for everyone |
| `registry.py` | which engine a sport resolves to; an unregistered sport is refused |

Four scoring rules ship: `rank` (championship points by finishing position),
`share` (proportional to raw score), `equal`, and `raw` — a deliberately
unnormalized baseline used for measurement, never for a live contest.

## Tests

```
python -m pytest tests_core -q      # 178 tests, well under a second
```

CI runs that suite on every push, and then runs `scripts/mutation_dryrun.py` and
fails if a single planted fault survives — because a green suite and a suite
that would notice are different claims, and only the second one is worth a
badge. Pull requests additionally get an adversarial audit
([corral](https://corralai.dev)) that plants faults this repository never
imagined and measures how many the tests kill.

They need nothing but `pytest`. No services, no network, no virtualenv — which
is deliberate, and enforced: `tests_core/test_boundary.py` fails if any module
starts importing something outside the standard library.

## Why this repository exists separately

It is the audit subject for [corral](https://corralai.dev), a multi-agent code
audit tool. `AUDIT.md` and `docs/audit-demo.md` describe what to attack and why
the guarantee is hard to violate accidentally.

`scripts/mutation_dryrun.py` plants thirty-six goal-violating changes and reports
how many the tests kill. It currently kills all thirty-six — but that is a floor,
not a claim, and the library has the receipts to prove it. An adversarial audit
planted twenty faults of its own and **two got through**: a single-round contest
paying nothing, and a field landing exactly on `min_participants` being treated
as short of it. Both are now tested, and both were added to the dry-run, which
had sixteen mutants before them and has grown since with each new guarantee. Those were the failures nobody
here imagined, which is the entire argument for having something adversarial
plant them.

Three branches carry a real bug **with a green test suite**, so an audit is what
finds them rather than CI:

- `demo/bug-forfeited-pot` — a round nobody scored awards nothing
- `demo/bug-tko-not-ko` — TKO stops counting as KO
- `demo/bug-counts-pickers` — a minimum-turnout guard counts everyone present
  rather than everyone who scored

A fourth, `demo/thin-boundaries`, carries no bug at all — it is this suite as
an audit graded it, before `main` closed the two gaps that got through. Kept so
the flaws stay readable rather than disappearing into a diff. `DEMO-GAPS.md`
there explains all three, including a test that sits exactly on the boundary it
appears to cover and returns the right answer either way.

None of them should be merged.

## Versions

Breaking changes and what to do about them are listed in
[CHANGELOG.md](CHANGELOG.md). 0.3.0 removes every value the library used to
choose for its callers: an unregistered sport is refused rather than scored as
binary, and a contest budget for contests without one, a `min_participants_mode`
and a rank `tail_value` must be given.

The package is not on PyPI. Depend on a release tag's archive:

```
sportspicker-core @ https://github.com/pdbethke/sportspicker-core/archive/refs/tags/v0.3.0.tar.gz
```

## License

[Elastic License 2.0](LICENSE).
