"""Tests of programs/recall.py: the method's converted turns solve the cube, the old run's solutions are
reproduced in both versions, and every way the method can fail is counted."""
import random
import time

import pytest
from conftest import read_fixture

from cube_ladder.cube import EDGES, SOLVED, TURNS, apply_turns, random_cube
from cube_ladder.programs import recall
from cube_ladder.programs.common import pick_on


def test_converted_moves_solve_the_cube():
    rng = random.Random(12)
    cubes = [random_cube(rng) for _ in range(15)]
    for version in recall.VERSIONS:
        for cube in cubes:
            turns = recall.solution(cube, version)
            assert all(t in TURNS for t in turns)
            assert apply_turns(cube, turns) == SOLVED


def test_reproduces_the_old_run_in_both_versions():
    for state in read_fixture("old_run_states.jsonl"):
        assert recall.solution(state["cube"], "top") == state["method_top"]
        assert recall.solution(state["cube"], "bottom") == state["method_bottom"]


def test_picks_the_first_turn():
    state = read_fixture("old_run_states.jsonl")[0]
    chosen, failures = recall.picks([state["cube"]], "bottom")
    assert chosen == [pick_on([state["method_bottom"][0]])] and failures == []
    assert recall.picks([SOLVED], "top") == ([pick_on(TURNS)], [])


def first_cross(cube, turns, edges):
    """How many turns of the solution until the four given edges are all home (a cross)."""
    for n in range(len(turns) + 1):
        reached = apply_turns(cube, turns[:n])
        if all(reached[i] == SOLVED[i] for e in edges for i in EDGES[e]):
            return n


def test_each_version_builds_its_cross_on_its_own_face():
    # The method starts with a cross. The top version completes the U cross (edges UR UF UL UB) well before
    # the D cross, and the bottom version the other way round.
    rng = random.Random(3)
    for cube in (random_cube(rng) for _ in range(5)):
        top, bottom = recall.solution(cube, "top"), recall.solution(cube, "bottom")
        assert first_cross(cube, top, [0, 1, 2, 3]) < first_cross(cube, top, [4, 5, 6, 7])
        assert first_cross(cube, bottom, [4, 5, 6, 7]) < first_cross(cube, bottom, [0, 1, 2, 3])


def test_library_letters():
    assert recall.to_library(SOLVED) == "y" * 9 + "b" * 9 + "r" * 9 + "g" * 9 + "o" * 9 + "w" * 9


def failing_with(error):
    def solve(*_):
        raise error
    return solve


def test_a_method_error_is_counted_and_guessed(monkeypatch):
    monkeypatch.setattr(recall.utils, "solve", failing_with(RuntimeError("broken")))
    cube = apply_turns(SOLVED, "R U")
    chosen, failures = recall.picks([SOLVED, cube], "top")
    assert chosen[1] == pick_on(TURNS)
    assert failures == [(1, "the method raised RuntimeError('broken')")]


def test_a_slow_method_is_stopped(monkeypatch):
    monkeypatch.setattr(recall, "SECONDS_ALLOWED", 1)
    monkeypatch.setattr(recall.utils, "solve", lambda *_: time.sleep(5))
    started = time.time()
    chosen, failures = recall.picks([apply_turns(SOLVED, "R")], "bottom")
    assert time.time() - started < 4
    assert failures == [(0, "no solution within 1 s")]


def test_a_conversion_that_does_not_solve_is_a_failure(monkeypatch):
    monkeypatch.setattr(recall, "to_turns", lambda moves: ["R"])
    _, failures = recall.picks([apply_turns(SOLVED, "U")], "bottom")
    assert failures == [(0, "the converted solution does not solve the cube")]


def test_a_wrong_mapping_back_is_a_failure(monkeypatch):
    monkeypatch.setattr(recall, "upside_down_turn", lambda turn: turn)
    _, failures = recall.picks([apply_turns(SOLVED, "U F")], "top")
    assert failures == [(0, "the solution mapped back from upside down does not solve the cube")]


def test_unknown_version_is_refused():
    with pytest.raises(ValueError):
        recall.solution(SOLVED, "middle")
