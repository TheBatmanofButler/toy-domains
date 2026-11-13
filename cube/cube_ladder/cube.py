"""The cube and its turns. This is the only file that knows how a turn moves stickers.

A cube is a string of 54 letters, faces in the order U R F D L B, nine stickers per face read row by row
as in the flat drawing; each letter names the face whose colour the sticker has. The turns are worked
out once, from the position of every sticker in space, so no sticker cycle is typed in by hand.
(cube_rows.py does the same operations on many cubes at once, using the turns worked out here.)
"""
FACES = "URFDLB"
SOLVED = "".join(face * 9 for face in FACES)
TURNS = ("U", "U'", "U2", "D", "D'", "D2", "R", "R'", "R2",
         "L", "L'", "L2", "F", "F'", "F2", "B", "B'", "B2")

# Space is measured from the cube's centre: x grows towards R, y towards U, z towards F.
NORMAL = {"U": (0, 1, 0), "R": (1, 0, 0), "F": (0, 0, 1), "D": (0, -1, 0), "L": (-1, 0, 0), "B": (0, 0, -1)}


def _sticker_position(face, row, col):
    """Centre of the small cube a sticker sits on (each coordinate -1, 0 or 1), from its row and column in
    the flat drawing (0 to 2, from the top left). Each face is drawn as seen from outside. Side faces have
    U above (a lower row lowers y); along a row F runs L to R, R runs F to B, B runs R to L, L runs B to F.
    U is seen from above with B at the top; D from below with F at the top."""
    return {"U": (col - 1, 1, row - 1), "R": (1, 1 - row, 1 - col), "F": (col - 1, 1 - row, 1),
            "D": (col - 1, -1, 1 - row), "L": (-1, 1 - row, col - 1), "B": (1 - col, 1 - row, -1)}[face]


