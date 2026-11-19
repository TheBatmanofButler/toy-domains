"""Options only: a reader trained on the options alone, never shown the theorem or the given facts.

Logistic regression predicting "this option is the held-back one" from the option alone: its length, its number
of different symbols, its citation count, how many facts stand between it and the start of its article, and its
rank among the 30 on each of those. The pick is the option with the highest value. Its one setting keeps
scikit-learn's default strength (C = 1); the features are put on one scale first.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from mizar_ladder import statements
from mizar_ladder.programs.common import check_training_problems, option_names, pick_best, ranks

FEATURES = ("length", "different_symbols", "citations", "from_article_start")


def option_view(problem, counts):
    """All this reader is given about a problem: per option, the four numbers; and, for training, which option
    is the held-back one. Nothing about the theorem or the given facts is kept."""
    own = problem["theorem"]       # used only to leave the problem's own theorem out of the citation count
    view = {"options": [{"length": statements.length(counts.statement[name]),
                         "different_symbols": len(counts.symbols[name]),
                         "citations": counts.citations(name, own=own),
                         "from_article_start": counts.from_article_start(name)} for name in option_names(problem)]}
    if "held_back" in problem:
        view["held_back"] = problem["held_back"]
    return view


def features(view):
    """One row per option: the four numbers, then the option's rank among the 30 on each. Refuses anything
    that carries the theorem or the given facts."""
    unexpected = set(view) - {"options", "held_back"}
    if unexpected:
        raise ValueError(f"the options-only reader is never given the theorem or the given facts: {sorted(unexpected)}")
    columns = [[option[name] for option in view["options"]] for name in FEATURES]
    return np.array([list(row) for row in zip(*columns, *map(ranks, columns))], dtype=float)


def labels(problem):
    return [int(n == problem["held_back"]) for n in range(1, len(problem["options"]) + 1)]


def fit(rows, targets, strength):
    model = make_pipeline(StandardScaler(), LogisticRegression(C=strength, max_iter=2000))
    model.fit(np.vstack(rows), np.concatenate(targets))
    return model


def best_options(model, rows):
    return [pick_best(list(model.decision_function(r))) for r in rows]


def train(training_problems, counts, strength=1.0):
    check_training_problems(training_problems, counts.left_out)
    rows = [features(option_view(p, counts)) for p in training_problems]
    return {"model": fit(rows, [labels(p) for p in training_problems], strength), "strength": strength}


def picks(problems, trained, counts):
    return best_options(trained["model"], [features(option_view(p, counts)) for p in problems])
