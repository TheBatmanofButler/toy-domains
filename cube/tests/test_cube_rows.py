"""Tests of cube_rows.py: every operation on rows agrees with its string form in cube.py."""
import random

from cube_ladder.cube import SOLVED, TURNS, apply_turn, pieces_in_place, random_cube, stickers_in_place
from cube_ladder.cube_rows import (apply_turn_to_rows, from_row, pieces_and_stickers_in_place_rows, solved_rows,
                                   to_rows)


def test_rows_agree_with_strings():
    rng = random.Random(5)
    cubes = [random_cube(rng) for _ in range(50)] + [SOLVED]
    rows = to_rows(cubes)
    assert [from_row(r) for r in rows] == cubes
    for turn in TURNS:
        turned = apply_turn_to_rows(rows, turn)
        assert [from_row(r) for r in turned] == [apply_turn(c, turn) for c in cubes]
    pieces, stickers = pieces_and_stickers_in_place_rows(rows)
    assert pieces.tolist() == [pieces_in_place(c) for c in cubes]
    assert stickers.tolist() == [stickers_in_place(c) for c in cubes]
    assert solved_rows(rows).tolist() == [False] * 50 + [True]
