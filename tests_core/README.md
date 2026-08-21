# The test suite

Needs nothing but `pytest` — no database, no network, no services, no
virtualenv.

    python -m pytest tests_core -q

The dependency surface is zero on purpose: it is what lets the library be
graded inside an offline sandbox, which mounts the system but not a
virtualenv. `test_boundary.py` enforces it, by running a fresh interpreter and
by reading the import statements.

Audit one of these with corral:

    corral certify --local --repo-dir . \
      --code sportspicker_core/awards.py \
      --test tests_core/test_awards.py \
      -- python -m pytest tests_core -q

If a test here would need a dependency, it belongs in the application this
library was extracted from, not here.
