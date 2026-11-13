"""Guessing: equal weight on every option. Its score on a problem is the share of options that are right."""
from fe_ladder.programs.common import pick_on


def picks(records):
    return [pick_on(len(r["options"]), range(len(r["options"]))) for r in records]
