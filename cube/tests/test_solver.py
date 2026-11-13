"""Tests of solver.py: reading nxopt's real saved output, the wrapper run against a stand-in nxopt, and the
brute-force solver against a plain search. The slow tests at the end need the real solver."""
import os
import random
import stat
import sys
from pathlib import Path

import pytest
from conftest import FIXTURES, plain_distance, read_fixture

from cube_ladder.cube import SOLVED, TURNS, apply_turn, apply_turns
from cube_ladder.solver import (BruteForceSolver, PerfectSolver, SolverError, checked_solution,
                                read_solver_output, to_singmaster)


@pytest.fixture(scope="module")
def brute_force():
    return BruteForceSolver()


def plain_right_turns(cube, distance, table):
    return [turn for turn in TURNS if table.get(apply_turn(cube, turn)) == distance - 1]


def cubes_at(distance, count, table, seed):
    """`count` different cubes exactly `distance` from solved, by short random scrambles checked against the
    plain search (a cube not within 4 that has a neighbour at 4 is exactly 5 away)."""
    rng, found = random.Random(seed), set()
    while len(found) < count:
        cube = apply_turns(SOLVED, [rng.choice(TURNS) for _ in range(distance)])
        if plain_distance(cube, table) == distance:
            found.add(cube)
    return sorted(found)


# ---- reading the real solver's saved input and output

def test_singmaster_lines_equal_the_saved_input():
    cubes = [r["cube"] for r in read_fixture("pilot_random_cubes.jsonl")]
    saved = (FIXTURES / "pilot_random_cubes_nxopt.in").read_text().split("\n")
    assert [to_singmaster(c) for c in cubes] == saved[:200]
    neighbours = [r["cube"] for r in read_fixture("pilot_within_12.jsonl")]
    assert [to_singmaster(c) for c in neighbours] == (FIXTURES / "pilot_within_12_nxopt.in").read_text().split("\n")[:360]


def test_reading_saved_distances_gives_the_saved_solutions():
    saved = read_fixture("pilot_random_cubes.jsonl")
    results = read_solver_output((FIXTURES / "pilot_random_cubes_nxopt.log").read_text(), len(saved))
    for record, result in zip(saved, results):
        assert result["solved"]
        solution = checked_solution(record["cube"], result["turns"], len(result["turns"]))
        assert len(solution) == record["distance"]
        assert " ".join(solution) == record["solution"]


@pytest.mark.parametrize("depth", [0, 1, 12])
def test_reading_saved_within_runs(depth):
    saved = read_fixture(f"pilot_within_{depth}.jsonl")
    results = read_solver_output((FIXTURES / f"pilot_within_{depth}_nxopt.log").read_text(), len(saved))
    assert [r["solved"] for r in results] == [s["solved"] for s in saved]
    assert any(r["solved"] for r in results) and not all(r["solved"] for r in results)
    for record, result in zip(saved, results):
        if result["solved"]:
            assert " ".join(checked_solution(record["cube"], result["turns"], depth)) == (record["solution"] or "")


def test_a_wrong_solution_is_rejected():
    record = read_fixture("pilot_random_cubes.jsonl")[0]
    log = (FIXTURES / "pilot_random_cubes_nxopt.log").read_text()
    printed = read_solver_output(log, 200)[0]["turns"]
    with pytest.raises(SolverError):
        checked_solution(record["cube"], printed[:-1] + [printed[-1][0]], len(printed))   # last turn changed
    with pytest.raises(SolverError):
        checked_solution(record["cube"], printed, len(printed) - 1)                        # wrong length
    with pytest.raises(SolverError):
        checked_solution(record["cube"], record["solution"].split(), len(printed))         # not inverted


def test_unreadable_output_is_rejected():
    with pytest.raises(SolverError, match="no answer"):
        read_solver_output("Solved 1 in 0 probes 1 evals 1 time 0.1\n", 2)
    with pytest.raises(SolverError, match="twice"):
        read_solver_output("Solved 1 in 0 probes 1 evals 1 time 0.1\nDid not solve 1 in probes 1 evals 1 time 0.1\n", 1)
    with pytest.raises(SolverError, match="expected 2 turns"):
        read_solver_output("Solved 1 in 2 probes 1 evals 1 time 0.1\n R1\n", 1)


# ---- the wrapper, run against a stand-in nxopt program

@pytest.fixture
def stand_in_solver(tmp_path):
    program = tmp_path / "nxopt23"
    program.write_text(f"#!/bin/sh\nexec {sys.executable} {Path(__file__).parent / 'fake_nxopt.py'} \"$@\"\n")
    program.chmod(program.stat().st_mode | stat.S_IEXEC)
    return PerfectSolver(str(tmp_path), threads=2)


