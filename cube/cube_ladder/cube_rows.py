"""The cube's operations on many cubes at once, as rows of a numpy array of face numbers (0 to 5 for U R F D L B).

Lookahead and the relaxed surface reader need this for speed. The turns themselves come from cube.py
(cube.SOURCES); nothing here works out how a turn moves stickers. Tests check that every function here
agrees with its string form in cube.py.
"""
import numpy as np

from cube_ladder.cube import CORNERS, EDGES, FACES, SOLVED, SOURCES

SOLVED_ROW = np.array([FACES.index(c) for c in SOLVED], dtype=np.uint8)
_SOURCE_ARRAYS = {turn: np.array(sources) for turn, sources in SOURCES.items()}
_CORNER_ARRAY, _EDGE_ARRAY = np.array(CORNERS), np.array(EDGES)


def to_rows(cubes):
    return np.array([[FACES.index(c) for c in cube] for cube in cubes], dtype=np.uint8).reshape(-1, 54)


def from_row(row):
    return "".join(FACES[i] for i in row)


def apply_turn_to_rows(rows, turn):
    return rows[:, _SOURCE_ARRAYS[turn]]


def solved_rows(rows):
    return (rows == SOLVED_ROW).all(axis=1)


def pieces_and_stickers_in_place_rows(rows):
    home = rows == SOLVED_ROW
    pieces = home[:, _CORNER_ARRAY].all(axis=2).sum(axis=1) + home[:, _EDGE_ARRAY].all(axis=2).sum(axis=1)
    stickers = home.sum(axis=1) - 6  # the six centres never move
    return pieces, stickers