# Every sticker as (position of its small cube, direction it faces), in the order of the 54 letters.
STICKERS = [(_sticker_position(face, i // 3, i % 3), NORMAL[face]) for face in FACES for i in range(9)]
_INDEX = {sticker: i for i, sticker in enumerate(STICKERS)}


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _clockwise(vector, axis):
    """Quarter turn of `vector`, clockwise as seen looking at the cube from the tip of `axis`.

    Rodrigues' formula, v cos t + (a x v) sin t + a (a . v)(1 - cos t), turns anticlockwise seen from the
    tip of a for positive t; clockwise is t = -90 degrees: v' = (a . v) a - a x v. Check: for U the
    front-top edge (0, 1, 1) goes to (-1, 1, 0), the left-top edge, as U moves the front to the left."""
    along = sum(a * v for a, v in zip(axis, vector))
    across = _cross(axis, vector)
    return tuple(along * a - c for a, c in zip(axis, across))


def _quarter_turn_sources(face):
    """sources[j] = the index of the sticker that a clockwise quarter turn of `face` brings to place j."""
    axis = NORMAL[face]
    sources = list(range(54))
    for i, (position, normal) in enumerate(STICKERS):
        if sum(a * p for a, p in zip(axis, position)) == 1:  # the sticker is in the turning layer
            sources[_INDEX[(_clockwise(position, axis), _clockwise(normal, axis))]] = i
    return sources


def _done_twice_or_three_times(sources, times):
    """The sources of doing the same quarter turn `times` times in a row."""
    combined = list(range(54))
    for _ in range(times):
        combined = [combined[i] for i in sources]
    return combined


def _all_turn_sources():
    """{turn name: sources}. A half turn is two quarter turns, an anticlockwise turn three."""
    sources = {}
    for face in FACES:
        quarter = _quarter_turn_sources(face)
        sources[face] = quarter
        sources[face + "2"] = _done_twice_or_three_times(quarter, 2)
        sources[face + "'"] = _done_twice_or_three_times(quarter, 3)
    return sources


SOURCES = _all_turn_sources()


def apply_turn(cube, turn):
    return "".join([cube[i] for i in SOURCES[turn]])


def apply_turns(cube, turns):
    """`turns` is a list of turn names, or one string with names separated by spaces."""
    if isinstance(turns, str):
        turns = turns.split()
    for turn in turns:
        cube = apply_turn(cube, turn)
    return cube


def inverse_turn(turn):
    return turn[0] + {"": "'", "'": "", "2": "2"}[turn[1:]]


def inverse_turns(turns):
    """The sequence that undoes `turns`."""
    return [inverse_turn(turn) for turn in reversed(list(turns))]


# Holding the whole cube upside down (a half turn about the R-L axis) swaps U with D and F with B.
# The scripted method always builds its first layer on one face; this lets it build on the other.
_UPSIDE_DOWN_FACE = {"U": "D", "D": "U", "F": "B", "B": "F", "R": "R", "L": "L"}
_UPSIDE_DOWN_DESTINATION = [_INDEX[((p[0], -p[1], -p[2]), (n[0], -n[1], -n[2]))] for p, n in STICKERS]


def turn_upside_down(cube):
    """The same cube held upside down, with letters renamed so that each centre again names its face."""
    stickers = [""] * 54
    for i, destination in enumerate(_UPSIDE_DOWN_DESTINATION):
        stickers[destination] = _UPSIDE_DOWN_FACE[cube[i]]
    return "".join(stickers)


def upside_down_turn(turn):
    """The turn that does to the upside-down cube what `turn` does to the cube."""
    return _UPSIDE_DOWN_FACE[turn[0]] + turn[1:]


# The 20 movable pieces, as sticker indices, in the usual Kociemba order. Every corner lists its
# U or D sticker first and goes round the corner the same way, so a corner's twist is simply where
# its U or D colour sits. Every edge lists first its U or D sticker, or for the four middle-layer
# edges its F or B sticker.
CORNERS = ((8, 9, 20), (6, 18, 38), (0, 36, 47), (2, 45, 11),
           (29, 26, 15), (27, 44, 24), (33, 53, 42), (35, 17, 51))
EDGES = ((5, 10), (7, 19), (3, 37), (1, 46), (32, 16), (28, 25),
         (30, 43), (34, 52), (23, 12), (21, 41), (50, 39), (48, 14))
CORNER_COLOURS = tuple("".join(SOLVED[i] for i in corner) for corner in CORNERS)
EDGE_COLOURS = tuple("".join(SOLVED[i] for i in edge) for edge in EDGES)
NON_CENTRES = tuple(i for i in range(54) if i % 9 != 4)


def _turned_corner(colours, twist):
    """A corner's colours as read in its place when it is twisted: its U or D colour is read at position
    `twist` instead of first, the others following round the corner in the same order."""
    return "".join(colours[(k - twist) % 3] for k in range(3))


def read_pieces(cube):
    """(corner_order, twists, edge_order, flips): which piece sits in each place and how it is turned.
    Returns None if some place holds colours that no real piece has."""
    corner_order, twists = [], []
    for corner in CORNERS:
        letters = "".join(cube[i] for i in corner)
        found = [(piece, twist) for piece, colours in enumerate(CORNER_COLOURS) for twist in range(3)
                 if letters == _turned_corner(colours, twist)]
        if not found:
            return None
        corner_order.append(found[0][0])
        twists.append(found[0][1])
    edge_order, flips = [], []
    for edge in EDGES:
        letters = "".join(cube[i] for i in edge)
        found = [(piece, flip) for piece, colours in enumerate(EDGE_COLOURS) for flip in range(2)
                 if letters == (colours if flip == 0 else colours[::-1])]
        if not found:
            return None
        edge_order.append(found[0][0])
        flips.append(found[0][1])
    return corner_order, twists, edge_order, flips


def _parity(order):
    """0 if the arrangement takes an even number of swaps to put right, 1 if odd."""
    order, swaps = list(order), 0
    for i in range(len(order)):
        while order[i] != i:
            j = order[i]
            order[i], order[j] = order[j], order[i]
            swaps += 1
    return swaps % 2


def is_valid(cube):
    """True only for cubes that can be reached from solved by turning."""
    if not isinstance(cube, str) or len(cube) != 54 or cube[4::9] != FACES:
        return False
    pieces = read_pieces(cube)
    if pieces is None:
        return False
    corner_order, twists, edge_order, flips = pieces
    return (sorted(corner_order) == list(range(8)) and sorted(edge_order) == list(range(12))
            and sum(twists) % 3 == 0 and sum(flips) % 2 == 0
            and _parity(corner_order) == _parity(edge_order))


def cube_from_pieces(corner_order, twists, edge_order, flips):
    """The sticker string of a cube described piece by piece (the inverse of reading the pieces)."""
    stickers = list(SOLVED)
    for place, (piece, twist) in enumerate(zip(corner_order, twists)):
        for i, letter in zip(CORNERS[place], _turned_corner(CORNER_COLOURS[piece], twist)):
            stickers[i] = letter
    for place, (piece, flip) in enumerate(zip(edge_order, flips)):
        colours = EDGE_COLOURS[piece] if flip == 0 else EDGE_COLOURS[piece][::-1]
        for k, i in enumerate(EDGES[place]):
            stickers[i] = colours[k]
    return "".join(stickers)


def random_cube(rng):
    """A valid cube, every valid cube equally likely. `rng` is a random.Random.

    Draw the corners and the edges in any order and the first 7 twists and 11 flips freely; the last
    twist and flip are then forced. If the two orders have different parity, swapping the last two edges
    fixes it; this pairs the arrangements two to one, so every valid cube stays equally likely."""
    corner_order = rng.sample(range(8), 8)
    edge_order = rng.sample(range(12), 12)
    if _parity(corner_order) != _parity(edge_order):
        edge_order[10], edge_order[11] = edge_order[11], edge_order[10]
    twists = [rng.randrange(3) for _ in range(7)]
    twists.append(-sum(twists) % 3)
    flips = [rng.randrange(2) for _ in range(11)]
    flips.append(sum(flips) % 2)
    return cube_from_pieces(corner_order, twists, edge_order, flips)


def pieces_in_place(cube):
    """Corners and edges (0 to 20) whose every sticker shows its own face's colour."""
    return sum(all(cube[i] == SOLVED[i] for i in piece) for piece in CORNERS + EDGES)


def stickers_in_place(cube):
    """Stickers (0 to 48, centres not counted) showing their own face's colour."""
    return sum(cube[i] == SOLVED[i] for i in NON_CENTRES)
