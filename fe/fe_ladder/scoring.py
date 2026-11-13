"""Every figure in the report is worked out here, and only here.

Scores: a pick scores the weight it puts on right moves; a model try scores 1 if its move is right. A problem's
model score is the share of its tries that are right; a depth's score is the average over its problems.
Room at a depth is one minus the best simple program there. Problem by problem, the model "gets" a problem when
more than half its tries are right (3 of 5), and a program gets it when more than half its weight is on right
moves; the same bar for both. The model's moves are read afresh from its answer text, so the answer reader
can change without asking the model again. The options differ from problem to problem, so a pick's weights
and a move are matched to the problem's options by number.

Margins of error are given as numbers only; nothing here decides what counts as "above". A standard error is
the sample standard deviation (n - 1 in the divisor) of the per-problem figures over the square root of the
number of problems; with one problem there is none (None). It reflects the choice of test problems only.
"""
from math import comb, sqrt
from statistics import stdev

from fe_ladder.answers import option_of, read_move

# Each search program's budget, in its own units: move sequences examined (lookahead) or identities worked out
# (narrow-and-deep). A pick record carries one of them.
SEARCH_BUDGETS = ("sequences_examined", "identities_worked_out")
# Scores closer than this are tied (they are averages of the same few fractions).
TIE = 1e-12


class ScoringError(Exception):
    pass


def score_pick(weights, right_moves, option_count):
    if len(weights) != option_count or abs(sum(weights) - 1) > 1e-9 or min(weights) < 0:
        raise ScoringError(f"not a pick: {weights}")
    return sum(weights[n] for n in right_moves)


def _by_problem(records, test_problems, kind):
    """Group records by their `problem_id`; every test problem must be there. `kind` names the records in errors."""
    grouped = {s["id"]: [] for s in test_problems}
    for record in records:
        if record["problem_id"] not in grouped:
            raise ScoringError(f"{kind} for {record['problem_id']}, which is not a test problem")
        grouped[record["problem_id"]].append(record)
    return grouped


def model_move(answer):
    """The move read from a saved answer's text (None if unreadable or the request failed)."""
    return None if answer["failed"] else read_move(answer["answer_text"])


def model_option(answer, problem):
    """The option of `problem` that the saved answer's move belongs to (None if unreadable or not available)."""
    move = model_move(answer)
    return None if move is None else option_of(problem, move)


def model_right(answer, problem):
    return model_option(answer, problem) in problem["right_moves"]


def model_right_counts(test_problems, answers, tries):
    """{problem id: number of right tries}, judged afresh against the problem's right moves. Stops if a
    problem lacks a try or an answer failed."""
    by_id = {s["id"]: s for s in test_problems}
    counts = {}
    for problem_id, records in _by_problem(answers, test_problems, "answer").items():
        if sorted(r["try"] for r in records) != list(range(1, tries + 1)):
            raise ScoringError(f"{problem_id}: tries {sorted(r['try'] for r in records)}, expected 1 to {tries}")
        failed = [r["try"] for r in records if r["failed"]]
        if failed:
            raise ScoringError(f"{problem_id}: tries {failed} failed; ask them again before scoring")
        counts[problem_id] = sum(model_right(r, by_id[problem_id]) for r in records)
    return counts


def program_scores(test_problems, program_picks):
    """{program: {problem id: score}}, scored afresh from the weights. Stops if a program lacks a problem, has
    one twice, or saved a score that differs from the weights."""
    by_id = {s["id"]: s for s in test_problems}
    programs = sorted({p["program"] for p in program_picks})
    scores = {}
    for program in programs:
        mine = [p for p in program_picks if p["program"] == program]
        grouped = _by_problem(mine, test_problems, program)
        for problem_id, picks in grouped.items():
            if len(picks) != 1:
                raise ScoringError(f"{program} has {len(picks)} picks for {problem_id}")
        scores[program] = {problem_id: score_pick(picks[0]["weights"], by_id[problem_id]["right_moves"],
                                                  len(by_id[problem_id]["options"]))
                           for problem_id, picks in grouped.items()}
        for problem_id, picks in grouped.items():
            if abs(picks[0]["score"] - scores[program][problem_id]) > 1e-9:
                raise ScoringError(f"{program} on {problem_id}: saved score {picks[0]['score']} does not match its weights")
    return scores


