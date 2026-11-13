"""Stage 4: score everything and write the report.

Reads test_problems.jsonl, program_picks.jsonl, model_answers.jsonl and (for the tokens one equation takes to
write out) model_run_check.json from --data. Writes scores_by_depth.json, problem_by_problem.json,
wrong_moves.json, report.txt and curve.svg. Every figure comes from fe_ladder/scoring.py and, for the same wrong
moves, fe_ladder/wrong_moves.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fe_ladder import report, scoring, wrong_moves  # noqa: E402
from fe_ladder.problems import read_jsonl  # noqa: E402


MARGINS_NOTE = (
    "Margins of error. Each standard error is the sample standard deviation (n - 1) of the per-problem figures\n"
    "over the square root of the number of problems at that depth (n/a with one problem): for every score, and\n"
    "for the model minus each program on the same problems. Beside the count of problems only the model gets,\n"
    "the count expected if the model's successes were unrelated to the program's is m x p (m problems the\n"
    "program misses, p the share the model gets), with standard error sqrt(m p (1 - p)). In the same-wrong-moves\n"
    "table each is across the problems with a wrong try (n/a with fewer than two), because the tries on one\n"
    "problem are not independent. These margins reflect the choice of test problems only; for the surface\n"
    "readers they do not say what a different training set would give. With 4 depths, an occasional gap of two\n"
    "standard errors is expected by luck alone.")

BUDGETS_NOTE = (
    "Budgets, each in its own units: the model's allowance, tokens actually used and share of forced answers;\n"
    "each lookahead's number of sequences examined; the narrow-and-deep program's number of identities worked\n"
    "out. One common figure, as an upper limit only (tokens_used is one too):\n"
    "the most identities the model could have written out in its tokens\n"
    "(most_identities_written: tokens used over the tokens of one identity, the equation's).\n"
    "This places the model among the programs and does not rank them on equal terms.")

WRONG_MOVES_NOTE = (
    "Same wrong moves, over the problems where the model gave a readable wrong move: the weight the program's\n"
    "pick puts on that move (match), what even guessing among the wrong moves would give (uniform), the same moves\n"
    "set against the program's picks on the other problems at that depth (shuffle), match minus shuffle (excess),\n"
    "and the excess less each control's on the same problems (over_...), with standard errors across problems.\n"
    "Moves that are not available are left out (no program can put weight on them); left_out_not_available\n"
    "gives how many tries that was.\n"
    "It describes a resemblance between the model's mistakes and the program's, nothing more.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--tries", type=int, default=5)
    args = parser.parse_args(argv)
    data = Path(args.data)
    test = read_jsonl(data / "test_problems.jsonl")
    picks = read_jsonl(data / "program_picks.jsonl")
    answers = read_jsonl(data / "model_answers.jsonl")
    tokens_per_identity = json.loads((data / "model_run_check.json").read_text())["tokens_per_equation"]
    allowance = answers[0]["settings"]["thinking_allowance"]

    by_depth = scoring.scores_by_depth(test, picks, answers, args.tries)
    for row in by_depth.values():
        row["most_identities_written"] = scoring.most_identities_written(row["tokens_used_mean"], tokens_per_identity)
    four_counts = scoring.problem_by_problem(test, picks, answers, args.tries)
    (data / "scores_by_depth.json").write_text(json.dumps(by_depth, indent=1))
    (data / "problem_by_problem.json").write_text(json.dumps(four_counts, indent=1))
    same_wrong = wrong_moves.same_wrong_moves(test, picks, answers)
    (data / "wrong_moves.json").write_text(json.dumps(same_wrong, indent=1))
    text = "\n\n".join([
        MARGINS_NOTE,
        "Scores by depth (room = 1 - best simple program)\n" + report.scores_text(by_depth),
        "Standard errors of the scores (room's is the named best program's)\n"
        + report.standard_errors_text(by_depth),
        "Model minus each program, per-problem difference on the same problems: mean, then standard error\n"
        + report.model_minus_program_text(by_depth),
        "Forced and unforced answers: how many, and the share right among each\n"
        + report.forced_and_unforced_text(by_depth),
        BUDGETS_NOTE + "\n" + report.budgets_text(by_depth, allowance),
        "Problem by problem (model gets a problem: more than half its tries right; a program: more than half its "
        "weight on right moves). Programs are exact; the model's 3 of 5 is a noisy estimate (a model right 55% "
        "of the time on a problem gets it about 59% of the time).\n" + report.problem_by_problem_text(four_counts),
        WRONG_MOVES_NOTE + "\n" + report.wrong_moves_text(same_wrong)])
    (data / "report.txt").write_text(text + "\n")
    (data / "curve.svg").write_text(report.curve_svg(by_depth))
    print(text)


if __name__ == "__main__":
    main()
