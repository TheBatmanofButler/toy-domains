"""Shared test set-up: where the fixtures are, the slow-test switch, and small problems made for the tests.

Slow tests take more than a minute (the earlier run's 60 problems, searched to depth 5) and are skipped unless
pytest is run with --run-slow.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fe_ladder.identity_text import read_identity  # noqa: E402
from fe_ladder.problems import problem_fields  # noqa: E402
from fe_ladder.shortest import solve  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", help="run the tests that take more than a minute")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: takes more than a minute; run with --run-slow")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="takes more than a minute: run with --run-slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


def read_fixture(name):
    with open(FIXTURES / name) as f:
        return [json.loads(line) for line in f if line.strip()]


def record(equation_text, goal_text, problem_id="test-0-0001", most_moves=5):
    """A problem record, as the build writes it, for an equation and goal given as text."""
    equation, goal = read_identity(equation_text), read_identity(goal_text)
    solution = solve(equation, goal, most_moves)
    fields = problem_fields(equation, goal, solution)
    return {"id": problem_id, **fields, "family": "made up", "planted": None, "attempt": None, "seed": None}
