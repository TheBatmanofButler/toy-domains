"""Tests of together.py on four made-up problems, every count worked out by hand.

Problems (right option = held-back number): p1 (2 cited, sets, right 1), p2 (3 cited, sets, right 2), p3 (5 cited,
topology, right 3), p4 (8 cited, topology, right 4). Weight on the right option:
- A: p1 1, p2 exactly .5 (does not get it), p3 .6, p4 0: gets p1 and p3.
- B: p2 .51: gets p2.
- C: p1 .9: gets p1.
- guessing (made up to put everything on p4's right option): gets p4, but is left out of "at least one".
The model (five tries): p1 2 right, p2 3, p3 0, p4 5: gets p2 and p4.

All problems: best single A (2); at least one program: p1, p2, p3 (3); none: p4 (1); the model gets p2 of the
first three and p4 of the last.
2 to 3 cited (p1, p2): A, B and C get one each (best 1, tied); at least one 2; none 0; the model 1 and 0.
4 to 6 cited (p3): A (1); at least one 1; none 0; the model 0 and 0.
7 or more cited (p4): guessing gets it (best 1, guessing alone; the others 0); at least one 0; none 1; the model
0 and 1.
Sets (p1, p2) as 2 to 3 cited; topology (p3, p4): best 1 (A and guessing); at least one 1; none 1; the model 0
and 1.
"""
from mizar_ladder import together

PROBLEMS = [{"id": "p1", "cited_count": 2, "group": "sets, relations and functions", "held_back": 1},
            {"id": "p2", "cited_count": 3, "group": "sets, relations and functions", "held_back": 2},
            {"id": "p3", "cited_count": 5, "group": "topology", "held_back": 3},
            {"id": "p4", "cited_count": 8, "group": "topology", "held_back": 4}]
ON_RIGHT = {"A": [1, 0.5, 0.6, 0], "B": [0, 0.51, 0, 0], "C": [0.9, 0, 0, 0], "guessing": [0, 0, 0, 1]}
MODEL_RIGHT = {"p1": 2, "p2": 3, "p3": 0, "p4": 5}


def pick(right, weight):
    """`weight` on option `right`, the rest spread evenly over the other 29."""
    return [weight if n == right else (1 - weight) / 29 for n in range(1, 31)]


def picks():
    return [{"problem_id": p["id"], "program": name, "weights": pick(p["held_back"], w), "score": w}
            for name, weights in ON_RIGHT.items() for p, w in zip(PROBLEMS, weights)]


def answers():
    found = []
    for p in PROBLEMS:
        for t in range(1, 6):
            option = p["held_back"] if t <= MODEL_RIGHT[p["id"]] else p["held_back"] + 10
            found.append({"problem_id": p["id"], "try": t, "failed": False, "answer_text": f"FACT: {option}"})
    return found


def row(best, names, some, none, model=None):
    found = {"best_single_program": best, "best_single_programs": names, "at_least_one_program": some,
             "no_program": none}
    if model:
        found.update(model_gets_of_at_least_one_program=model[0], model_gets_of_no_program=model[1])
    return found


def test_counted_together_worked_by_hand():
    table = together.counted_together(PROBLEMS, picks(), answers())
    expected = {"all problems": (4, row(2, ["A"], 3, 1, (1, 1))),
                "2 to 3 cited": (2, row(1, ["A", "B", "C"], 2, 0, (1, 0))),
                "4 to 6 cited": (1, row(1, ["A"], 1, 0, (0, 0))),
                "7 or more cited": (1, row(1, ["guessing"], 0, 1, (0, 1))),
                "sets, relations and functions": (2, row(1, ["A", "B", "C"], 2, 0, (1, 0))),
                "topology": (2, row(1, ["A", "guessing"], 1, 1, (0, 1)))}
    assert list(table) == list(expected)
    for name, (problems, figures) in expected.items():
        assert table[name] == {"problems": problems, **figures}, name


def test_exactly_half_the_weight_does_not_get_a_problem():
    gets = together.program_gets(PROBLEMS, picks())
    assert gets["A"]["p2"] is False and gets["B"]["p2"] is True and gets["A"]["p3"] is True


def test_without_answers_there_are_no_model_figures():
    table = together.counted_together(PROBLEMS, picks())
    assert table["all problems"] == {"problems": 4, **row(2, ["A"], 3, 1)}
