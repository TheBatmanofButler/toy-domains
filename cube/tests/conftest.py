"""Shared test set-up: where the fixtures are, the slow-test switch, and one plain search used by several files.

Slow tests need the real solver and are skipped unless pytest is run with --run-slow --solver-dir FOLDER.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cube_ladder.cube import SOLVED, TURNS, apply_turn  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", help="run the tests that need the real solver")
    parser.addoption("--solver-dir", help="folder holding nxopt23 and its table, for the slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: needs the real solver; run with --run-slow --solver-dir FOLDER")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="needs the real solver: run with --run-slow --solver-dir FOLDER")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


def read_fixture(name):
    with open(FIXTURES / name) as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="session")
def distance_table():
    """Plain breadth-first search from solved: {cube: distance} for every cube within 4 turns.
    Written here, independently of solver.py, so the solver can be checked against it."""
    table = {SOLVED: 0}
    layer = [SOLVED]
    for distance in range(1, 5):
        next_layer = []
        for cube in layer:
            for turn in TURNS:
                neighbour = apply_turn(cube, turn)
                if neighbour not in table:
                    table[neighbour] = distance
                    next_layer.append(neighbour)
        layer = next_layer
    return table


def plain_distance(cube, table):
    """Distance by the plain search: from the table within 4, or 5 if the cube is not within 4 but one turn
    takes it to 4. None if it is further."""
    if cube in table:
        return table[cube]
    return 5 if any(table.get(apply_turn(cube, turn)) == 4 for turn in TURNS) else None
