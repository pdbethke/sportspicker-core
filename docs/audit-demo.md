# A worked audit: scoring a pick'em league

`sportspicker_core` is the scoring domain of a sports pick'em platform. Members
predict match results; the library decides who was right and what each round of
each contest is worth. About 520 lines, no database, no HTTP, no clock.

It makes a good audit subject for a reason that has nothing to do with its
size: **you already understand the domain.** Everyone has an intuition for a
league table, so the guarantee being protected needs no explaining — and when a
mutant breaks it, you can see immediately that something is wrong.

## The guarantee

> A contest contributes exactly its budget to the championship, whatever
> scoring rule is chosen, however many members played, and however they scored.

That is what makes cross-sport aggregation possible at all. An 18-round NFL
season and a single UFC card can sit in one championship because each is
allotted a budget and each distributes precisely that — no more from a sport
with more fixtures, no less from a sport with fewer.

Everything else in the library serves it. A rule emits *relative weights*; the
library normalises them into shares of the round's pot. A rule can pay 25 points
or 25,000 and the championship is unmoved.

## Why a violation is hard to spot

Consider a round where nobody scored — every member picked wrong, or the whole
slate ended in draws. What should it pay?

The obvious answer is nothing. Nobody earned anything, so award nothing. It
reads as correct, it would pass code review, and it is wrong: that round's pot
vanishes, the contest quietly contributes less than its budget, and a sport with
more washout rounds silently counts for less than the one beside it. The correct
behaviour is to split the pot evenly — nothing distinguishes the members, so
nothing should separate them.

That is the shape of bug this domain produces. Not crashes: plausible tables
that are quietly unfair, where the only symptom is a member finishing lower than
they should have.

Real examples from the library's history, all of which shipped and were caught
later:

- Unplayed rounds paid out their full pot, so a group awarded its entire budget
  on day one and a member who had never made a pick sat level with the leader.
- Members tied on every sort key got arbitrary ranks, so two identical rebuilds
  disagreed about who came third.
- A sport whose module was not registered scored with the default engine
  instead of its own — no error, just wrong points.

## Running the audit

```
corral certify --local --repo-dir . \
  --code sportspicker_core/awards.py \
  --test tests_core/test_awards.py \
  -- python -m pytest tests_core -q
```

The core suite is 81 tests and runs in under half a second on a bare system
Python with only `pytest` installed — no virtualenv, no services, no network.
That matters in an offline jail, which binds `/usr` but not the home directory,
so a venv is invisible inside it.

`tests_core/test_boundary.py` keeps it that way: it fails if any module starts
importing something outside the standard library, checked both by running a
fresh interpreter and by reading the import statements.

## What to expect

A hand-run dry pass — sixteen goal-violating mutants planted by hand, the suite
run against each — currently kills all sixteen:

```
python scripts/mutation_dryrun.py
kill rate: 16/16 = 1.00
```

Treat that as a floor, not a prediction. Those are the failures *the test author
imagined*; an adversarial generator will plant things nobody imagined, which is
the entire reason to run it. The dry pass earns its keep differently — its first
run surfaced a real gap: the sport-module fallback was covered only by tests
that stayed behind in the application, so this suite never exercised it at all.

One thing worth knowing before reading a critic's advice: `min_participants`
counts members who **scored**, not members who played. That looks like a bug and
is not. Because weights are normalised, a member who scored nothing already
takes nothing from the pot, so the risk the knob guards against — a handful of
scorers splitting a pot meant for a much larger field — is about scorers.
Counting participants would not guard against it at all.

## Where the guarantees are written down

- `tests_core/test_awards.py::TestPotExactness` — the budget guarantee, checked
  directly rather than inferred from a league table
- `TestBaseline` — one rule deliberately ignores budgets, because measuring the
  unnormalised behaviour is its whole purpose; "fixing" it is a regression
- `TestCompetitionRanks` — tied members share a rank and the next place is
  skipped
- `README.md` — the guarantee in one sentence, and what each module decides
