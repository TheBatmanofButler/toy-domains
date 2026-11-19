"""Guessing: equal weight on all 30 options."""
from mizar_ladder.problems import OPTIONS


def picks(problems):
    return [[1.0 / OPTIONS] * OPTIONS for _ in problems]
