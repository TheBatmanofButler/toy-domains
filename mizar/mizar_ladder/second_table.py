"""The second table: the same answers and picks scored with the prover's key, on the problems where it has one.

Over the problems in the bin "has right options": every program's and the model's score under the prover's key,
under "right by either key", and under the author's key on those same problems, each with its standard error,
and the model minus each program on the same problems; `search` is left out, since under the prover's key it is
the judge itself. Then how the keys relate: how often the held-back option is right under the prover's key, how
many of the other 29 are per problem on average, and how many option calls proved the theorem without the option
in the proof; and the counts of the four prover bins, with the share of the key's calls on which the prover's two
runs disagreed (from settled.json). Numbers only: no rule about a changed position is here.
"""
from mizar_ladder import scoring
from mizar_ladder.prover_key import BINS, HAS_RIGHT

KEYS = ("prover", "either", "author")


def _rights(problem, line):
    held = problem["held_back"]
    return {"prover": set(line["right"]), "either": set(line["right"]) | {held}, "author": {held}}


def _figures(values):
    return {"mean": sum(values) / len(values) if values else None, "standard_error": scoring.standard_error(values)}


def second_table(test_problems, program_picks, answers, prover_key, tries=5, runs_disagreed=None):
    """`runs_disagreed` is settled.json's share of unsettled calls, shown beside the bins."""
    key = {line["problem_id"]: line for line in prover_key}
    if set(key) != {p["id"] for p in test_problems}:
        raise scoring.ScoringError("the prover's key does not cover exactly the test problems")
    here = [p for p in test_problems if key[p["id"]]["bin"] == HAS_RIGHT]
    rights = {p["id"]: _rights(p, key[p["id"]]) for p in here}
    model = {}
    # Every answer is checked as scoring does (each try there once, none failed); then read afresh here.
    scoring.model_right_counts(test_problems, answers, tries)
    grouped = scoring.by_problem(answers, test_problems, "answer")
    for p in here:
        options = [scoring.model_option(a) for a in grouped[p["id"]]]
        model[p["id"]] = {k: sum(o in rights[p["id"]][k] for o in options) / tries for k in KEYS}
    scoring.program_scores(test_problems, program_picks)      # the same checks on the picks as the scores get
    programs = {}
    for record in program_picks:
        if record["program"] != "search" and record["problem_id"] in rights:
            right = rights[record["problem_id"]]
            programs.setdefault(record["program"], {})[record["problem_id"]] = {
                k: scoring.score_pick(record["weights"], right[k]) for k in KEYS}
    ids = [p["id"] for p in here]
    table = {"bins": {name: sum(line["bin"] == name for line in prover_key) for name in BINS},
             "runs_disagreed_share": runs_disagreed,
             "problems": len(here),
             "model": {k: _figures([model[i][k] for i in ids]) for k in KEYS},
             "programs": {name: {k: _figures([scores[i][k] for i in ids]) for k in KEYS}
                          for name, scores in sorted(programs.items())},
             "model_minus_program": {name: {k: _figures([model[i][k] - scores[i][k] for i in ids]) for k in KEYS}
                                     for name, scores in sorted(programs.items())}}
    table["held_back_right_share"] = (sum(p["held_back"] in key[p["id"]]["right"] for p in here) / len(here)
                                      if here else None)
    table["other_right_mean"] = (sum(len(set(key[p["id"]]["right"]) - {p["held_back"]}) for p in here) / len(here)
                                 if here else None)
    table["proved_without_use_calls"] = sum(len(key[i]["proved_without_use"]) for i in ids)
    return table
