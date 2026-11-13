"""Tests of cube.py: turns, validity, random cubes, the sticker score, and agreement with the old cube model."""
import random
import sys
from collections import Counter
from pathlib import Path

import pytest

from cube_ladder.cube import (CORNERS, EDGES, SOLVED, TURNS, apply_turn, apply_turns, cube_from_pieces,
                              inverse_turn, inverse_turns, is_valid, pieces_in_place, random_cube, read_pieces,
                              stickers_in_place, turn_upside_down, upside_down_turn)

sys.path.insert(0, str(Path(__file__).resolve().parent / "reference"))
from old_puzzle import CUBE3, state_to_str, str_to_state  # noqa: E402


def random_turns(rng, length):
    return [rng.choice(TURNS) for _ in range(length)]


@pytest.mark.parametrize("turn", TURNS)
def test_every_turn_four_times_changes_nothing(turn):
    assert apply_turns(SOLVED, [turn] * 4) == SOLVED
    scrambled = apply_turns(SOLVED, "R U F' L2 D B")
    assert apply_turns(scrambled, [turn] * 4) == scrambled


@pytest.mark.parametrize("turn", TURNS)
def test_turn_then_inverse_changes_nothing(turn):
    assert apply_turns(SOLVED, [turn, inverse_turn(turn)]) == SOLVED
    assert apply_turn(SOLVED, turn) != SOLVED


def test_inverse_turns_undo_a_sequence():
    rng = random.Random(1)
    for _ in range(100):
        turns = random_turns(rng, 12)
        assert apply_turns(apply_turns(SOLVED, turns), inverse_turns(turns)) == SOLVED


def test_sexy_move_six_times_changes_nothing():
    assert apply_turns(SOLVED, "R U R' U'") != SOLVED
    assert apply_turns(SOLVED, ["R", "U", "R'", "U'"] * 6) == SOLVED


def test_half_turn_is_two_quarter_turns():
    for face in "URFDLB":
        assert apply_turn(SOLVED, face + "2") == apply_turns(SOLVED, [face, face])
        assert apply_turn(SOLVED, face + "'") == apply_turns(SOLVED, [face] * 3)


def test_number_of_cubes_at_each_distance(distance_table):
    counts = Counter(distance_table.values())
    assert [counts[d] for d in range(5)] == [1, 18, 243, 3240, 43239]


def test_u_turn_moves_front_row_to_left():
    # Seen from above, U turns clockwise: the front face's top row goes to the left face.
    after = apply_turn(SOLVED, "U")
    assert after[36:39] == "FFF"   # L face, top row
    assert after[18:21] == "RRR"   # F face, top row now shows R
    assert after[0:9] == "U" * 9


def test_solved_scores_20_and_48():
    assert pieces_in_place(SOLVED) == 20
    assert stickers_in_place(SOLVED) == 48


def test_one_quarter_turn_scores_12_and_36():
    # A quarter turn moves the 8 pieces of one layer; its own face keeps its colour, and the 12 stickers
    # on the four sides of the layer all leave their faces.
    for turn in ("U", "R'", "F"):
        cube = apply_turn(SOLVED, turn)
        assert pieces_in_place(cube) == 12
        assert stickers_in_place(cube) == 36


def test_solved_and_turned_cubes_are_valid():
    assert is_valid(SOLVED)
    assert all(is_valid(apply_turn(SOLVED, turn)) for turn in TURNS)


def test_flipped_edge_is_invalid():
    stickers = list(SOLVED)
    a, b = EDGES[1]   # the UF edge
    stickers[a], stickers[b] = stickers[b], stickers[a]
    assert not is_valid("".join(stickers))


def test_twisted_corner_is_invalid():
    stickers = list(SOLVED)
    a, b, c = CORNERS[0]   # the URF corner, turned a third in its place
    stickers[a], stickers[b], stickers[c] = SOLVED[c], SOLVED[a], SOLVED[b]
    assert not is_valid("".join(stickers))


def test_two_swapped_pieces_are_invalid():
    stickers = list(SOLVED)
    for i, j in zip(EDGES[0], EDGES[1]):   # swap the UR and UF edges, colours facing the same way
        stickers[i], stickers[j] = SOLVED[j], SOLVED[i]
    assert not is_valid("".join(stickers))


