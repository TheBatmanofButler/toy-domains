"""Stage 2: run every simple program on the test problems and check the programs themselves.

Reads test_problems.jsonl and train_problems.jsonl from --data; writes program_picks.jsonl and
programs_summary.json. The checks (from fe_plan.md): guessing equals the average share of right moves; lookahead
of up to k moves scores 1 at every depth of k or less, for each k. The options-only line (lookup) is reported
and nothing waits on it. Outputs are written first. A failed check is printed first, before the table, and then
stops the stage.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fe_ladder import scoring  # noqa: E402
from fe_ladder.problems import read_jsonl, write_jsonl  # noqa: E402
from fe_ladder.programs import (guessing, lookahead, lookup, narrow_deep, recall, surface_relaxed,  # noqa: E402
                                surface_strict)
from fe_ladder.report import scores_text  # noqa: E402


def run_programs(test, train, seed):
    """Returns ({program: list of picks}, {search program: (budget name, budget per problem)}, summary). Each
    lookahead's budget is the move sequences it examined; narrow-and-deep's, the identities it worked out.
    Every program that learns is given the test problems, and refuses to train if any is in `train`."""
    picks, budgets, summary = {}, {}, {}
    picks["guessing"] = guessing.picks(test)
    picks["lookup"] = lookup.picks(test, lookup.train(train, test))
    picks["recall"] = recall.picks(test)
    strict = surface_strict.train(train, test)
    picks["surface_strict"] = surface_strict.picks(test, strict)
    summary["surface_strict_strength"] = strict["strength"]
    summary["surface_strict_cross_validation"] = strict["cross_validation"]
    picks["surface_relaxed"] = surface_relaxed.picks(test, surface_relaxed.train(train, test))
    for depth in (1, 2, 3):
        found = [lookahead.search(problem, depth) for problem in test]
        picks[f"lookahead_{depth}"] = [pick for pick, _ in found]
        budgets[f"lookahead_{depth}"] = ("sequences_examined", [examined for _, examined in found])
    found = [narrow_deep.search(problem, seed) for problem in test]
    picks["narrow_deep"] = [pick for pick, _ in found]
    budgets["narrow_deep"] = ("identities_worked_out", [worked_out for _, worked_out in found])
    summary["narrow_deep_settings"] = {"paths": narrow_deep.PATHS, "most_moves": narrow_deep.MOST_MOVES, "seed": seed}
    return picks, budgets, summary


def failed_checks(test, by_depth):
    """Every check of fe_plan.md's stage 2 that does not hold, as one line each."""
    problems = []
    for depth, row in by_depth.items():
        here = [p for p in test if p["depth"] == depth]
        share = sum(len(p["right_moves"]) / len(p["options"]) for p in here) / len(here)
        if abs(row["programs"]["guessing"] - share) > 1e-9:
            problems.append(f"depth {depth}: guessing scores {row['programs']['guessing']}, "
                            f"average share of right moves is {share}")
        for k in (1, 2, 3):
            if depth <= k and abs(row["programs"][f"lookahead_{k}"] - 1) > 1e-9:
                problems.append(f"depth {depth}: lookahead_{k} scores {row['programs'][f'lookahead_{k}']}, not 1")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    args = parser.parse_args(argv)
    data = Path(args.data)
    test, train = read_jsonl(data / "test_problems.jsonl"), read_jsonl(data / "train_problems.jsonl")
    seeds = {p["seed"] for p in test + train}
    if len(seeds) != 1:
        sys.exit(f"STOP: the problems come from more than one build seed: {sorted(seeds)}")

    picks, budgets, summary = run_programs(test, train, seeds.pop())
    records = []
    for program, program_picks in picks.items():
        for n, (problem, pick) in enumerate(zip(test, program_picks)):
            record = {"problem_id": problem["id"], "program": program, "weights": pick,
                      "score": scoring.score_pick(pick, problem["right_moves"], len(problem["options"]))}
            if program in budgets:
                name, per_problem = budgets[program]
                record[name] = per_problem[n]
            records.append(record)
    write_jsonl(data / "program_picks.jsonl", records)
    by_depth = scoring.scores_by_depth(test, records)
    summary["scores_by_depth"] = by_depth
    (data / "programs_summary.json").write_text(json.dumps(summary, indent=1))
    problems = failed_checks(test, by_depth)
    if problems:   # reported first, so it cannot be missed under the table
        print("STOP: checks on the programs failed:\n" + "\n".join(problems) + "\n")
    print(scores_text(by_depth))
    print(f"surface_strict: strength chosen {summary['surface_strict_strength']}")
    for depth, row in by_depth.items():
        print(f"depth {depth}: options only (lookup) {row['programs']['lookup']:.3f}, "
              f"guessing {row['programs']['guessing']:.3f}; sequences examined {row['sequences_examined_mean']}, "
              f"identities worked out {row['identities_worked_out_mean']}")
    if problems:
        sys.exit("STOP: checks on the programs failed (listed at the top)")
    print("checks on the programs hold")


if __name__ == "__main__":
    main()
