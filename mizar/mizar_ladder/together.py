"""Counted together: the simple programs get different problems right, so beside their scores, per row of the
tables, how many problems the best single program gets, how many at least one program gets and how many none
gets. A program gets a problem when more than half its weight is on the right option (exactly half does not);
`guessing` is left out of "at least one program" (it never gets one). With the model's answers, also: of the
problems at least one program gets, how many the model gets; of those no program gets, how many the model gets.
The model gets a problem when more than half its tries are right (3 of 5). Numbers only.
"""
from mizar_ladder import scoring

LEFT_OUT = ("guessing",)


def program_gets(test_problems, program_picks):
    """{program: {problem id: True when more than half its weight is on the right option}}."""
    return {name: {i: score > 0.5 for i, score in scores.items()}
            for name, scores in scoring.program_scores(test_problems, program_picks).items()}


def counted_together(test_problems, program_picks, answers=None, tries=5):
    gets = program_gets(test_problems, program_picks)
    counted = [name for name in gets if name not in LEFT_OUT]
    model = None
    if answers is not None:
        right = scoring.model_right_counts(test_problems, answers, tries)
        model = {i: 2 * n > tries for i, n in right.items()}
    table = {}
    for name_of_row, ids in scoring.rows(test_problems).items():
        each = {name: sum(gets[name][i] for i in ids) for name in gets}
        best = max(each.values())
        some = [i for i in ids if any(gets[name][i] for name in counted)]
        none = [i for i in ids if i not in set(some)]
        row = {"problems": len(ids), "best_single_program": best,
               "best_single_programs": sorted(name for name, n in each.items() if n == best),
               "at_least_one_program": len(some), "no_program": len(none)}
        if model is not None:
            row["model_gets_of_at_least_one_program"] = sum(model[i] for i in some)
            row["model_gets_of_no_program"] = sum(model[i] for i in none)
        table[name_of_row] = row
    return table
