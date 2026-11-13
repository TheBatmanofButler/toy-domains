"""Lookup: the substitution that is right most often in the training set, among those available.

For each substitution, count the training problems in which applying it to the equation is a right move, all
depths together. For a problem, pick the available substitution with the highest count (equal weight on ties).
This is also the reader that sees only the options: the options are nearly the same in every problem.
"""
from fe_ladder.identities import SUBSTITUTIONS
from fe_ladder.programs.common import check_training_problems, pick_best


def train(training_problems, test_problems):
    """{substitution: count}. `test_problems`: none of them may be in the training set."""
    check_training_problems(training_problems, test_problems)
    counts = {s: 0 for s in SUBSTITUTIONS}
    for problem in training_problems:
        for n in problem["right_moves"]:
            for number, substitution in problem["options"][n]["moves"]:
                if number == 1:
                    counts[substitution] += 1
    return counts


def picks(records, counts):
    # An option's value is the highest count among its moves, so ties between substitutions that give
    # different options share the weight, and two that give the same option count once.
    return [pick_best([max(counts[s] for _, s in o["moves"]) for o in r["options"]]) for r in records]
