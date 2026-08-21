"""
The test suite.

Deliberately empty of fixtures and imports. Every test here must run with
nothing installed but pytest, because the library is meant to be gradeable
inside an offline sandbox — one that mounts the system but not a virtualenv,
so anything pip installed is invisible.

Adding a fixture that needs a service would defeat that, and
`test_boundary.py` would fail before it did any damage.
"""
