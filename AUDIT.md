# Auditing this repo

For the narrative version — what the library does, why a violation is hard to
spot, and what a run should return — see [docs/audit-demo.md](docs/audit-demo.md).

`sportspicker_core` is the scoring and aggregation domain: given what happened
in a match and what a member picked, decide who was right and what a round is
worth. No database, no HTTP, no configuration, no clock, and no dependencies —
the last of which is enforced by a test rather than left to discipline.

The suite therefore runs with no services, no network and no virtualenv —
including inside an offline audit jail, which binds `/usr` but not the home
directory, so anything pip installed is invisible inside it.

    python -m pytest tests_core -q

That command must keep working on a bare system Python with only `pytest`
installed system-wide. `tests_core/test_boundary.py` fails the moment any
module starts importing something outside the standard library.

This library is extracted from a larger application, which keeps the database,
the HTTP API and the command line. Only the scoring domain lives here, because
only the scoring domain can be graded without standing anything up.

## Targets

Ranked by how much they would hurt if silently wrong.

| target | what it decides |
|---|---|
| `sportspicker_core/awards.py` | the pot, the shares, the ranks — a contest must contribute exactly its budget |
| `sportspicker_core/strategies/builtin.py` | how each rule weighs a round, including tie splitting across the points table |
| `sportspicker_core/engines/binary.py` | correct/incorrect and the tiebreaker distance for every non-MMA sport |
| `sportspicker_core/engines/mma.py` | winner + method + round scoring, draw and no-contest handling |
| `sportspicker_core/budgets.py` | whether adding a contest devalues the ones already in a group |
| `sportspicker_core/registry.py` | which engine a sport resolves to; an unregistered sport silently falls back |

## Running corral

    corral certify --local --repo-dir . \
      --code sportspicker_core/awards.py \
      --test tests_core/test_awards.py \
      -- python -m pytest tests_core -q

Before spending an audit, run the free dry pass:

    python scripts/mutation_dryrun.py

It plants sixteen goal-violating mutants by hand and reports the kill rate
(currently 16/16). It is not an independent audit — those are the failures the
test author imagined — but it answers "would we pass?" for nothing, and its
first run found a real gap.

Notes worth knowing before the first run:

- **Python needs `pytest` installed system-wide.** A `--user` or venv install is
  invisible inside the jail and grading fails closed while the tool looks
  present on the host.
- **The default models are Claude for all three roles**, and the shadow
  challenger doubles the mutant count. For a cheaper cross-vendor run:
  `--mutant-model gemini-3.6-flash --writer-model gemini-3.6-flash
  --critic-model claude-haiku-4-5 --shadow-model off`.
- Auto-vendoring is Go-only, so the lane's zero-dependency rule is what makes
  the Python side work offline. Keep it at zero.

## Where the invariants are stated

The properties worth attacking are written down rather than implied:

- **Pot exactness** — a contest contributes exactly its budget under any
  strategy and any field, including one where nobody scored.
  `tests_core/test_awards.py::TestPotExactness`
- **Baseline bypass** — the `raw` strategy deliberately ignores budgets; that
  unnormalised behaviour is what it exists to measure and must not be
  "corrected". `TestBaseline`
- **Competition ranking** — tied members share a rank and the next place is
  skipped, matching the tie splitting the strategies perform.
- **Scorers, not pickers** — `min_participants` counts members who scored,
  because normalised weights already give non-scorers nothing.

Each is stated as a guarantee rather than as a description of the code, which
is the form an audit can attack. `docs/audit-demo.md` walks through why the
first one is hard to violate on purpose and easy to violate by accident.
