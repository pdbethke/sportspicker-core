# sportspicker-core

Scoring and aggregation for sports pick'em contests. Members predict match
results; this library decides who was right and what each round of each contest
is worth.

About 520 lines, no dependencies, no database, no HTTP, no clock.

```python
from sportspicker_core import award_round, normalization_registry, pot_for

pot = pot_for(budget=1000, round_count=4)        # 250.0 for this round
scores = [...]                                    # what each member scored
rule = normalization_registry.get("rank")
awards = award_round(scores, rule.weigh_round(scores, params), pot, params)

sum(a.points_awarded for a in awards)            # == 250.0, always
```

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

## What's here

| module | what it decides |
|---|---|
| `awards.py` | the pot, the shares, the ranks |
| `budgets.py` | what each contest contributes |
| `strategies/` | how each rule weighs a round |
| `engines/` | who was right — binary sports and MMA |
| `registry.py` | which engine a sport resolves to |

Four scoring rules ship: `rank` (championship points by finishing position),
`share` (proportional to raw score), `equal`, and `raw` — a deliberately
unnormalized baseline used for measurement, never for a live contest.

## Tests

```
python -m pytest tests_core -q      # 81 tests, well under a second
```

They need nothing but `pytest`. No services, no network, no virtualenv — which
is deliberate, and enforced: `tests_core/test_boundary.py` fails if any module
starts importing something outside the standard library.


## License

[Elastic License 2.0](LICENSE).
