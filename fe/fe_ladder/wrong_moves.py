"""Same wrong moves: when the model is wrong, is it wrong in the way a program is?

Worked out afterwards from the saved answers and picks; nothing new is asked of the model. For each program
and each depth:
- A wrong try is a try whose answer reads as a move (read afresh from the answer text, as in the rest of the
  scoring, never from the stored `move`) that is one of the problem's options and is not right. Unreadable
  and failed tries are left out, and so are moves that are not available (no program can put weight on them),
  so a problem whose tries are all right, unreadable or not available takes no part. How many tries were left
  out because their move is not available is given beside the figures.
- A problem's match value is the average, over its wrong tries, of the weight the program's pick puts on the
  model's option (a program torn between three options puts a third on each). The match rate is the average
  over the problems with a wrong try.
- Uniform figure: per such problem, the program's total weight on wrong options over the number of wrong
  options; what a program guessing evenly among the wrong options would score; averaged over the same problems.
- Shuffle figure: per wrong try, the average weight the program puts on that same move over every other test
  problem at that depth (whether or not the move is right there); the options differ from problem to problem,
  so the move is matched to the other problem's options by its identity number and substitution, and weighs 0
  where it is not available. Averaged by problem as the match value is. It shows how many matches come from
  habits alone (a model or a program that favours certain moves). It uses every other problem, so no random
  numbers are needed.
- Excess: match minus shuffle, problem by problem; and for each control program the difference between this
  program's excess and the control's on the same problems.

Everything is by problem, because the five tries on one problem are not independent: the standard errors (as
in scoring.py: n - 1, over the square root of n) are across problems, and there is none with fewer than two
problems. Numbers only: nothing here decides what counts as a resemblance.
"""
from fe_ladder import scoring
from fe_ladder.answers import option_of


def control_programs(names):
    """The programs that do no search, which serve as controls: recall and the strict surface reader, as named
    among `names` (the programs in the picks file)."""
    return sorted(name for name in names if name in ("recall", "surface_strict"))


def wrong_tries(test_problems, answers):
    """{problem id: the model's readable wrong moves that are options, one per such try}; problems without one
    are left out."""
    by_id = {s["id"]: s for s in test_problems}
    found = {}
    for problem_id, records in scoring._by_problem(answers, test_problems, "answer").items():
        problem = by_id[problem_id]
        readable = [m for m in map(scoring.model_move, records) if m is not None]
        options = [option_of(problem, m) for m in readable]
        wrong = [m for m, n in zip(readable, options) if n is not None and n not in problem["right_moves"]]
        if wrong:
            found[problem_id] = wrong
    return found


def not_available_tries(test_problems, answers):
    """{problem id: number of tries whose move was read but is not available}; problems with none left out."""
    by_id = {s["id"]: s for s in test_problems}
    found = {}
    for problem_id, records in scoring._by_problem(answers, test_problems, "answer").items():
        count = sum(1 for r in records if scoring.model_move(r) is not None
                    and scoring.model_option(r, by_id[problem_id]) is None)
        if count:
            found[problem_id] = count
    return found


def _mean(values):
    return sum(values) / len(values) if values else None


def _weight_on(weights, problem, move):
    """The weight a pick on `problem` puts on the option holding `move`; 0 if the move is not available there."""
    n = option_of(problem, move)
    return 0.0 if n is None else weights[n]


def _problem_figures(weights, wrong, ids, by_id):
    """{problem: (match, uniform, shuffle)} for one program at one depth, over the problems in `wrong`.
    `weights` maps each problem id to its pick; shuffle is None when the depth has no other problem."""
    figures = {}
    for problem_id in ids:
        if problem_id not in wrong:
            continue
        pick, problem = weights[problem_id], by_id[problem_id]
        match = _mean([_weight_on(pick, problem, m) for m in wrong[problem_id]])
        wrong_options = [n for n in range(len(problem["options"])) if n not in problem["right_moves"]]
        uniform = sum(pick[n] for n in wrong_options) / len(wrong_options)
        others = [i for i in ids if i != problem_id]
        shuffle = (_mean([_mean([_weight_on(weights[i], by_id[i], m) for i in others]) for m in wrong[problem_id]])
                   if others else None)
        figures[problem_id] = (match, uniform, shuffle)
    return figures


def _mean_and_error(values):
    return {"mean": _mean(values), "standard_error": scoring.standard_error(values)}


def same_wrong_moves(test_problems, program_picks, answers, controls=None):
    """{program: {depth: row}}. Each row: `problems` (problems with a wrong try) and `wrong_tries` behind every
    figure; `not_available_left_out`, the tries at that depth left out because their move is not available;
    `match_rate` and its standard error; `uniform`; `shuffle`; `excess` and its standard error; and
    `excess_over_control`, {control: mean and standard error of this program's excess minus the control's,
    problem by problem} for each control other than the program itself. `controls` defaults to
    control_programs of the programs in `program_picks`. A figure that cannot be worked out (no problem with a
    wrong try, or for the shuffle no other problem at the depth) is None."""
    scoring.program_scores(test_problems, program_picks)   # the same checks on the picks as the scores get
    programs = sorted({p["program"] for p in program_picks})
    controls = control_programs(programs) if controls is None else controls
    weights = {name: {p["problem_id"]: p["weights"] for p in program_picks if p["program"] == name}
               for name in programs}
    by_id = {s["id"]: s for s in test_problems}
    wrong = wrong_tries(test_problems, answers)
    left_out = not_available_tries(test_problems, answers)
    depths = sorted({s["depth"] for s in test_problems})
    ids = {d: [s["id"] for s in test_problems if s["depth"] == d] for d in depths}
    figures = {name: {d: _problem_figures(weights[name], wrong, ids[d], by_id) for d in depths}
               for name in programs}

    def excess(name, d):
        return {problem: match - shuffle for problem, (match, _, shuffle) in figures[name][d].items()
                if shuffle is not None}

    table = {}
    for name in programs:
        table[name] = {}
        for d in depths:
            here = figures[name][d]
            mine = excess(name, d)
            matches = [match for match, _, _ in here.values()]
            row = {"problems": len(here), "wrong_tries": sum(len(wrong[problem]) for problem in here),
                   "not_available_left_out": sum(left_out.get(i, 0) for i in ids[d]),
                   "match_rate": _mean(matches), "match_rate_standard_error": scoring.standard_error(matches),
                   "uniform": _mean([uniform for _, uniform, _ in here.values()]),
                   "shuffle": _mean([shuffle for _, _, shuffle in here.values() if shuffle is not None])}
            excess_figures = _mean_and_error(list(mine.values()))
            row["excess"], row["excess_standard_error"] = excess_figures["mean"], excess_figures["standard_error"]
            row["excess_over_control"] = {}
            for control in controls:
                if control != name:
                    theirs = excess(control, d)
                    row["excess_over_control"][control] = _mean_and_error([mine[c] - theirs[c] for c in mine])
            table[name][d] = row
    return table
