"""Every figure in the report is worked out here, and only here.

Scores: a pick scores the weight it puts on right options; a model try scores 1 if its option is right. Under
the author's key the one right option is the held-back fact. A problem's model score is the share of its tries
that are right; a row's score is the average over its problems. There are no distances: every table has one row
for all problems, then rows by number of cited facts (2 to 3, 4 to 6, 7 or more) and by article group. Room in a
row is one minus the best simple program there. Problem by problem, the model "gets" a problem when more than half
its tries are right (3 of 5), and a program gets it when more than half its weight is on right options; the same
bar for both. The model's options are read afresh from its answer text, so the answer reader can change without
asking the model again.

Margins of error are given as numbers only; nothing here decides what counts as "above". A standard error is
the sample standard deviation (n - 1 in the divisor) of the per-problem figures over the square root of the
number of problems; with one problem there is none (None). It reflects the choice of test problems only.
"""
from math import comb, sqrt
from statistics import stdev

from mizar_ladder.answers import read_option
from mizar_ladder.library import GROUPS
from mizar_ladder.problems import OPTIONS

ALL = "all problems"
CITED_ROWS = (("2 to 3 cited", 2, 3), ("4 to 6 cited", 4, 6), ("7 or more cited", 7, None))

# Scores closer than this are tied (they are averages of the same few fractions).
TIE = 1e-12


class ScoringError(Exception):
    pass


def right_options(problem):
    """The right options under the author's key: the held-back fact's number."""
    return [problem["held_back"]]


def row_names(problem):
    """The rows a problem is counted in: all problems, its number of cited facts, its article group."""
    cited = next(name for name, low, high in CITED_ROWS if low <= problem["cited_count"] and
                 (high is None or problem["cited_count"] <= high))
    return [ALL, cited, problem["group"]]


def rows(test_problems):
    """{row: ids of its problems}, in the fixed order of the rows; rows without problems are left out."""
    order = [ALL] + [name for name, _, _ in CITED_ROWS] + list(GROUPS)
    found = {name: [] for name in order}
    for problem in test_problems:
        for name in row_names(problem):
            if name not in found:
                raise ScoringError(f"{problem['id']}: no row for {name!r}")
            found[name].append(problem["id"])
    return {name: ids for name, ids in found.items() if ids}


def score_pick(weights, right):
    """The weight a pick puts on the right options (numbers 1 to 30)."""
    if len(weights) != OPTIONS or abs(sum(weights) - 1) > 1e-9 or min(weights) < 0:
        raise ScoringError(f"not a pick: {weights}")
    return sum(weight for number, weight in enumerate(weights, 1) if number in right)


def by_problem(records, test_problems, kind):
    """Group records by their `problem_id`; every test problem must be there. `kind` names the records in errors."""
    grouped = {p["id"]: [] for p in test_problems}
    for record in records:
        if record["problem_id"] not in grouped:
            raise ScoringError(f"{kind} for {record['problem_id']}, which is not a test problem")
        grouped[record["problem_id"]].append(record)
    return grouped


def model_option(answer):
    """The option read from a saved answer's text (None if unreadable or the request failed)."""
    return None if answer["failed"] else read_option(answer["answer_text"])


def model_right_counts(test_problems, answers, tries):
    """{problem id: number of right tries}, judged afresh against the problem's right option. Stops if a
    problem lacks a try or an answer failed."""
    right = {p["id"]: right_options(p) for p in test_problems}
    counts = {}
    for problem_id, records in by_problem(answers, test_problems, "answer").items():
        if sorted(r["try"] for r in records) != list(range(1, tries + 1)):
            raise ScoringError(f"{problem_id}: tries {sorted(r['try'] for r in records)}, expected 1 to {tries}")
        failed = [r["try"] for r in records if r["failed"]]
        if failed:
            raise ScoringError(f"{problem_id}: tries {failed} failed; ask them again before scoring")
        counts[problem_id] = sum(model_option(r) in right[problem_id] for r in records)
    return counts


