"""Lookahead (search): try every sequence of up to `depth` turns and score where it leads.

Sequences never turn the same face twice running. If some sequence reaches the solved cube, the shortest
such sequences win and the search stops there. Otherwise the winners are the sequences of exactly `depth`
turns whose end cube has the most pieces in place, with stickers in place breaking ties. The pick is equal
weight on the distinct first turns of the winners. No solver is used.
"""
import numpy as np

from cube_ladder.cube import FACES, TURNS
from cube_ladder.cube_rows import apply_turn_to_rows, pieces_and_stickers_in_place_rows, solved_rows, to_rows
from cube_ladder.programs.common import pick_on

_FACE_NUMBER = np.array([FACES.index(turn[0]) for turn in TURNS])


def search(cube, depth):
    """Returns (pick, number of positions examined)."""
    if depth < 1:
        raise ValueError("depth must be at least 1")
    rows = to_rows([cube])
    first_turn = np.array([-1])   # index into TURNS of each sequence's first turn
    last_face = np.array([-1])    # face number of each sequence's last turn
    examined = 0
    for level in range(1, depth + 1):
        grown_rows, grown_first, grown_face = [], [], []
        for t, turn in enumerate(TURNS):
            allowed = last_face != _FACE_NUMBER[t]
            grown_rows.append(apply_turn_to_rows(rows[allowed], turn))
            grown_first.append(first_turn[allowed] if level > 1 else np.array([t]))
            grown_face.append(np.full(allowed.sum(), _FACE_NUMBER[t]))
        rows, first_turn, last_face = np.concatenate(grown_rows), np.concatenate(grown_first), np.concatenate(grown_face)
        examined += len(rows)
        solved = solved_rows(rows)
        if solved.any():
            return pick_on([TURNS[t] for t in set(first_turn[solved].tolist())]), examined
    pieces, stickers = pieces_and_stickers_in_place_rows(rows)
    value = pieces * 100 + stickers   # pieces first: stickers (at most 48) can never outweigh one piece
    winners = value == value.max()
    return pick_on([TURNS[t] for t in set(first_turn[winners].tolist())]), examined


def picks(cubes, depth):
    return [search(cube, depth)[0] for cube in cubes]
