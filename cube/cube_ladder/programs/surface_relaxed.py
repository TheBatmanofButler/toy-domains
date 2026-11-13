"""Surface reader, relaxed form: the old run's reader, which sees whole-cube counts before and after each turn.

For each cube and turn: 18 counts describing the cube now, the same counts after the turn, their
differences, which face turns and which kind of turn it is (63 numbers). A logistic regression predicts
"this turn is right"; the pick is the turn with the highest predicted value. Seeing the cube after each
turn is one turn of lookahead with a learned score, which is why this form is labelled relaxed. The
settings are the old run's: standardised inputs and C = 1.0. Trained on all distances mixed.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cube_ladder.cube import CORNERS, EDGES, FACES, NON_CENTRES, TURNS
from cube_ladder.cube_rows import SOLVED_ROW, apply_turn_to_rows, pieces_and_stickers_in_place_rows, to_rows
from cube_ladder.programs.common import check_training_states, pick_best

COUNT_NAMES = (["pieces", "stickers"] + [f"face_{f}" for f in FACES] + ["corners", "edges", "twist", "flip"]
               + [f"cross_{f}" for f in FACES])
FEATURE_NAMES = ([f"before_{n}" for n in COUNT_NAMES] + [f"after_{n}" for n in COUNT_NAMES]
                 + [f"change_{n}" for n in COUNT_NAMES] + [f"face_is_{f}" for f in FACES]
                 + ["turn_clockwise", "turn_anticlockwise", "turn_half"])
_U, _D, _F, _B = (FACES.index(f) for f in "UDFB")
_FACE_STICKERS = [[i for i in NON_CENTRES if i // 9 == f] for f in range(6)]
# The four edges with a sticker on each face; all four in place make that face's "cross".
_CROSS_EDGES = [[e for e, edge in enumerate(EDGES) if any(i // 9 == f for i in edge)] for f in range(6)]


def counts(rows):
    """The 18 counts of COUNT_NAMES for each cube (rows from cube.to_rows)."""
    home = rows == SOLVED_ROW
    corners_home = home[:, np.array(CORNERS)].all(axis=2)
    edges_home = home[:, np.array(EDGES)].all(axis=2)
    pieces, stickers = pieces_and_stickers_in_place_rows(rows)
    columns = [pieces, stickers] + [home[:, _FACE_STICKERS[f]].sum(axis=1) for f in range(6)]
    columns += [corners_home.sum(axis=1), edges_home.sum(axis=1)]
    # Twist: corners whose U-or-D place sticker does not show U or D.
    corner_reference = rows[:, [corner[0] for corner in CORNERS]]
    columns.append(((corner_reference != _U) & (corner_reference != _D)).sum(axis=1))
    # Flip: the edge's reference sticker (U or D place, else F or B place) should show the edge's U or D
    # colour if it has one, else its F or B colour.
    edge_colours = rows[:, np.array(EDGES)]
    has_up_or_down = ((edge_colours == _U) | (edge_colours == _D)).any(axis=2)
    reference = edge_colours[:, :, 0]
    good = np.where(has_up_or_down, (reference == _U) | (reference == _D), (reference == _F) | (reference == _B))
    columns.append((~good).sum(axis=1))
    columns += [edges_home[:, _CROSS_EDGES[f]].all(axis=1) for f in range(6)]
    return np.stack(columns, axis=1).astype(np.float64)


def features(cubes):
    """Array (cubes, 18 turns, 63 numbers) in the order of FEATURE_NAMES."""
    rows = to_rows(cubes)
    before = counts(rows)
    blocks = []
    for turn in TURNS:
        after = counts(apply_turn_to_rows(rows, turn))
        which_face = np.zeros((len(cubes), 6))
        which_face[:, FACES.index(turn[0])] = 1
        kind = np.zeros((len(cubes), 3))
        kind[:, {"": 0, "'": 1, "2": 2}[turn[1:]]] = 1
        blocks.append(np.concatenate([before, after, after - before, which_face, kind], axis=1))
    return np.stack(blocks, axis=1)


def train(training_states, test_cubes):
    """`test_cubes`: the cubes of the test set, none of which may be in the training set."""
    check_training_states(training_states, test_cubes)
    x = features([s["cube"] for s in training_states])
    right = np.array([[turn in s["right_turns"] for turn in TURNS] for s in training_states])
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000))
    return model.fit(x.reshape(-1, x.shape[2]), right.reshape(-1).astype(int))


def picks(cubes, model):
    x = features(cubes)
    values = model.predict_proba(x.reshape(-1, x.shape[2]))[:, 1].reshape(len(cubes), len(TURNS))
    return [pick_best(row.tolist()) for row in values]