def program_scores(test_problems, program_picks):
    """{program: {problem id: score}}, scored afresh from the weights. Stops if a program lacks a problem, has
    one twice, or saved a score that differs from the weights."""
    right = {p["id"]: right_options(p) for p in test_problems}
    programs = sorted({p["program"] for p in program_picks})
    scores = {}
    for program in programs:
        mine = [p for p in program_picks if p["program"] == program]
        grouped = by_problem(mine, test_problems, program)
        for problem_id, picks in grouped.items():
            if len(picks) != 1:
                raise ScoringError(f"{program} has {len(picks)} picks for {problem_id}")
        scores[program] = {problem_id: score_pick(picks[0]["weights"], right[problem_id])
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


def chance_model_gets(right_count, tries):
    """Chance that a model guessing evenly among the 30 options is right on more than half of its tries."""
    p = right_count / OPTIONS
    return sum(comb(tries, k) * p ** k * (1 - p) ** (tries - k) for k in range(tries + 1) if 2 * k > tries)


def scores_by_row(test_problems, program_picks, answers=None, tries=5):
    """Per row: number of problems, each program's score and its standard error, the best programs, room and
    the standard error of the best program's score (`room_standard_error_of` names it: the first of the tied
    best, alphabetically); with answers, also the model's score and standard error, the mean per-problem
    difference between the model and each program on the same problems with its standard error, and the
    model's use of the answers (see answer_use)."""
    programs = program_scores(test_problems, program_picks)
    right_counts = model_right_counts(test_problems, answers, tries) if answers is not None else None
    table = {}
    for name_of_row, ids in rows(test_problems).items():
        id_set = set(ids)
        row = {"problems": len(ids),
               "programs": {name: _mean([scores[i] for i in ids]) for name, scores in programs.items()},
               "programs_standard_error": {name: standard_error([scores[i] for i in ids])
                                           for name, scores in programs.items()}}
        best = max(row["programs"].values())
        row["best_programs"] = sorted(name for name, score in row["programs"].items() if score >= best - TIE)
        row["room"] = 1 - best
        row["room_standard_error_of"] = row["best_programs"][0]
        row["room_standard_error"] = row["programs_standard_error"][row["room_standard_error_of"]]
        if answers is not None:
            model = {i: right_counts[i] / tries for i in ids}
            row["model"] = _mean(list(model.values()))
            row["model_standard_error"] = standard_error(list(model.values()))
            row["model_minus_program"] = {}
            for name, scores in programs.items():
                differences = [model[i] - scores[i] for i in ids]
                row["model_minus_program"][name] = {"mean": _mean(differences),
                                                    "standard_error": standard_error(differences)}
            row.update(answer_use([a for a in answers if a["problem_id"] in id_set]))
        table[name_of_row] = row
    return table


def problem_by_problem(test_problems, program_picks, answers, tries=5):
    """Per program and row: problems both get, only the model, only the program, neither, and two figures for
    how many "only the model" problems to expect by chance: if the model were guessing evenly among the 30
    options, and if the model got problems independently of the program (m x p: m problems the program misses,
    p the share of problems the model gets in that row), with that figure's standard error sqrt(m p (1 - p))
    (None in a row with one problem)."""
    programs = program_scores(test_problems, program_picks)
    right_counts = model_right_counts(test_problems, answers, tries)
    by_id = {p["id"]: p for p in test_problems}
    table = {}
    for program, scores in programs.items():
        table[program] = {}
        for name_of_row, ids in rows(test_problems).items():
            here = [by_id[i] for i in ids]
            row = {"both": 0, "only_model": 0, "only_program": 0, "neither": 0, "only_model_expected_by_chance": 0.0}
            for problem in here:
                model_gets = 2 * right_counts[problem["id"]] > tries
                program_gets = scores[problem["id"]] > 0.5
                key = {(True, True): "both", (True, False): "only_model",
                       (False, True): "only_program", (False, False): "neither"}[(model_gets, program_gets)]
                row[key] += 1
                if not program_gets:
                    row["only_model_expected_by_chance"] += chance_model_gets(len(right_options(problem)), tries)
            model_gets_share = (row["both"] + row["only_model"]) / len(here)
            misses = row["only_model"] + row["neither"]
            row["only_model_expected_if_independent"] = misses * model_gets_share
            row["only_model_if_independent_standard_error"] = (
                sqrt(misses * model_gets_share * (1 - model_gets_share)) if len(here) > 1 else None)
            table[program][name_of_row] = row
    return table


def own_thinking_tokens(answer):
    """The thinking tokens the model wrote itself: for a forced answer, those before the server's end text
    (its record keeps both, `thinking_tokens` counting the end text too); for any other, all of them. A record
    saved before the count without the end text was kept has only the count with it."""
    if answer["forced"]:
        return answer.get("thinking_tokens_before_end_text", answer["thinking_tokens"])
    return answer["thinking_tokens"]


def answer_use(answers):
    """Shares of failed, unreadable, forced and cut-off-but-already-readable answers, and token use per answer
    that did not fail. An answer is unreadable when the request worked but no option could be read from it.
    An answer is forced when the server closed its thinking at the allowance (see thinking_end.py).
    `thinking_tokens_mean` is the model's own thinking (`own_thinking_tokens`), so it can be set beside the
    allowance. It is exact, and taken over the answers that have a count (the server gave token ids);
    `answers_without_thinking_count` says how many that did not fail lack one, so a missing count shows
    rather than emptying the figure. It is None only when no answer has a count. `tokens_used_mean`
    counts every token of the reply (thinking, the server's end text, answer), so it is an upper limit on
    thinking."""
    worked = [a for a in answers if not a["failed"]]
    counted = [t for t in (own_thinking_tokens(a) for a in worked) if t is not None]
    return {"answers": len(answers),
            "failed_share": _mean([bool(a["failed"]) for a in answers]),
            "unreadable_share": _mean([not a["failed"] and model_option(a) is None for a in answers]),
            "forced_share": _mean([bool(a["forced"]) for a in answers]),
            "cut_off_but_readable_share": _mean([bool(a["cut_off_but_readable"]) for a in answers]),
            "thinking_tokens_mean": _mean(counted) if counted else None,
            "answers_without_thinking_count": len(worked) - len(counted),
            "tokens_used_mean": _mean([a["tokens_used"] for a in worked]) if worked else None}
