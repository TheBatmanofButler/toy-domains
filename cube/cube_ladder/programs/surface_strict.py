"""Surface reader, strict form: logistic regression from the stickers as they are now to a turn.

Input: 324 yes-or-no facts, one per sticker position and colour. Output: one of 18 turns, with separate
weights for each turn. It never sees the result of a turn. A training cube with several right turns counts
once per right turn, each copy weighted so the cube counts once in all. The strength of the one setting
(C, the inverse strength of the penalty on large weights) is chosen by cross-validation inside the training
set, using the experiment's own score. Trained on all distances mixed: a reader is not told the distance.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from cube_ladder.cube import TURNS
from cube_ladder.cube_rows import to_rows
from cube_ladder.programs.common import check_training_states, pick_best

STRENGTHS = (0.01, 0.1, 1.0, 10.0)


def features(cubes):
    """Row i, column 6 * position + colour is 1 when sticker `position` of cube i has that colour."""
    rows = to_rows(cubes)
    return np.eye(6, dtype=np.float32)[rows].reshape(len(cubes), 54 * 6)


def _training_rows(states):
    """One row per (state, right turn), weighted 1 / number of right turns; `groups` names the state."""
    cubes, answers, weights, groups = [], [], [], []
    for n, state in enumerate(states):
        for turn in state["right_turns"]:
            cubes.append(state["cube"])
            answers.append(TURNS.index(turn))
            weights.append(1.0 / len(state["right_turns"]))
            groups.append(n)
    return features(cubes), np.array(answers), np.array(weights), np.array(groups)


def _fit(x, answers, weights, strength):
    model = LogisticRegression(C=strength, max_iter=2000)
    return model.fit(x, answers, sample_weight=weights)


def _values(model, x):
    """Predicted probability of each of the 18 turns; turns never seen in training get 0."""
    values = np.zeros((len(x), len(TURNS)))
    values[:, model.classes_] = model.predict_proba(x)
    return values


def _mean_score(model, states):
    total = 0.0
    for state, values in zip(states, _values(model, features([s["cube"] for s in states]))):
        pick = pick_best(values.tolist())
        total += sum(weight for weight, turn in zip(pick, TURNS) if turn in state["right_turns"])
    return total / len(states)


def train(training_states, test_cubes, strengths=STRENGTHS, folds=5):
    """Returns {"model", "strength", "cross_validation": {strength: mean held-out score}}. `test_cubes`: the
    cubes of the test set, none of which may be in the training set."""
    check_training_states(training_states, test_cubes)
    x, answers, weights, groups = _training_rows(training_states)
    cross_validation = {}
    for strength in strengths:
        scores = []
        for fit_rows, _ in GroupKFold(n_splits=folds).split(x, answers, groups):
            held_out = sorted(set(range(len(training_states))) - set(groups[fit_rows].tolist()))
            model = _fit(x[fit_rows], answers[fit_rows], weights[fit_rows], strength)
            scores.append(_mean_score(model, [training_states[n] for n in held_out]))
        cross_validation[strength] = float(np.mean(scores))
    best = max(strengths, key=lambda s: cross_validation[s])  # the first listed wins a tie
    return {"model": _fit(x, answers, weights, best), "strength": best, "cross_validation": cross_validation}


def picks(cubes, trained):
    return [pick_best(values.tolist()) for values in _values(trained["model"], features(cubes))]
