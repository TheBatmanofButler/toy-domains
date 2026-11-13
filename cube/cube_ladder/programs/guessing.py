"""Guessing: equal weight on all 18 turns. Its score on a cube is the share of turns that are right."""
from cube_ladder.cube import TURNS
from cube_ladder.programs.common import pick_on


def picks(cubes):
    return [pick_on(TURNS) for _ in cubes]
