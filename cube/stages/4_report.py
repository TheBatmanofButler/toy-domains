"""Stage 4: score everything and write the report.

Reads test_states.jsonl, program_picks.jsonl, model_answers.jsonl and (for the tokens one cube takes to write
out) model_run_check.json from --data. Writes scores_by_distance.json, state_by_state.json, report.txt and
curve.svg. Every figure comes from cube_ladder/scoring.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder import report, scoring  # noqa: E402
from cube_ladder.states import read_jsonl  # noqa: E402


MARGINS_NOTE = (
    "Margins of error. Each standard error is the sample standard deviation (n - 1) of the per-state figures\n"
    "over the square root of the number of states at that distance (n/a with one state): for every score, and\n"
    "for the model minus each program on the same states. Beside the count of states only the model gets, the\n"
    "count expected if the model's successes were unrelated to the program's is m x p (m states the program\n"
    "misses, p the share the model gets), with standard error sqrt(m p (1 - p)). These margins reflect the\n"
    "choice of test states only; for the surface readers they do not say what a different training set would\n"
    "give. With 17 distances, an occasional gap of two standard errors is expected by luck alone.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--tries", type=int, default=5)
    args = parser.parse_args(argv)
    data = Path(args.data)
    test = read_jsonl(data / "test_states.jsonl")
    picks = read_jsonl(data / "program_picks.jsonl")
    answers = read_jsonl(data / "model_answers.jsonl")
    tokens_per_cube = json.loads((data / "model_run_check.json").read_text())["tokens_per_cube_string"]
    allowance = answers[0]["settings"]["thinking_allowance"]

    by_distance = scoring.scores_by_distance(test, picks, answers, args.tries)
    for row in by_distance.values():
        row["most_cubes_written"] = scoring.most_cubes_written(row["tokens_used_mean"], tokens_per_cube)
    four_counts = scoring.state_by_state(test, picks, answers, args.tries)
    (data / "scores_by_distance.json").write_text(json.dumps(by_distance, indent=1))
    (data / "state_by_state.json").write_text(json.dumps(four_counts, indent=1))
    text = "\n\n".join([
        MARGINS_NOTE,
        "Scores by distance (room = 1 - best simple program)\n" + report.scores_text(by_distance),
        "Standard errors of the scores (room's is the named best program's)\n"
        + report.standard_errors_text(by_distance),
        "Model minus each program, per-state difference on the same states: mean, then standard error\n"
        + report.model_minus_program_text(by_distance),
        "Budgets, each in its own units (tokens_used and most_cubes_written are upper limits)\n"
        + report.budgets_text(by_distance, allowance),
        "State by state (model gets a state: more than half its tries right; a program: more than half its "
        "weight on right turns). Programs are exact; the model's 3 of 5 is a noisy estimate (a model right 55% "
        "of the time on a state gets it about 59% of the time).\n" + report.state_by_state_text(four_counts)])
    (data / "report.txt").write_text(text + "\n")
    (data / "curve.svg").write_text(report.curve_svg(by_distance))
    print(text)


if __name__ == "__main__":
    main()
