"""
The boundary around the library.

`sportspicker_core` has no dependencies, and that is a property worth
defending rather than a coincidence. It is what lets the library be tested in
an offline sandbox — one that mounts the system but not a virtualenv, so
anything installed with pip is invisible inside it.

The check runs in a SUBPROCESS on purpose. `sys.modules` is process-global, so
inspecting it in-process would measure whatever the test session had already
imported rather than what this package pulls in. A fresh interpreter measures
only the library.
"""
import ast
import pathlib
import subprocess
import sys

import pytest

#: Anything outside the standard library. The list names the usual suspects
#: explicitly so a failure says which dependency crept in, rather than
#: reporting an opaque count.
FORBIDDEN = [
    "sqlalchemy", "asyncpg", "psycopg2", "fastapi", "starlette", "uvicorn",
    "duckdb", "pyarrow", "httpx", "requests", "typer", "click", "alembic",
    "pydantic", "numpy", "pandas", "scipy",
]

STDLIB = set(sys.stdlib_module_names)

#: The package's own source, found from this file rather than the working
#: directory. A cwd-relative path finds nothing when pytest runs from
#: anywhere else, and a scan of no files passes.
PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "sportspicker_core"


def _sources() -> list[pathlib.Path]:
    sources = sorted(PACKAGE.rglob("*.py"))
    assert sources, f"found no source files under {PACKAGE}; the checks below would pass on nothing"
    return sources


def _probe(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_importing_the_library_pulls_in_no_third_party_package():
    """
    The strongest form of the check: importing the top level loads every
    submodule and registers the built-in sport modules, so if anything
    anywhere reaches for a driver or a framework, this fails.
    """
    script = (
        f"import sys, sportspicker_core; "
        f"bad = sorted({{n.split('.')[0] for n in sys.modules}} & set({FORBIDDEN!r})); "
        f"assert not bad, bad"
    )

    result = _probe(script)

    assert result.returncode == 0, (
        f"the library imported {result.stderr.strip().splitlines()[-1:]}. "
        f"Keeping the dependency surface at zero is what makes it auditable "
        f"offline."
    )


def test_the_check_can_actually_fail():
    """Guard the guard: the probe must detect a forbidden import when there is one."""
    script = (
        f"import sys\n"
        f"try:\n"
        f"    import pydantic\n"
        f"except ImportError:\n"
        f"    raise SystemExit(1)\n"
        f"bad = sorted({{n.split('.')[0] for n in sys.modules}} & set({FORBIDDEN!r}))\n"
        f"assert not bad, bad\n"
    )

    result = _probe(script)

    assert result.returncode != 0, "the probe passed while a forbidden package was imported"


def test_no_module_imports_anything_outside_the_standard_library():
    """
    A source-level check to complement the runtime one.

    It reads import statements rather than searching for names, because the
    package docstring mentions other projects while explaining itself, and a
    check that cannot tell prose from an import would flag its own
    documentation.
    """
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:          # a relative import, i.e. within this package
                    continue
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                if root and root not in STDLIB and root != "sportspicker_core":
                    offenders.append(f"{path}:{node.lineno} imports {name}")

    assert not offenders, f"third-party imports in the library: {offenders}"


def test_the_source_scan_finds_the_package_from_any_working_directory(tmp_path, monkeypatch):
    """Guard the guard: the scan must not depend on where pytest was started."""
    monkeypatch.chdir(tmp_path)

    found = {path.name for path in _sources()}

    assert {"__init__.py", "awards.py", "registry.py"} <= found


#: Ways to read the clock or the calendar. Core is a function of its inputs;
#: a round scored today and rescored next year must come out the same.
CLOCK_CALLS = {
    ("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"),
    ("date", "today"), ("time", "time"), ("time", "time_ns"),
    ("time", "monotonic"), ("time", "monotonic_ns"), ("time", "perf_counter"),
    ("time", "localtime"), ("time", "gmtime"),
}


def _clock_reads(tree: ast.AST) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Attribute)):
            owner = node.value.id if isinstance(node.value, ast.Name) else node.value.attr
            if (owner, node.attr) in CLOCK_CALLS:
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module in ("time", "datetime"):
            if any((node.module, alias.name) in CLOCK_CALLS for alias in node.names):
                lines.append(node.lineno)
    return lines


def test_no_module_reads_the_clock():
    offenders = [
        f"{path.relative_to(PACKAGE.parent)}:{line}"
        for path in _sources()
        for line in _clock_reads(ast.parse(path.read_text()))
    ]

    assert not offenders, f"core reads the clock at {offenders}"


@pytest.mark.parametrize("source", [
    "import datetime\nx = datetime.datetime.now()",
    "from datetime import date\nx = date.today()",
    "import time\nx = time.time()",
    "from time import monotonic",
])
def test_the_clock_check_can_actually_fail(source):
    assert _clock_reads(ast.parse(source))
