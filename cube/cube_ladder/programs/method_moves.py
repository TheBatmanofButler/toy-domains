"""Converts the scripted method's moves (speedcubing notation) to the 18 turns.

Speedcubing notation also has whole-cube rotations (x y z), wide turns (r, or Rw: two layers at once) and
middle-slice turns (M E S). Each of these equals a face turn plus a whole-cube rotation, and a rotation only
renames the faces for the moves after it. So the conversion keeps track of which face is where, writes every
move as a turn of a face in the cube's original position, and finally merges neighbouring turns of the same
face (also across a turn of the opposite face, which does not interfere). Ported from the old run's code.
"""
import re

OPPOSITE = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}
# What each rotation does to the faces: x turns the cube like R (the F face goes to U), y like U (the F
# face goes to L), z like F (the U face goes to R). Entries are {position: position its face comes from}.
_ROTATION = {"x": {"U": "F", "B": "U", "D": "B", "F": "D"},
             "y": {"L": "F", "B": "L", "R": "B", "F": "R"},
             "z": {"R": "U", "D": "R", "L": "D", "U": "L"}}
# Every move as parts (a face turn or a rotation, with its clockwise quarter turns: 1, or 3 for anticlockwise).
# A wide turn is the opposite face's turn plus a rotation (r = L and x); a middle-slice turn is two opposite
# face turns plus a rotation (M = L' R x'). The parts of one move share an axis, so their order does not matter.
_PARTS = {"r": [("L", 1), ("x", 1)], "l": [("R", 1), ("x", 3)], "u": [("D", 1), ("y", 1)],
          "d": [("U", 1), ("y", 3)], "f": [("B", 1), ("z", 1)], "b": [("F", 1), ("z", 3)],
          "M": [("L", 3), ("R", 1), ("x", 3)], "E": [("D", 3), ("U", 1), ("y", 3)], "S": [("F", 3), ("B", 1), ("z", 1)]}
_MOVE = re.compile(r"^([UDRLFBudrlfbxyzMES])(w?)(2'|2|'|)$")


def _quarter_turns(suffix):
    return {"": 1, "'": 3, "2": 2, "2'": 2}[suffix]


def _rotate(where, rotation, times):
    """`where[p]` is the original face now at position p; returns it after `times` quarter rotations."""
    for _ in range(times % 4):
        moved = dict(where)
        for target, source in _ROTATION[rotation].items():
            moved[target] = where[source]
        where = moved
    return where


def _add_turn(turns, face, quarters):
    """Add a turn to `turns` (pairs [face, quarter turns 1 to 3]), merging it into the last turn of the same
    face if only turns of the opposite face (which do not interfere) come after that one."""
    quarters %= 4   # 1 to 3: every part turns by at least a quarter
    i = len(turns) - 1
    while i >= 0 and turns[i][0] in (face, OPPOSITE[face]):
        if turns[i][0] == face:
            turns[i][1] = (turns[i][1] + quarters) % 4
            if turns[i][1] == 0:
                turns.pop(i)
            return
        i -= 1
    turns.append([face, quarters])


def to_turns(moves):
    """Moves (a list, or a string separated by spaces; brackets ignored) -> list of turn names."""
    if isinstance(moves, str):
        moves = moves.replace("(", " ").replace(")", " ").split()
    where = {face: face for face in "UDRLFB"}
    turns = []
    for move in moves:
        match = _MOVE.match(move)
        if not match:
            raise ValueError(f"cannot read move {move!r}")
        base, wide, suffix = match.groups()
        base = base.lower() if wide == "w" else base
        times = _quarter_turns(suffix)
        parts = _PARTS.get(base, [(base, 1)])
        for name, quarters in parts:
            if name in OPPOSITE:            # a face turn, written in the cube's original position
                _add_turn(turns, where[name], quarters * times)
        for name, quarters in parts:
            if name in _ROTATION:           # a rotation renames the faces for the moves after it
                where = _rotate(where, name, quarters * times)
    return [face + {1: "", 2: "2", 3: "'"}[quarters] for face, quarters in turns]
