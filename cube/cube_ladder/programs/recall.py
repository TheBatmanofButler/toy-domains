"""Recall: the first turn of a scripted speedsolving method (CFOP: cross, first two layers, last layer).

The method is the open-source `rubik-solver` 0.2.0. It builds its first layer on its white face, which is our
D face (bottom). For the other version the cube is held upside down, solved, and the turns are mapped back,
so the first layer is built on our U face (top). Both versions are reported. Every converted solution is
replayed with cube.py and must solve the cube. If the method fails on a cube, the pick is equal weight on
all turns, and the failure is counted.
"""
import signal

from rubik_solver import utils

from cube_ladder.cube import (FACES, SOLVED, TURNS, apply_turns, turn_upside_down, upside_down_turn)
from cube_ladder.programs.common import pick_on
from cube_ladder.programs.method_moves import to_turns

VERSIONS = ("top", "bottom")
SECONDS_ALLOWED = 30
# The library's colour letters for our faces, and the order in which it reads the faces, as in the library's
# own mapping between its colours and face names. The evidence that they are right: every converted solution
# is replayed with cube.py and must solve the cube, and the old run's whole solutions are reproduced in both
# versions on 60 saved states (tests/test_recall.py).
_LIBRARY_COLOUR = {"U": "y", "R": "g", "F": "r", "D": "w", "L": "b", "B": "o"}
_LIBRARY_FACE_ORDER = "ULFRBD"


class MethodFailed(Exception):
    pass


def to_library(cube):
    """The cube in the library's format: its faces in the library's order, each sticker as a colour letter."""
    faces = {face: cube[9 * n:9 * n + 9] for n, face in enumerate(FACES)}
    return "".join(_LIBRARY_COLOUR[letter] for face in _LIBRARY_FACE_ORDER for letter in faces[face])


def _out_of_time(*_):
    raise MethodFailed(f"no solution within {SECONDS_ALLOWED} s")


def _bottom_layer_solution(cube):
    """The method's solution, converted to our 18 turns and checked."""
    if cube == SOLVED:
        return []
    previous = signal.signal(signal.SIGALRM, _out_of_time)
    signal.alarm(SECONDS_ALLOWED)
    try:
        moves = [str(m) for m in utils.solve(to_library(cube), "CFOP")]
    except MethodFailed:
        raise
    except Exception as error:  # the library fails in its own ways; each becomes a counted failure
        raise MethodFailed(f"the method raised {error!r}") from error
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    # The library writes whole-cube rotations in capitals (X, Y, Z); the notation uses x, y, z.
    turns = to_turns([m[0].lower() + m[1:] if m[0] in "XYZ" else m for m in moves])
    if apply_turns(cube, turns) != SOLVED:
        raise MethodFailed("the converted solution does not solve the cube")
    return turns


def solution(cube, version):
    """The method's whole solution, as a list of turns, with the first layer on the `version` face."""
    if version == "bottom":
        return _bottom_layer_solution(cube)
    if version != "top":
        raise ValueError(f"version must be one of {VERSIONS}")
    turns = [upside_down_turn(t) for t in _bottom_layer_solution(turn_upside_down(cube))]
    if apply_turns(cube, turns) != SOLVED:
        raise MethodFailed("the solution mapped back from upside down does not solve the cube")
    return turns


def picks(cubes, version):
    """Returns (picks, failures): failures lists (index of cube, reason) for each cube the method failed on."""
    chosen, failures = [], []
    for n, cube in enumerate(cubes):
        try:
            turns = solution(cube, version)
            chosen.append(pick_on(turns[:1]) if turns else pick_on(TURNS))
        except MethodFailed as failure:
            chosen.append(pick_on(TURNS))
            failures.append((n, str(failure)))
    return chosen, failures
