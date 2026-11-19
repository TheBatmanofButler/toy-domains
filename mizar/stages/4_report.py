"""Stage 4: score everything and write the report.

Reads test_problems.jsonl, program_picks.jsonl, prover_key.jsonl, settled.json and raw/model_answers.jsonl from
--data. Stops if the answers were not all asked under the same settings (mizar_ladder/run_settings.py). Writes
scores.json, problem_by_problem.json, counted_together.json, wrong_answers.json, second_table.json, report.txt and
bars.svg. Every figure comes from mizar_ladder/scoring.py and, for the same wrong answers and the second table,
mizar_ladder/wrong_answers.py and mizar_ladder/second_table.py, and for the programs counted together
mizar_ladder/together.py. Every table has one row for all problems, then rows by number of cited facts and by
article group.

If raw/model_answers_renamed.jsonl exists (stage 3 with --renamed), it must hold the named answers' problems and
tries under the same settings but `renamed`, or the stage stops; the report then ends with a section "Named against
renamed" (mizar_ladder/renaming.py) and renamed.json is written. It also stops if a renamed answer's request seed
is not the named answer's for the same problem and try, or its question is not the renamed question of its problem
in test_problems_renamed.jsonl. Without renamed answers none of that is written, and a renamed.json left from an
earlier run is removed.

For each raw/model_answers_renamed_t<N>.jsonl (stage 3 with --renamed --other-allowance), the same checks with
`thinking_allowance` equal to N, a section "Named against renamed at a thinking allowance of N" and
renamed_t<N>.json; with the plain renamed answers present too, a table "Renamed at the two allowances" and
renamed_t<N>_two_allowances.json. Without such files nothing of that is written, and such files left from an
earlier run are removed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mizar_ladder import report, renaming, run_settings, scoring, second_table, together, wrong_answers  # noqa: E402
from mizar_ladder.problems import read_jsonl  # noqa: E402


MARGINS_NOTE = (
    "Margins of error. Each standard error is the sample standard deviation (n - 1) of the per-problem figures\n"
    "over the square root of the number of problems in the row (n/a with one problem): for every score, and\n"
    "for the model minus each program on the same problems. Beside the count of problems only the model gets,\n"
    "the count expected if the model's successes were unrelated to the program's is m x p (m problems the\n"
    "program misses, p the share the model gets), with standard error sqrt(m p (1 - p)). In the same-wrong-answers\n"
    "table each is across the problems with a wrong try (n/a with fewer than two), because the tries on one\n"
    "problem are not independent. These margins reflect the choice of test problems only; for the trained\n"
    "readers they do not say what a different training set would give. With seven rows, an occasional gap of two\n"
    "standard errors is expected by luck alone.")

WRONG_ANSWERS_NOTE = (
    "Same wrong answers, over the problems where the model gave a readable wrong option: the weight the program's\n"
    "pick puts on that option (match), what even guessing among the wrong options would give (uniform), the same\n"
    "option numbers set against the program's picks on the other problems in the row (shuffle), match minus\n"
    "shuffle (excess), and the excess less each control's on the same problems (over_...), with standard errors\n"
    "across problems. It describes a resemblance between the model's mistakes and the program's, nothing more.")


RENAMED_NOTE = (
    "Named against renamed: the same problems and tries asked with every symbol replaced by a meaningless code.\n"
    "Drop = the mean over problems of the named score minus the renamed score. both / named_only / renamed_only /\n"
    "neither are shares of the paired tries (same problem, same try).")


OTHER_ALLOWANCE = re.compile(r"model_answers_renamed_t([0-9]+)\.jsonl")


def other_allowances(data, test, picks, answers, tries, plain):
    """For each raw/model_answers_renamed_t<N>.jsonl: the renamed answers at a thinking allowance of N, checked as
    the renamed answers are but with `thinking_allowance` equal to N; writes renamed_t<N>.json and, with the plain
    renamed answers (`plain`) present too, renamed_t<N>_two_allowances.json. Removes such files of an earlier run
    that has no answers file now. Returns the text the report gains (empty without such files)."""
    found = {}
    for path in sorted((data / "raw").glob("model_answers_renamed_t*.jsonl")):
        match = OTHER_ALLOWANCE.fullmatch(path.name)
        if not match:
            sys.exit(f"STOP: {path.name}: not a file of a renamed run at another allowance (model_answers_renamed_t<N>"
                     ".jsonl)")
        found[int(match.group(1))] = path
    for old in list(data.glob("renamed_t*.json")):
        number = re.fullmatch(r"renamed_t([0-9]+)(_two_allowances)?\.json", old.name)
        if number and int(number.group(1)) not in found:
            old.unlink()
    text = ""
    named_allowance = answers[0]["settings"]["thinking_allowance"]      # one for all (run_settings)
    for allowance, path in sorted(found.items()):
        if allowance == named_allowance:
            sys.exit(f"STOP: {path.name}: the named run's own thinking allowance; those answers belong in "
                     "model_answers_renamed.jsonl")
        other = read_jsonl(path)
        try:
            run_settings.shared_settings(other)
            compared = renaming.named_against_renamed(test, picks, answers, other, tries, allowance)
            renaming.check_seeds_and_questions(answers, other, read_jsonl(data / "test_problems_renamed.jsonl"))
            both = renaming.two_allowances(test, plain, other, tries) if plain is not None else None
        except (run_settings.SettingsDiffer, renaming.RenamingError, scoring.ScoringError) as error:
            sys.exit(f"STOP: the renamed answers at a thinking allowance of {allowance}: {error}")
        (data / f"renamed_t{allowance}.json").write_text(json.dumps(compared, indent=1))
        text += (f"\n\nNamed against renamed at a thinking allowance of {allowance}: " + RENAMED_NOTE.split(": ", 1)[1]
                 + "\n" + report.renamed_text(compared))
        two_path = data / f"renamed_t{allowance}_two_allowances.json"
        if both is None:
            two_path.unlink(missing_ok=True)
        else:
            two_path.write_text(json.dumps(both, indent=1))
            text += (f"\n\nRenamed at the two allowances: the named run's and {allowance}, on the same problems and "
                     f"tries; difference = the mean over problems of the score at {allowance} minus the score at the "
                     "named run's allowance\n" + report.two_allowances_text(both))
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--tries", type=int, default=5)
    args = parser.parse_args(argv)
    data = Path(args.data)
    test = read_jsonl(data / "test_problems.jsonl")
    picks = read_jsonl(data / "program_picks.jsonl")
    answers = read_jsonl(data / "raw" / "model_answers.jsonl")
    prover_key = read_jsonl(data / "prover_key.jsonl")
    # Every answer's settings are read: answers asked in different ways must not be mixed in one report.
    try:
        allowance = run_settings.shared_settings(answers)["thinking_allowance"]
    except run_settings.SettingsDiffer as error:
        sys.exit(f"STOP: {error}")

    by_row = scoring.scores_by_row(test, picks, answers, args.tries)
    four_counts = scoring.problem_by_problem(test, picks, answers, args.tries)
    (data / "scores.json").write_text(json.dumps(by_row, indent=1))
    (data / "problem_by_problem.json").write_text(json.dumps(four_counts, indent=1))
    counted = together.counted_together(test, picks, answers, args.tries)
    (data / "counted_together.json").write_text(json.dumps(counted, indent=1))
    same_wrong = wrong_answers.same_wrong_answers(test, picks, answers)
    (data / "wrong_answers.json").write_text(json.dumps(same_wrong, indent=1))
    disagreed = json.loads((data / "settled.json").read_text())["unsettled_share"]
    second = second_table.second_table(test, picks, answers, prover_key, args.tries, disagreed)
    (data / "second_table.json").write_text(json.dumps(second, indent=1))
    text = "\n\n".join([
        MARGINS_NOTE,
        "Scores (room = 1 - best simple program)\n" + report.scores_text(by_row),
        "Standard errors of the scores (room's is the named best program's)\n"
        + report.standard_errors_text(by_row),
        "Model minus each program, per-problem difference on the same problems: mean, then standard error\n"
        + report.model_minus_program_text(by_row),
        "Budget (tokens_used is an upper limit on thinking)\n" + report.budgets_text(by_row, allowance),
        "Problem by problem (model gets a problem: more than half its tries right; a program: more than half its "
        "weight on the right option). Programs are exact; the model's 3 of 5 is a noisy estimate (a model right "
        "55% of the time on a problem gets it about 59% of the time).\n"
        + report.problem_by_problem_text(four_counts),
        "Counted together: problems the best single program gets, at least one program gets (guessing left out),\n"
        "none gets; and of the last two, how many the model gets (3 of 5 tries right)\n"
        + report.together_text(counted),
        WRONG_ANSWERS_NOTE + "\n" + report.wrong_answers_text(same_wrong),
        "The second table: scored again with the prover's key (search left out)\n" + report.second_table_text(second)])
    renamed_path = data / "raw" / "model_answers_renamed.jsonl"
    if renamed_path.exists():
        renamed = read_jsonl(renamed_path)
        try:
            run_settings.shared_settings(renamed)
            compared = renaming.named_against_renamed(test, picks, answers, renamed, args.tries)
            renaming.check_seeds_and_questions(answers, renamed, read_jsonl(data / "test_problems_renamed.jsonl"))
        except (run_settings.SettingsDiffer, renaming.RenamingError, scoring.ScoringError) as error:
            sys.exit(f"STOP: the renamed answers: {error}")
        (data / "renamed.json").write_text(json.dumps(compared, indent=1))
        text += "\n\n" + RENAMED_NOTE + "\n" + report.renamed_text(compared)
    else:
        (data / "renamed.json").unlink(missing_ok=True)       # from an earlier run with renamed answers
    text += other_allowances(data, test, picks, answers, args.tries,
                             renamed if renamed_path.exists() else None)
    (data / "report.txt").write_text(text + "\n")
    (data / "bars.svg").write_text(report.bars_svg(by_row))
    print(text)


if __name__ == "__main__":
    main()
