"""Shared test set-up: where the fixtures are, the slow-test switch, and the stand-in prover.

Slow tests need the pinned prover and are skipped unless pytest is run with --run-slow --prover PROGRAM.
"""
import gzip
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REFERENCE = Path(__file__).resolve().parent / "reference"
STAND_IN = Path(__file__).resolve().parent / "stand_in_prover.py"


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", help="run the tests that need the pinned prover")
    parser.addoption("--prover", help="command that starts the pinned prover, for the slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs the pinned prover; run with --run-slow --prover PROGRAM")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="needs the pinned prover: run with --run-slow --prover PROGRAM")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def real_prover(request):
    program = request.config.getoption("--prover")
    if not program:
        pytest.fail("the slow tests need --prover PROGRAM")
    return program


def read_jsonl_gz(name):
    with gzip.open(FIXTURES / name, "rt") as f:
        return [json.loads(line) for line in f]


def read_json(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def stand_in(tmp_path):
    """The stand-in prover, answering from a table: call it with a list of (texts that must all appear in the
    arguments or input, answer to print), and the version it reports if not the pinned one. Returns the path of
    a program that starts it with that table (see stand_in_prover.py for why the table is not a setting). The
    environment of every start is logged (see environments_seen)."""
    made = []

    def answering(table, version=None):
        made.append(None)
        path = tmp_path / f"stand_in_table_{len(made)}.json"
        path.write_text(json.dumps({"version": version,
                                    "answers": [{"when": list(when), "output": output} for when, output in table]}))
        program = tmp_path / f"stand_in_prover_{len(made)}"
        log = environments_seen(program)
        program.write_text(f"#!{sys.executable} -I\nimport sys\nsys.path.insert(0, {str(STAND_IN.parent)!r})\n"
                           f"import stand_in_prover\nstand_in_prover.main({str(path)!r}, {str(log)!r})\n")
        program.chmod(0o755)
        return str(program)
    return answering


def environments_seen(program):
    """The log file of the environments a stand-in program was started with, one JSON object per line."""
    return Path(str(program) + ".environments.jsonl")


def pilot_code():
    """The earlier pilot's code, kept in tests/reference/ and used by tests only."""
    if str(REFERENCE) not in sys.path:
        sys.path.insert(0, str(REFERENCE))
    import fol.terms
    return fol.terms

