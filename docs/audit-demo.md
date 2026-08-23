# A worked audit: scoring a pick'em league

`sportspicker_core` is the scoring domain of a sports pick'em platform. Members
predict match results; the library decides who was right and what each round of
each contest is worth. About 700 lines, no database, no HTTP, no clock.

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

The core suite is 86 tests and runs in under half a second on a bare system
Python with only `pytest` installed — no virtualenv, no services, no network.
That matters in an offline jail, which binds `/usr` but not the home directory,
so a venv is invisible inside it.

`tests_core/test_boundary.py` keeps it that way: it fails if any module starts
importing something outside the standard library, checked both by running a
fresh interpreter and by reading the import statements.

## What to expect

A hand-run dry pass — twenty-one goal-violating mutants, the suite run against
each — currently kills all twenty-one:

```
python scripts/mutation_dryrun.py
kill rate: 21/21 = 1.00
```

Treat that as a floor, not a prediction — and here the floor has already been
tested. A real audit of this file planted twenty faults and **two survived**:
a single-round contest paying nothing, and a field landing exactly on
`min_participants` read as short of it. Neither was on the hand-written list,
because they were failures *the test author had not imagined*. Both are covered
now, which is why the count above is twenty-one. That is the entire reason to run
something adversarial rather than grade your own homework. The dry pass earns its keep differently — its first
run surfaced a real gap: the sport-module fallback had no test here at all, so
nothing in this suite would have noticed it breaking.

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

## Branches to audit against

Three branches carry a real bug **with a green test suite**, so an audit is what
finds them rather than CI. Each recreates a state this repository could
plausibly have been in: the bug is present and the test that would have caught
it does not exist yet.

| branch | the bug | why it hides |
|---|---|---|
| `demo/bug-forfeited-pot` | a round nobody scored awards nothing | reads as obviously correct; the contest quietly contributes less than its budget |
| `demo/bug-tko-not-ko` | TKO stops normalising to KO | members lose a method bonus and assume they were simply wrong |
| `demo/bug-counts-pickers` | `min_participants` counts everyone present | looks like a *correction* — the parameter is named for participants |

Run the same command against a branch and `master` to see the difference:

```
git checkout demo/bug-forfeited-pot
python -m pytest tests_core -q          # green — the suite does not know

corral certify --local --repo-dir . \
  --code sportspicker_core/awards.py \
  --test tests_core/test_awards.py \
  -- python -m pytest tests_core -q
```

Each branch carries a `DEMO-BUG.md` naming the defect, why the suite misses it,
and what a correct audit should report. **None of them should ever be merged.**

`demo/bug-counts-pickers` is the interesting one for judging a critic. The
change looks like a fix, and a critic may well advise that counting scorers was
the bug. It would be wrong — normalised weights already give non-scorers
nothing, so the guard is about scoring turnout. Advice is advisory; that branch
is where it shows.