def test_wrapper_agrees_with_brute_force(stand_in_solver, brute_force, distance_table):
    cubes = [c for d in (1, 2, 3, 4, 5) for c in cubes_at(d, 4, distance_table, seed=d)]
    found = stand_in_solver.distances(cubes)
    assert found == brute_force.distances(cubes)
    distances = [d for d, _ in found]
    assert stand_in_solver.right_turns_many(cubes, distances) == brute_force.right_turns_many(cubes, distances)
    assert stand_in_solver.right_turns(cubes[0], 1) == brute_force.right_turns(cubes[0], 1)
    assert stand_in_solver.seconds > 0
    assert stand_in_solver.distances([]) == []


@pytest.mark.parametrize("mode, message", [("wrong", "do not solve"), ("missing", "no answer"), ("short", "expected")])
def test_wrapper_fails_loudly_on_bad_solver_output(stand_in_solver, mode, message, monkeypatch):
    monkeypatch.setenv("FAKE_NXOPT_MODE", mode)
    cube = apply_turns(SOLVED, "R U F")
    with pytest.raises(SolverError, match=message):
        stand_in_solver.distances([SOLVED, cube])


def test_wrapper_rejects_a_wrong_distance(stand_in_solver):
    cube = apply_turns(SOLVED, "R U F")
    with pytest.raises(SolverError, match="its distance is not 4"):
        stand_in_solver.right_turns(cube, 4)


def test_wrapper_fails_when_no_solution_is_found(stand_in_solver):
    far = apply_turns(SOLVED, "R U F L D B R2 U2")   # beyond the stand-in's reach
    with pytest.raises(SolverError, match="not solved"):
        stand_in_solver.distances([far])


# ---- the brute-force solver against a plain search written in conftest.py

def test_brute_force_on_every_cube_within_3(brute_force, distance_table):
    near = [c for c, d in distance_table.items() if 1 <= d <= 3]
    assert len(near) == 18 + 243 + 3240
    for cube in near:
        distance = distance_table[cube]
        (found, solution), = brute_force.distances([cube])
        assert found == distance and apply_turns(cube, solution) == SOLVED
        assert brute_force.right_turns(cube, distance) == plain_right_turns(cube, distance, distance_table)


@pytest.mark.parametrize("distance", [4, 5])
def test_brute_force_on_250_cubes_at_4_and_5(brute_force, distance_table, distance):
    for cube in cubes_at(distance, 250, distance_table, seed=100 + distance):
        (found, solution), = brute_force.distances([cube])
        assert found == distance and len(solution) == distance and apply_turns(cube, solution) == SOLVED
        assert brute_force.right_turns(cube, distance) == plain_right_turns(cube, distance, distance_table)


def test_brute_force_refuses_what_it_cannot_answer(brute_force):
    far = apply_turns(SOLVED, "R U F L D B R2 U2")
    with pytest.raises(SolverError, match="more than 5"):
        brute_force.distances([far])
    with pytest.raises(SolverError, match="outside"):
        brute_force.right_turns(SOLVED, 6)
    with pytest.raises(SolverError, match="its distance is not 3"):
        brute_force.right_turns(apply_turn(SOLVED, "R"), 3)
    assert brute_force.distances([SOLVED]) == [(0, [])]


# ---- slow: the real solver

@pytest.fixture(scope="module")
def real_solver(request):
    folder = request.config.getoption("--solver-dir")
    if not folder or not os.path.exists(os.path.join(folder, "nxopt23")):
        pytest.fail("--solver-dir must name the folder holding nxopt23 and its table")
    return PerfectSolver(folder, threads=os.cpu_count())


@pytest.mark.slow
def test_real_solver_reproduces_60_old_states(real_solver):
    old = read_fixture("old_run_states.jsonl")
    found = real_solver.distances([s["cube"] for s in old])
    assert [d for d, _ in found] == [s["distance"] for s in old]
    right = real_solver.right_turns_many([s["cube"] for s in old], [s["distance"] for s in old])
    assert [sorted(r) for r in right] == [sorted(s["right_turns"]) for s in old]


@pytest.mark.slow
def test_real_solver_agrees_with_brute_force_on_200_cubes(real_solver, brute_force, distance_table):
    cubes = [c for d in (1, 2, 3, 4, 5) for c in cubes_at(d, 40, distance_table, seed=300 + d)]
    distances = [d for d, _ in real_solver.distances(cubes)]   # the solutions may differ; their lengths may not
    assert distances == [d for d, _ in brute_force.distances(cubes)]
    assert real_solver.right_turns_many(cubes, distances) == brute_force.right_turns_many(cubes, distances)
