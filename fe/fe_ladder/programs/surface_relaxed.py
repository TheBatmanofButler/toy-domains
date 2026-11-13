"""Surface reader, relaxed form: the earlier run's reader, which also sees the result of each move.

For each option: which substitution (that of its first move), the number of terms on the page before and after
the move, how many of the goal's terms are present after, whether the substitution brings in a constant, and
how many f(...) terms and how many powers the result has. A logistic regression predicts "this move is right";
the pick is the option with the highest predicted value. Seeing each result is one move of lookahead with a
learned score, which is why this form is labelled relaxed. The settings are the earlier run's: standardised
inputs and C = 1.0. Trained on all depths mixed. The earlier run's inputs also held whether the move was on a
derived identity and how many moves had been made; both are always 0 on the page of the equation, so they are
left out.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fe_ladder.identities import BRING_IN_A_CONSTANT, F_TERM, SUBSTITUTIONS, terms
from fe_ladder.identity_text import read_identity
from fe_ladder.programs.common import check_training_problems, pick_best

FEATURE_NAMES = ([f"substitution {s}" for s in SUBSTITUTIONS]
                 + ["terms before", "terms after", "goal terms present after", "brings in a constant",
                    "f terms in result", "powers in result"])


def option_features(record):
    """One row per option, in the order of FEATURE_NAMES."""
    before = terms(read_identity(record["equation"]))
    goal = terms(read_identity(record["goal"]))
    rows = []
    for option in record["options"]:
        substitution = option["moves"][0][1]
        result = terms(read_identity(option["result"]))
        after = before | result
        f_terms = sum(1 for t in result if t[0] == F_TERM)
        which = [float(s == substitution) for s in SUBSTITUTIONS]
        rows.append(which + [float(len(before)), float(len(after)), float(len(goal & after)),
                             float(substitution in BRING_IN_A_CONSTANT), float(f_terms), float(len(result) - f_terms)])
    return np.array(rows)


def train(training_problems, test_problems):
    """`test_problems`: none of them may be in the training set."""
    check_training_problems(training_problems, test_problems)
    x = np.vstack([option_features(r) for r in training_problems])
    right = np.concatenate([[n in r["right_moves"] for n in range(len(r["options"]))] for r in training_problems])
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000))
    return model.fit(x, right.astype(int))


def picks(records, model):
    return [pick_best(model.predict_proba(option_features(r))[:, 1].tolist()) for r in records]
