# This branch is the suite an audit graded — gaps and all

**Do not merge it.** It exists so the flaws stay readable after `main` fixed
them.

This is the exact tree behind the published `sportspicker-pickem-certified`
recording: 20 planted faults, **18 killed, 2 survived, CERTIFIED at 0.90**.

Nothing here is a bug. `awards.py` is correct on this branch and identical to
`main`'s. What differs is what the tests *defend* — and that distinction is the
whole point, because a passing suite reports nothing about it.

## The two faults that got through

**1. A single-round contest paying nothing.** Widen the empty-contest guard in
`pot_for` from `round_count <= 0` to `<= 1` and the entire suite still passes:

```python
if round_count <= 1:      # a one-round contest now returns 0.0
    return 0.0
```

Every test here uses four rounds or none, so the one-round case — a fight card
beside an 18-round season, the exact shape the library exists to support — is
never asserted. The contest silently contributes nothing to the championship.

**2. A field exactly on `min_participants` treated as short of it.** Flip
`scoring >= minimum` to `>` and the suite still passes.

This one is subtler, and more instructive. `test_a_full_field_is_untouched`
*does* sit exactly on the minimum — but in **scale** mode, where the fallback
computes `pot * (scoring / minimum)`, which is `pot` when the two are equal. It
returns the right answer under either comparison. It reads as coverage of the
boundary and discriminates nothing. Only **void** mode separates them: the whole
pot, or none of it.

## And one test that cannot fail

The audit's critic flagged `test_a_member_missing_from_the_weights_scores_
nothing_but_stays_ranked` as tautological, and it was right:

```python
scores = field(9, 0)      # the second member scored NOTHING
weights = {1: 25.0}
...
assert by_member[2].points_awarded == 0.0
```

Because weights are normalized, a member on zero raw points takes nothing from
the pot no matter how absent-from-weights is handled. The assertion holds even
if that logic is removed entirely. Give the second member a real score and the
test starts proving something.

## What `main` did about it

All three are fixed there — two new boundary tests and a rewritten assertion —
and both faults were added to `scripts/mutation_dryrun.py`, which is why it
plants eighteen rather than sixteen. A re-audit of the fixed suite scored
**0.95, CERTIFIED**.

Read that improvement carefully. The mutants are generated fresh each run, so
0.90 → 0.95 is two samples, not a controlled measurement. What is not a sample:
two specific faults that got through before and are now covered by tests proven
to kill them.

    python -m pytest tests_core -q     # 81 tests, all passing, on this branch