def test_impossible_sticker_strings_are_invalid():
    assert not is_valid(SOLVED[:-1])
    assert not is_valid(SOLVED.replace("U", "R", 1))     # a piece with colours no piece has
    assert not is_valid(SOLVED[:4] + "R" + SOLVED[5:13] + "U" + SOLVED[14:])  # two centres swapped
    mirrored = list(SOLVED)
    a, b, c = CORNERS[0]
    mirrored[b], mirrored[c] = SOLVED[c], SOLVED[b]       # a corner's colours in mirror order
    assert not is_valid("".join(mirrored))
    assert not is_valid(None)
    no_such_edge = list(SOLVED)
    no_such_edge[EDGES[1][1]] = "D"   # the UF edge shows U and D; a D sticker shows F instead
    no_such_edge[EDGES[5][0]] = "F"
    assert not is_valid("".join(no_such_edge))


def test_random_cubes_are_valid_and_reproducible():
    rng = random.Random(2026)
    cubes = [random_cube(rng) for _ in range(1000)]
    assert all(is_valid(cube) for cube in cubes)
    assert len(set(cubes)) == 1000
    again = random.Random(2026)
    assert [random_cube(again) for _ in range(1000)] == cubes


def _spread(counts, draws):
    """Chi-square of a table of counts against every cell being equally likely."""
    cells = [count for row in counts for count in row]
    expected = draws / len(counts[0])
    return sum((count - expected) ** 2 / expected for count in cells)


def test_random_cube_puts_every_piece_everywhere_equally_often():
    # Count, over 20,000 cubes, how often each place holds each piece, and each twist and flip. For a
    # uniform draw the chi-square is near its degrees of freedom (corners 49, edges 121, twists 16,
    # flips 12); the limits below are about twice that. A shuffle that swaps each position with any
    # other (a common biased shuffle) gives about 1,800 for corners and 3,100 for edges.
    draws = 20000
    rng = random.Random(1)
    corners = [[0] * 8 for _ in range(8)]
    edges = [[0] * 12 for _ in range(12)]
    twists = [[0] * 3 for _ in range(8)]
    flips = [[0] * 2 for _ in range(12)]
    for _ in range(draws):
        corner_order, corner_twists, edge_order, edge_flips = read_pieces(random_cube(rng))
        for place, piece in enumerate(corner_order):
            corners[place][piece] += 1
        for place, piece in enumerate(edge_order):
            edges[place][piece] += 1
        for place, twist in enumerate(corner_twists):
            twists[place][twist] += 1
        for place, flip in enumerate(edge_flips):
            flips[place][flip] += 1
    assert _spread(corners, draws) < 100
    assert _spread(edges, draws) < 240
    assert _spread(twists, draws) < 40
    assert _spread(flips, draws) < 30


def test_pieces_round_trip():
    rng = random.Random(3)
    for _ in range(200):
        cube = apply_turns(SOLVED, random_turns(rng, 20))
        assert cube_from_pieces(*read_pieces(cube)) == cube


def test_agrees_with_old_cube_model_on_1000_turn_sequences():
    rng = random.Random(11)
    for _ in range(1000):
        turns = random_turns(rng, rng.randrange(1, 30))
        new = apply_turns(SOLVED, turns)
        old = state_to_str(CUBE3, CUBE3.apply(str_to_state(CUBE3, SOLVED), turns))
        assert new == old
        assert (pieces_in_place(new), stickers_in_place(new)) == CUBE3.h(str_to_state(CUBE3, new))


def test_upside_down_cube_turns_the_same_way():
    rng = random.Random(9)
    assert turn_upside_down(SOLVED) == SOLVED
    for _ in range(100):
        cube, turns = random_cube(rng), random_turns(rng, 6)
        upside_down = turn_upside_down(cube)
        assert is_valid(upside_down)
        assert turn_upside_down(upside_down) == cube
        assert turn_upside_down(apply_turns(cube, turns)) == apply_turns(upside_down, [upside_down_turn(t) for t in turns])
