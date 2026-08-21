# This branch is deliberately broken

**Do not merge it.** It exists so an audit has something real to find.

## The bug

`sportspicker_core/engines/mma.py` — the method normaliser no longer treats
TKO as KO:

```python
if method in ("ko", "ko/tko"):
    return "ko"
```

A fight recorded as ending by TKO, picked by a member who said "KO", now scores
as a wrong method. They lose the method bonus — one point instead of two, or
two instead of the five-point jackpot when they also called the round.

Nobody will report this as a bug. The member sees a lower score and assumes they
were wrong; nothing errors, nothing looks broken, and the standings remain
plausible. It is precisely the kind of quiet unfairness this domain produces.

Anyone who follows the sport knows a TKO and a KO are the same outcome for
prediction purposes. That domain knowledge is what the missing branch encodes.

## Why the test suite does not catch it

`tests_core/test_mma_engine.py::test_tko_equals_ko` has been removed. Every
other MMA test uses matching method strings, so none of them exercises
normalisation at all.

    python -m pytest tests_core -q     # passes

## What an audit should report

Mutants touching the method normaliser will survive, because no test asserts
that two different spellings of the same outcome score alike. The audit should
drop below the certification threshold and the test-writer should author a case
pinning TKO and KO together.
