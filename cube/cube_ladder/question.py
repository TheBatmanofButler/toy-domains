"""The text the model is shown for one cube.

Everything up to the sticker string is the old run's layout, unchanged: the role line (SYSTEM_TEXT), the colour
scheme, the meaning of each turn, the 18 allowed turns, the flat drawing and the sticker string in colour
letters. The last paragraph states the rule for a right turn. The text depends on the cube only: it never
contains the distance or the right turns.
"""
COLOUR_OF_FACE = {"U": "W", "D": "Y", "F": "G", "B": "B", "R": "R", "L": "O"}

SYSTEM_TEXT = "You are an expert Rubik's cube solver. Follow the requested answer format exactly."

COLOUR_LINE = ("Colour scheme: the centre sticker of each face fixes its colour and never moves: "
               "U (up) = white W, D (down) = yellow Y, F (front) = green G, B (back) = blue B, "
               "R (right) = red R, L (left) = orange O.")
TURN_LINES = ("Moves: U, D, R, L, F, B each turn that face 90 degrees clockwise as seen looking directly at that face; "
              "X' is the 90 degree counterclockwise turn and X2 the 180 degree turn.\n"
              "The allowed moves are exactly: U U' U2 D D' D2 R R' R2 L L' L2 F F' F2 B B' B2 (no whole-cube rotations).")
RULE = ("A move is correct if it is the first move of a shortest possible solution. Each of the 18 allowed moves "
        "counts as one move, so a 180 degree turn counts as one. Give one correct move, written exactly as it "
        "appears in the list of allowed moves. Answer with `MOVE: <move>`.")


def colours(cube):
    return "".join(COLOUR_OF_FACE[c] for c in cube)


def flat_drawing(cube):
    """The cross-shaped net: U above F; L F R B in a row; D below F. Each face is drawn as three rows of three
    colour letters; blocks are 5 characters wide, 3 spaces apart."""
    faces = {name: colours(cube[9 * i:9 * i + 9]) for i, name in enumerate("URFDLB")}

    def row(face, r):
        return " ".join(faces[face][3 * r:3 * r + 3])

    pad = " " * 8
    lines = [pad + "  U"] + [pad + row("U", r) for r in range(3)]
    lines.append("  L" + " " * 5 + "  F" + " " * 5 + "  R" + " " * 5 + "  B")
    lines += ["   ".join(row(face, r) for face in "LFRB") for r in range(3)]
    lines += [pad + "  D"] + [pad + row("D", r) for r in range(3)]
    return "\n".join(lines)


def build_question(cube):
    return ("Here is a 3x3x3 Rubik's cube.\n\n"
            f"{COLOUR_LINE}\n{TURN_LINES}\n\n"
            f"Net (each face seen from outside):\n{flat_drawing(cube)}\n"
            "Facelet string (colour letters; faces in the order U R F D L B, 9 stickers each, read row by row as in the net):\n"
            f"{colours(cube)}\n\n"
            f"{RULE}")
