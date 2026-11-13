"""Tests of programs/method_moves.py: speedcubing notation to the 18 turns."""
import random

import pytest

from cube_ladder.cube import SOLVED, TURNS, apply_turns
from cube_ladder.programs.method_moves import to_turns


def test_plain_turns_pass_through():
    assert to_turns("R U' F2 D") == ["R", "U'", "F2", "D"]
    assert to_turns(["L2", "B'"]) == ["L2", "B'"]


def test_neighbouring_turns_of_one_face_merge_or_cancel():
    assert to_turns("U U") == ["U2"]
    assert to_turns("U U'") == []
    assert to_turns("R U2 U") == ["R", "U'"]
    assert to_turns("U D U") == ["U2", "D"]   # D does not interfere with U


def test_rotations_rename_the_faces_that_follow():
    assert to_turns("y R") == ["B"]    # after y (turning like U), the old B face is at R
    assert to_turns("x U") == ["F"]    # after x (turning like R), the face at U is the old F
    assert to_turns("z U") == ["L"]    # after z (turning like F), the face at U is the old L
    assert to_turns("y2 R2'") == ["L2"]


@pytest.mark.parametrize("alg, same_as", [
    ("r", "R M'"), ("Rw", "R M'"), ("u'", "U' E"), ("f2", "F2 S2"), ("l", "L M"), ("d", "D E"), ("b", "B S'")])
def test_wide_and_slice_turns_act_on_the_cube_as_expected(alg, same_as):
    # A wide turn is a face turn plus the middle slice next to it. Compare their effect on a scrambled cube,
    # with each written in the 18 turns (the cube's centres stay put, so the frames must agree too).
    scrambled = apply_turns(SOLVED, "R U F' L2 D B'")
    assert apply_turns(scrambled, to_turns(alg + " " + _undo(same_as))) == scrambled


def _undo(alg):
    out = []
    for move in reversed(alg.split()):
        out.append(move[:-1] if move.endswith("'") else move if move.endswith("2") else move + "'")
    return " ".join(out)


def test_random_algorithms_with_rotations_and_their_inverse_cancel():
    rng = random.Random(4)
    pieces = list(TURNS) + ["x", "y", "z", "x'", "y2", "M", "E'", "S2", "r", "u2", "Lw'", "b"]
    for _ in range(200):
        alg = [rng.choice(pieces) for _ in range(12)]
        assert apply_turns(SOLVED, to_turns(alg + _undo(" ".join(alg)).split())) == SOLVED


def test_unknown_moves_are_refused():
    with pytest.raises(ValueError):
        to_turns("R Q")
    assert to_turns("(R U) (U' R')") == []
