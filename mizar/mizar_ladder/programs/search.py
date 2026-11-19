"""Search: for each option, the prover tries to prove the theorem from the given facts plus that option.

Reads the settled calls of prover_calls.jsonl. Equal weight on the options whose call proved the theorem; if
there is none, or the call without an option proved it, equal weight on all 30. It does not ask whether the
option is used in the proof. A call that did not decide (unsettled ones included) is not a success.
"""
from mizar_ladder import prover
from mizar_ladder.programs.common import pick_on
from mizar_ladder.problems import OPTIONS
from mizar_ladder.settle import decided


def picks(problems, calls):
    by_problem = {}
    for record in calls:
        by_problem.setdefault(record["problem_id"], {})[record["option"]] = record
    found = []
    for problem in problems:
        mine = by_problem[problem["id"]]

        def proved(option):
            return option in mine and decided(mine[option]) and mine[option]["ending"] == prover.PROVED
        working = [n for n in range(1, OPTIONS + 1) if proved(n)]
        found.append(pick_on(range(1, OPTIONS + 1)) if proved(None) or not working else pick_on(working))
    return found
