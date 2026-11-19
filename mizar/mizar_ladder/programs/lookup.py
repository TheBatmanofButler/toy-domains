"""Lookup: the option that is the held-back fact in the most training problems.

It is given, from the training problems, only the names of their held-back facts. Options held back equally often
share the weight; if none of a problem's 30 options was ever held back in training, the weight is equal on all 30.
"""
from collections import Counter

from mizar_ladder.problems import OPTIONS
from mizar_ladder.programs.common import check_training_problems, option_names, pick_best


def held_back_name(problem):
    return problem["options"][problem["held_back"] - 1]["name"]


def train(training_problems, counts):
    """{fact name: in how many training problems it is the held-back fact}."""
    check_training_problems(training_problems, counts.left_out)
    return Counter(held_back_name(p) for p in training_problems)


def picks(problems, trained):
    found = []
    for problem in problems:
        times = [trained.get(name, 0) for name in option_names(problem)]
        found.append(pick_best(times) if any(times) else [1.0 / OPTIONS] * OPTIONS)
    return found
