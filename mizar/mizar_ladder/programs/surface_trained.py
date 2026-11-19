"""Surface, trained: a reader trained on the theorem, the given facts and the options.

Logistic regression predicting "this option is the held-back one" from everything the options-only reader sees,
and: the shared-symbol sum with the theorem and with the given facts; the share of the option's symbols that are
in the theorem; the number of other theorems that cite the option together with at least one given fact; the
number of facts between the option and the theorem; and the option's rank among the 30 on each of these. The
strength of its one setting (C, the inverse strength of the penalty on large weights) is chosen by cross-validation
inside the training set, splitting by article, using the experiment's own score.
"""
import numpy as np
from sklearn.model_selection import GroupKFold

from mizar_ladder.programs import options_only
from mizar_ladder.programs.common import check_training_problems, option_names, ranks

STRENGTHS = (0.01, 0.1, 1.0, 10.0, 100.0)
FOLDS = 5


def features(problem, counts):
    own = problem["theorem"]
    given = [g["name"] for g in problem["given"]]
    theorem_symbols = counts.symbols[own]
    extra = [[], [], [], [], []]
    for name in option_names(problem):
        mine = counts.symbols[name]
        values = (counts.shared_sum(name, [own], own=own), counts.shared_sum(name, given, own=own),
                  len(mine & theorem_symbols) / len(mine) if mine else 0.0,
                  counts.cited_with(name, given, own=own), counts.between(name, own))
        for column, value in zip(extra, values):
            column.append(value)
    added = np.array([list(row) for row in zip(*extra, *map(ranks, extra))], dtype=float)
    return np.hstack([options_only.features(options_only.option_view(problem, counts)), added])


def mean_score(model, rows, problems):
    """The mean weight the picks put on the held-back option."""
    return float(np.mean([pick[p["held_back"] - 1] for pick, p in zip(options_only.best_options(model, rows), problems)]))


def cross_validation(rows, problems, strengths=STRENGTHS, folds=FOLDS):
    """{strength: mean score on the held-out articles}, splitting the training problems by article."""
    groups = [p["article"] for p in problems]
    splits = list(GroupKFold(n_splits=min(folds, len(set(groups)))).split(rows, groups=groups))
    targets = [options_only.labels(p) for p in problems]
    found = {}
    for strength in strengths:
        scores = []
        for inside, outside in splits:
            model = options_only.fit([rows[i] for i in inside], [targets[i] for i in inside], strength)
            scores.append(mean_score(model, [rows[i] for i in outside], [problems[i] for i in outside]))
        found[strength] = float(np.mean(scores))
    return found


def train(training_problems, counts, strengths=STRENGTHS):
    """The model trained on every training problem at the strength that scored best across articles (of equal
    scores, the first listed: the smallest C, which holds the weights closest to zero)."""
    check_training_problems(training_problems, counts.left_out)
    rows = [features(p, counts) for p in training_problems]
    tried = cross_validation(rows, training_problems, strengths)
    strength = max(strengths, key=lambda s: tried[s])
    model = options_only.fit(rows, [options_only.labels(p) for p in training_problems], strength)
    return {"model": model, "strength": strength, "cross_validation": tried}


def picks(problems, trained, counts):
    return options_only.best_options(trained["model"], [features(p, counts) for p in problems])
