# This branch is deliberately broken

**Do not merge it.** It exists so an audit has something real to find.

## The bug

`sportspicker_core/awards.py` — when no member of a round scores, the round
awards nothing:

```python
else:
    # Nobody scored, so nobody earned anything.
    points = 0.0
```

That reads as obviously correct and would pass code review. It breaks the
guarantee the whole design rests on: **a contest contributes exactly its
budget**. A round where everyone picked wrong, or where the slate ended in
draws, silently forfeits its pot — so a sport with more washout rounds counts
for less than the one beside it, and no error is ever raised.

The correct behaviour is to split the pot evenly. Nothing distinguishes the
members, so nothing should separate them.

## Why the test suite does not catch it

`tests_core/test_awards.py::TestPotExactness` has had its all-zero-field case
removed. This is not a contrivance: it recreates the state this repository was
actually in before that test was written, when the same bug was live on `master`
and every test was green.

    python -m pytest tests_core -q     # passes

## What an audit should report

A mutation-based audit plants goal-violating changes and measures whether the
tests kill them. Mutants touching the zero-weight branch will survive here,
because nothing asserts anything about it — so the kill rate should drop below
the certification threshold and the test-writer should author a test that pins
the pot to its budget on an all-zero field.

`master` has that test and currently kills all sixteen hand-planted mutants
(`python scripts/mutation_dryrun.py`).