def _mean(values):
    return sum(values) / len(values)


def standard_error(values):
    """Standard error of the mean of `values`; None for fewer than two values."""
    return stdev(values) / sqrt(len(values)) if len(values) > 1 else None


def chance_model_gets(right_move_count, option_count, tries):
    """Chance that a model guessing evenly among the options is right on more than half of its tries."""
    p = right_move_count / option_count
    return sum(comb(tries, k) * p ** k * (1 - p) ** (tries - k) for k in range(tries + 1) if 2 * k > tries)


def scores_by_depth(test_problems, program_picks, answers=None, tries=5):
    """Per depth: number of problems, each program's score and its standard error, the best programs, room
    and the standard error of the best program's score (`room_standard_error_of` names it: the first of the
    tied best, alphabetically), each search program's mean budget (`sequences_examined_mean` for the
    lookaheads, `identities_worked_out_mean` for narrow-and-deep); with answers, also
    the model's score and standard error, the mean per-problem difference between the model and each program on
    the same problems with its standard error, the model's use of the answers (see answer_use), and the share
    right among forced answers and among unforced ones, with how many there are of each (None where there are
    none)."""
    programs = program_scores(test_problems, program_picks)
    right_counts = model_right_counts(test_problems, answers, tries) if answers is not None else None
    budgets = {field: sorted({p["program"] for p in program_picks if field in p}) for field in SEARCH_BUDGETS}
    by_id = {s["id"]: s for s in test_problems}
    table = {}
    for depth in sorted({s["depth"] for s in test_problems}):
        ids = [s["id"] for s in test_problems if s["depth"] == depth]
        id_set = set(ids)
        row = {"problems": len(ids), "programs": {name: _mean([scores[i] for i in ids]) for name, scores in programs.items()},
               "programs_standard_error": {name: standard_error([scores[i] for i in ids])
                                           for name, scores in programs.items()}}
        best = max(row["programs"].values())
        row["best_programs"] = sorted(name for name, score in row["programs"].items() if score >= best - TIE)
        row["room"] = 1 - best
        row["room_standard_error_of"] = row["best_programs"][0]
        row["room_standard_error"] = row["programs_standard_error"][row["room_standard_error_of"]]
        for field, searchers in budgets.items():
            if searchers:
                row[f"{field}_mean"] = {name: _mean([p[field] for p in program_picks
                                                     if p["program"] == name and p["problem_id"] in id_set])
                                        for name in searchers}
        if answers is not None:
            model = {i: right_counts[i] / tries for i in ids}
            row["model"] = _mean(list(model.values()))
            row["model_standard_error"] = standard_error(list(model.values()))
            row["model_minus_program"] = {}
            for name, scores in programs.items():
                differences = [model[i] - scores[i] for i in ids]
                row["model_minus_program"][name] = {"mean": _mean(differences),
                                                    "standard_error": standard_error(differences)}
            here = [a for a in answers if a["problem_id"] in id_set]
            row.update(answer_use(here, by_id))
            row.update(forced_and_unforced(here, by_id))
        table[depth] = row
    return table


def forced_and_unforced(answers, problems):
    """How many answers are forced and how many are not, and the share right among each (None if none).
    `problems` maps each problem id to its record."""
    out = {}
    for name, chosen in (("forced", [a for a in answers if a["forced"]]),
                         ("unforced", [a for a in answers if not a["forced"]])):
        out[f"{name}_answers"] = len(chosen)
        out[f"{name}_share_right"] = (_mean([model_right(a, problems[a["problem_id"]]) for a in chosen])
                                      if chosen else None)
    return out


