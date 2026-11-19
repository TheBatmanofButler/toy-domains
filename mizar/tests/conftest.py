"""Shared test set-up: where the fixtures are, the slow-test switch, and the two small libraries the tests read.

Slow tests need the real library's files or the pinned prover and are skipped unless pytest is run with
--run-slow and --library=FOLDER or --prover=PROGRAM. Also here: the stand-in prover (tests/stand_in_prover.py),
which answers from a table.
"""
import gzip
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mizar_ladder.library import Library, sha256  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STAND_IN_PROVER = Path(__file__).resolve().parent / "stand_in_prover.py"
MADE_UP = FIXTURES / "made_up_library"
PIECES = FIXTURES / "real_pieces"
CHECKED = ("statements", "seq", "00mizrefs", "00constrnames", "xboole_1.miz")


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", help="run the tests that need the real library's files")
    parser.addoption("--library", help="the folder holding the real library's files, for the slow tests")
    parser.addoption("--prover", help="command that starts the pinned prover, for the slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs the real library's files or the prover; run with --run-slow "
                                       "--library=FOLDER --prover=PROGRAM")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="needs the real library's files or the prover: run with --run-slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


def checksums_of(folder):
    """{file: sha256} for the five checked files in `folder`, as README.md gives them for the real library."""
    return {name: sha256(Path(folder) / name) for name in CHECKED}


def read_fixture(name):
    with open(FIXTURES / name) as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="session")
def made_up():
    """The made-up library of four small articles (tests/reference/make_fixtures.py)."""
    return Library(MADE_UP, checksums_of(MADE_UP))


@pytest.fixture
def made_up_copy(tmp_path):
    """A copy of the made-up library that a test may change; `load()` reads it with fresh checksums."""
    folder = tmp_path / "library"
    shutil.copytree(MADE_UP, folder)

    class Copy:
        path = folder

        @staticmethod
        def load():
            return Library(folder, checksums_of(folder))
    return Copy


@pytest.fixture(scope="session")
def real_library(request):
    """The real library, for the slow tests, checked against README.md."""
    folder = request.config.getoption("--library")
    if not folder:
        pytest.skip("needs --library FOLDER")
    return Library(folder)


@pytest.fixture(scope="session")
def real_prover(request):
    program = request.config.getoption("--prover")
    if not program:
        pytest.skip("needs --prover=PROGRAM")
    return program


def read_json_gz(name):
    with gzip.open(FIXTURES / name, "rt") as f:
        return json.load(f)


@pytest.fixture
def stand_in_prover(tmp_path):
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
        program.write_text(f"#!{sys.executable} -I\nimport sys\nsys.path.insert(0, {str(STAND_IN_PROVER.parent)!r})\n"
                           f"import stand_in_prover\nstand_in_prover.main({str(path)!r}, {str(log)!r})\n")
        program.chmod(0o755)
        return str(program)
    return answering


def environments_seen(program):
    """The log file of the environments a stand-in program was started with, one JSON object per line."""
    return Path(str(program) + ".environments.jsonl")
