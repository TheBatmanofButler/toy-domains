"""Stage 2: run every simple program on the test states and check the programs themselves.

Reads test_states.jsonl and train_states.jsonl from --data; writes program_picks.jsonl and
programs_summary.json. The checks (from cube_plan.md): guessing equals the average share of right turns;
lookahead of up to k turns scores 1 at every distance of k or less, for each k; lookup (the options-only
reader) is within 0.05 of guessing at every distance. Outputs are written first. A failed check is printed
first, before the table, and then stops the stage.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder import scoring  # noqa: E402
from cube_ladder.cube import TURNS  # noqa: E402
from cube_ladder.programs import (guessing, lookahead, lookup, recall, surface_relaxed,  # noqa: E402
                                  surface_strict)
from cube_ladder.report import scores_text  # noqa: E402
from cube_ladder.states import read_jsonl, write_jsonl  # noqa: E402


def run_programs(test, train):
    """Returns ({program: list of picks}, {lookahead program: positions examined per state}, summary).
    Every program that learns is given the test cubes, and refuses to train if any is in `train`."""
    cubes = [s["cube"] for s in test]
    test_cubes = set(cubes)
    picks, positions, summary = {}, {}, {}
    picks["guessing"] = guessing.picks(cubes)
    picks["lookup"] = lookup.picks(cubes, lookup.train(train, test_cubes))
    for version in recall.VERSIONS:
        picks[f"recall_{version}"], failures = recall.picks(cubes, version)
        summary[f"recall_{version}_failures"] = [[test[n]["id"], reason] for n, reason in failures]
    strict = surface_strict.train(train, test_cubes)
    picks["surface_strict"] = surface_strict.picks(cubes, strict)
    summary["surface_strict_strength"] = strict["strength"]
    summary["surface_strict_cross_validation"] = strict["cross_validation"]
    picks["surface_relaxed"] = surface_relaxed.picks(cubes, surface_relaxed.train(train, test_cubes))
    for depth in (1, 2, 3):
        found = [lookahead.search(cube, depth) for cube in cubes]
        picks[f"lookahead_{depth}"] = [pick for pick, _ in found]
        positions[f"lookahead_{depth}"] = [examined for _, examined in found]
    return picks, positions, summary


def failed_checks(test, by_distance, lookup_tolerance):
    """Every check of cube_plan.md's stage 2 that does not hold, as one line each."""
    problems = []
    for distance, row in by_distance.items():
        share = sum(len(s["right_turns"]) / len(TURNS) for s in test if s["distance"] == distance) / row["states"]
        if abs(row["programs"]["guessing"] - share) > 1e-9:
            problems.append(f"distance {distance}: guessing scores {row['programs']['guessing']}, "
                            f"average share of right turns is {share}")
        for depth in (1, 2, 3):
            if distance <= depth and abs(row["programs"][f"lookahead_{depth}"] - 1) > 1e-9:
                problems.append(f"distance {distance}: lookahead_{depth} scores {row['programs'][f'lookahead_{depth}']}, not 1")
        if abs(row["programs"]["lookup"] - row["programs"]["guessing"]) > lookup_tolerance:
            problems.append(f"distance {distance}: lookup (options only) scores {row['programs']['lookup']:.3f}, "
                            f"guessing {row['programs']['guessing']:.3f}: the options may leak something")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--lookup-tolerance", type=float, default=0.05)
    args = parser.parse_args(argv)
    data = Path(args.data)
    test, train = read_jsonl(data / "test_states.jsonl"), read_jsonl(data / "train_states.jsonl")
    if {s["cube"] for s in test} & {s["cube"] for s in train}:
        sys.exit("STOP: a test state is in the training set")

    picks, positions, summary = run_programs(test, train)
    records = []
    for program, program_picks in picks.items():
        for n, (state, pick) in enumerate(zip(test, program_picks)):
            record = {"state_id": state["id"], "program": program, "weights": pick,
                      "score": scoring.score_pick(pick, state["right_turns"])}
            if program in positions:
                record["positions_examined"] = positions[program][n]
            records.append(record)
    write_jsonl(data / "program_picks.jsonl", records)
    by_distance = scoring.scores_by_distance(test, records)
    summary["scores_by_distance"] = by_distance
    (data / "programs_summary.json").write_text(json.dumps(summary, indent=1))
    problems = failed_checks(test, by_distance, args.lookup_tolerance)
    if problems:   # reported first, so it cannot be missed under the table
        print("STOP: checks on the programs failed:\n" + "\n".join(problems) + "\n")
    print(scores_text(by_distance))
    for version in recall.VERSIONS:
        print(f"recall_{version}: the method failed on {len(summary[f'recall_{version}_failures'])} cubes")
    print(f"surface_strict: strength chosen {summary['surface_strict_strength']}")
    if problems:
        sys.exit("STOP: checks on the programs failed (listed at the top)")
    print("checks on the programs hold")


if __name__ == "__main__":
    main()