def problem_by_problem(test_problems, program_picks, answers, tries=5):
    """Per program and depth: problems both get, only the model, only the program, neither, and two figures
    for how many "only the model" problems to expect by chance: if the model were guessing evenly among the
    problem's options, and if the model got problems independently of the program (m x p: m problems the
    program misses, p the share of problems the model gets at that depth), with that figure's standard error
    sqrt(m p (1 - p)) (None at a depth with one problem)."""
    programs = program_scores(test_problems, program_picks)
    right_counts = model_right_counts(test_problems, answers, tries)
    table = {}
    for program, scores in programs.items():
        table[program] = {}
        for depth in sorted({s["depth"] for s in test_problems}):
            here = [s for s in test_problems if s["depth"] == depth]
            row = {"both": 0, "only_model": 0, "only_program": 0, "neither": 0, "only_model_expected_by_chance": 0.0}
            for problem in here:
                model_gets = 2 * right_counts[problem["id"]] > tries
                program_gets = scores[problem["id"]] > 0.5
                key = {(True, True): "both", (True, False): "only_model",
                       (False, True): "only_program", (False, False): "neither"}[(model_gets, program_gets)]
                row[key] += 1
                if not program_gets:
                    row["only_model_expected_by_chance"] += chance_model_gets(
                        len(problem["right_moves"]), len(problem["options"]), tries)
            model_gets_share = (row["both"] + row["only_model"]) / len(here)
            misses = row["only_model"] + row["neither"]
            row["only_model_expected_if_independent"] = misses * model_gets_share
            row["only_model_if_independent_standard_error"] = (
                sqrt(misses * model_gets_share * (1 - model_gets_share)) if len(here) > 1 else None)
            table[program][depth] = row
    return table


def own_thinking_tokens(answer):
    """The thinking tokens the model wrote itself: for a forced answer, those before the server's end text
    (its record keeps both, `thinking_tokens` counting the end text too); for any other, all of them. A record
    saved before the count without the end text was kept has only the count with it."""
    if answer["forced"]:
        return answer.get("thinking_tokens_before_end_text", answer["thinking_tokens"])
    return answer["thinking_tokens"]


def answer_use(answers, problems=None):
    """Shares of failed, unreadable, forced and cut-off-but-already-readable answers, and token use per answer
    that did not fail. An answer is unreadable when the request worked but no move could be read from it.
    With `problems` (each problem id to its record), also the share of answers whose move was read but is not
    available on the problem's page (it produces nothing new, or names an identity not on the page).
    An answer is forced when the server closed its thinking at the allowance (see thinking_end.py).
    `thinking_tokens_mean` is the model's own thinking (`own_thinking_tokens`), so it can be set beside the
    allowance; it is exact but None unless the server gave token ids for every answer. `tokens_used_mean`
    counts every token of the reply (thinking, the server's end text, answer), so it is an upper limit on
    thinking."""
    worked = [a for a in answers if not a["failed"]]
    thinking = [own_thinking_tokens(a) for a in worked]
    use = {"answers": len(answers),
           "failed_share": _mean([bool(a["failed"]) for a in answers]),
           "unreadable_share": _mean([not a["failed"] and model_move(a) is None for a in answers]),
           "forced_share": _mean([bool(a["forced"]) for a in answers]),
           "cut_off_but_readable_share": _mean([bool(a["cut_off_but_readable"]) for a in answers]),
           "thinking_tokens_mean": _mean(thinking) if worked and None not in thinking else None,
           "tokens_used_mean": _mean([a["tokens_used"] for a in worked]) if worked else None}
    if problems is not None:
        use["not_available_share"] = _mean([model_move(a) is not None and model_option(a, problems[a["problem_id"]])
                                            is None for a in answers])
    return use


def most_identities_written(tokens_used, tokens_per_identity):
    """An upper limit only: how many identities the model could have written out in the tokens it used, one
    identity taking as many tokens as the equation does."""
    return tokens_used / tokens_per_identity
