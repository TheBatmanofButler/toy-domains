"""Surface reader, strict form: logistic regression from what is on the page before any move to a substitution.

Input: for each of the 40 commonest terms in the training set (counted over its equations and goals), whether
it is in the equation and whether it is in the goal; and the number of terms in each. Output: one of the 13
substitutions. It never sees the result of a substitution. A training problem with several right moves counts
once in all, shared equally among them, and a right option given by several substitutions shares its part
among them. A problem's value for an option is the total predicted for the substitutions that give it. The
strength of the one setting (C) is chosen by cross-validation inside the training set, using the experiment's
own score. Trained on all depths mixed: a reader is not told the depth.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from fe_ladder.identities import SUBSTITUTIONS, terms
from fe_ladder.identity_text import read_identity
from fe_ladder.programs.common import check_training_problems, pick_best, score

STRENGTHS = (0.01, 0.1, 1.0, 10.0)
COMMONEST = 40


def _terms_of(record):
    return terms(read_identity(record["equation"])), terms(read_identity(record["goal"]))


def commonest_terms(training_problems, how_many=COMMONEST):
    """The terms found in the most equations and goals of the training set; ties go to the earlier term."""
    counts = {}
    for record in training_problems:
        for found in _terms_of(record):
            for term in found:
                counts[term] = counts.get(term, 0) + 1
    return sorted(counts, key=lambda term: (-counts[term], term))[:how_many]


def features(records, chosen_terms):
    rows = []
    for record in records:
        equation_terms, goal_terms = _terms_of(record)
        rows.append([float(t in equation_terms) for t in chosen_terms] + [float(t in goal_terms) for t in chosen_terms]
                    + [float(len(equation_terms)), float(len(goal_terms))])
    return np.array(rows)


def _training_rows(records, chosen_terms):
    """One row per (problem, right option, substitution on the equation that gives it), with its share."""
    x = features(records, chosen_terms)
    rows, answers, weights, groups = [], [], [], []
    for n, record in enumerate(records):
        for position in record["right_moves"]:
            substitutions = [s for number, s in record["options"][position]["moves"] if number == 1]
            for s in substitutions:
                rows.append(x[n])
                answers.append(SUBSTITUTIONS.index(s))
                weights.append(1.0 / len(record["right_moves"]) / len(substitutions))
                groups.append(n)
    return np.array(rows), np.array(answers), np.array(weights), np.array(groups)


def _fit(x, answers, weights, strength):
    return LogisticRegression(C=strength, max_iter=2000).fit(x, answers, sample_weight=weights)


def _option_values(model, records, chosen_terms):
    # The model knows only the substitutions that were right somewhere in training: one never right there has
    # no class of its own, so it is given 0 here.
    probabilities = np.zeros((len(records), len(SUBSTITUTIONS)))
    probabilities[:, model.classes_] = model.predict_proba(features(records, chosen_terms))
    return [[sum(p[SUBSTITUTIONS.index(s)] for number, s in o["moves"] if number == 1) for o in record["options"]]
            for record, p in zip(records, probabilities)]


def _mean_score(model, records, chosen_terms):
    values = _option_values(model, records, chosen_terms)
    return float(np.mean([score(pick_best(v), r["right_moves"]) for v, r in zip(values, records)]))


def train(training_problems, test_problems, strengths=STRENGTHS, folds=5):
    """Returns {"model", "terms", "strength", "cross_validation": {strength: mean held-out score}}.
    `test_problems`: none of them may be in the training set."""
    check_training_problems(training_problems, test_problems)
    chosen_terms = commonest_terms(training_problems)
    x, answers, weights, groups = _training_rows(training_problems, chosen_terms)
    cross_validation = {}
    for strength in strengths:
        scores = []
        for fit_rows, _ in GroupKFold(n_splits=folds).split(x, answers, groups):
            held_out = sorted(set(range(len(training_problems))) - set(groups[fit_rows].tolist()))
            model = _fit(x[fit_rows], answers[fit_rows], weights[fit_rows], strength)
            scores.append(_mean_score(model, [training_problems[n] for n in held_out], chosen_terms))
        cross_validation[strength] = float(np.mean(scores))
    best = max(strengths, key=lambda s: cross_validation[s])  # the first listed wins a tie
    return {"model": _fit(x, answers, weights, best), "terms": chosen_terms, "strength": best,
            "cross_validation": cross_validation}


def picks(records, trained):
    return [pick_best(v) for v in _option_values(trained["model"], records, trained["terms"])]
