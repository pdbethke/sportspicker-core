# This branch is deliberately broken

**Do not merge it.** It exists so an audit has something real to find.

## The bug

`sportspicker_core/awards.py` — `min_participants` now counts everyone in the
field rather than everyone who scored:

```python
scoring = len(scores)
```

This is the subtlest of the demo branches, because the change looks like a
*correction*. The parameter is called `min_participants`, so counting
participants seems right, and a reviewer would likely approve it.

It is wrong for a reason specific to how this library works. Weights are
normalised into shares of the pot, so a member who scored nothing already takes
nothing. The risk the knob guards against is therefore not a thin turnout — it
is a thin *scoring* turnout: two members of forty getting anything right and
splitting a pot sized for forty. Counting participants does not guard against
that at all, and the guard silently never fires.

Note this cuts against a plausible-sounding critique. An audit's critic may well
advise that counting scorers is the bug and participants is the fix. It is
advice, not a verdict — and here it would be wrong.

## Why the test suite does not catch it

`tests_core/test_awards.py::TestMinimumParticipants::test_it_counts_scorers_not_pickers`
has been removed, and the remaining cases now use fields where every member
scored — so participants and scorers are the same number and the distinction
never arises. Scaling and voiding are still covered; the difference between the
two counts simply never appears in a fixture.

That is what makes the branch realistic. Nobody deletes a test suite; they
write tests that happen never to hit the case.

    python -m pytest tests_core -q     # passes

## What an audit should report

Mutants swapping the two counts will survive. A killing test needs a field where
the two genuinely differ — several members present, only one scoring.
