"""Same wrong answers: when the model is wrong, is it wrong in the way a program is?

Worked out afterwards from the saved answers and picks; nothing new is asked of the model. For each program
and each row of the tables (all problems, by number of cited facts, by article group):
- A wrong try is a try whose answer reads as an option number (read afresh from the answer text, as in the
  rest of the scoring, never from the stored `option`) and that option is not right. Unreadable and failed tries
  are left out, so a problem whose tries are all right or unreadable takes no part.
- A problem's match value is the average, over its wrong tries, of the weight the program's pick puts on the
  model's option (a program torn between three options puts a third on each). The match rate is the average
  over the problems with a wrong try.
- Uniform figure: per such problem, the program's total weight on wrong options over the number of wrong
  options; what a program guessing evenly among the wrong options would score; averaged over the same problems.
- Shuffle figure: per wrong try, the average weight the program puts on that same option number over every
  other test problem in the row (whether or not the option is right there); averaged by problem as the match
  value is. It shows how many matches come from habits alone (a model or a program that favours certain
  numbers). It uses every other problem, so no random numbers are needed.
- Excess: match minus shuffle, problem by problem; and for each control program the difference between this
  program's excess and the control's on the same problems.

Everything is by problem, because the five tries on one problem are not independent: the standard errors (as
in scoring.py: n - 1, over the square root of n) are across problems, and there is none with fewer than two
problems. Numbers only: nothing here decides what counts as a resemblance.
"""
from mizar_ladder import scoring
from mizar_ladder.problems import OPTIONS


def control_programs(names):
    """The programs that do no search, which serve as controls: recall and the symbol-sharing surface reader,
    as named among `names` (the programs in the picks file)."""
    return sorted(name for name in names if name in ("recall", "surface_symbols"))


def wrong_tries(test_problems, answers):
    """{problem id: the model's readable wrong options, one per such try}; problems without one are left out."""
    right = {p["id"]: scoring.right_options(p) for p in test_problems}
    found = {}
    for problem_id, records in scoring.by_problem(answers, test_problems, "answer").items():
        options = [scoring.model_option(r) for r in records]
        wrong = [o for o in options if o is not None and o not in right[problem_id]]
        if wrong:
            found[problem_id] = wrong
    return found


def _mean(values):
    return sum(values) / len(values) if values else None


def _problem_figures(weights, wrong, ids, right):
    """{problem: (match, uniform, shuffle)} for one program in one row, over the problems in `wrong`.
    `weights` maps each problem id to its pick; shuffle is None when the row has no other problem."""
    figures = {}
    for problem in ids:
        if problem not in wrong:
            continue
        pick = weights[problem]
        match = _mean([pick[o - 1] for o in wrong[problem]])
        wrong_options = [o for o in range(1, OPTIONS + 1) if o not in right[problem]]
        uniform = sum(pick[o - 1] for o in wrong_options) / len(wrong_options)
        others = [i for i in ids if i != problem]
        shuffle = _mean([_mean([weights[i][o - 1] for i in others]) for o in wrong[problem]]) if others else None
        figures[problem] = (match, uniform, shuffle)
    return figures


def _mean_and_error(values):
    return {"mean": _mean(values), "standard_error": scoring.standard_error(values)}


def same_wrong_answers(test_problems, program_picks, answers, controls=None):
    """{program: {row: row figures}}. Each row: `problems` (problems with a wrong try) and `wrong_tries` behind
    every figure; `match_rate` and its standard error; `uniform`; `shuffle`; `excess` and its standard error;
    and `excess_over_control`, {control: mean and standard error of this program's excess minus the control's,
    problem by problem} for each control other than the program itself. `controls` defaults to
    control_programs of the programs in `program_picks`. A figure that cannot be worked out (no problem with a
    wrong try, or for the shuffle no other problem in the row) is None."""
    scoring.program_scores(test_problems, program_picks)   # the same checks on the picks as the scores get
    programs = sorted({p["program"] for p in program_picks})
    controls = control_programs(programs) if controls is None else controls
    weights = {name: {p["problem_id"]: p["weights"] for p in program_picks if p["program"] == name}
               for name in programs}
    right = {p["id"]: scoring.right_options(p) for p in test_problems}
    wrong = wrong_tries(test_problems, answers)
    ids = scoring.rows(test_problems)
    figures = {name: {r: _problem_figures(weights[name], wrong, ids[r], right) for r in ids} for name in programs}

    def excess(name, r):
        return {problem: match - shuffle for problem, (match, _, shuffle) in figures[name][r].items()
                if shuffle is not None}

    table = {}
    for name in programs:
        table[name] = {}
        for r in ids:
            here = figures[name][r]
            mine = excess(name, r)
            matches = [match for match, _, _ in here.values()]
            row = {"problems": len(here), "wrong_tries": sum(len(wrong[problem]) for problem in here),
                   "match_rate": _mean(matches), "match_rate_standard_error": scoring.standard_error(matches),
                   "uniform": _mean([uniform for _, uniform, _ in here.values()]),
                   "shuffle": _mean([shuffle for _, _, shuffle in here.values() if shuffle is not None])}
            excess_figures = _mean_and_error(list(mine.values()))
            row["excess"], row["excess_standard_error"] = excess_figures["mean"], excess_figures["standard_error"]
            row["excess_over_control"] = {}
            for control in controls:
                if control != name:
                    theirs = excess(control, r)
                    row["excess_over_control"][control] = _mean_and_error([mine[c] - theirs[c] for c in mine])
            table[name][r] = row
    return table
