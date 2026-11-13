"""Stage 1: build the test and training states, with distances and right turns from the perfect solver.

First the solver must reproduce the old run's distance and right turns on the saved old states; if it does
not, nothing is built. Writes test_states.jsonl, train_states.jsonl and build_summary.json to --data.
For a tiny trial without the real solver, --brute-force-scramble N draws cubes by N random turns instead
and uses the brute-force solver (only for N up to 5).
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder.cube import SOLVED, TURNS, apply_turns  # noqa: E402
from cube_ladder.solver import BruteForceSolver, PerfectSolver  # noqa: E402
from cube_ladder.states import (AS_DRAWN_DISTANCES, FOLLOW_HOME_DISTANCES, Rules, build_states,  # noqa: E402
                                read_jsonl, write_jsonl)


def distance_list(text):
    """'2-16' or '17,18' -> tuple of ints."""
    if "-" in text:
        low, high = text.split("-")
        return tuple(range(int(low), int(high) + 1))
    return tuple(int(part) for part in text.split(","))


def check_old_states(solver, path):
    old = read_jsonl(path)
    found = solver.distances([s["cube"] for s in old])
    right = solver.right_turns_many([s["cube"] for s in old], [d for d, _ in found])
    for state, (distance, _), turns in zip(old, found, right):
        if distance != state["distance"] or sorted(turns) != sorted(state["right_turns"]):
            sys.exit(f"STOP: old state {state['id']}: solver says distance {distance}, right turns {sorted(turns)}; "
                     f"the old run says {state['distance']}, {sorted(state['right_turns'])}")
    print(f"solver reproduces the old run on all {len(old)} old states")


def right_turn_summary(states):
    """Per distance: mean number of right turns and the share of states with exactly one."""
    summary = {}
    for distance in sorted({s["distance"] for s in states}):
        counts = [len(s["right_turns"]) for s in states if s["distance"] == distance]
        summary[distance] = {"states": len(counts), "mean_right_turns": sum(counts) / len(counts),
                             "share_with_one": sum(c == 1 for c in counts) / len(counts)}
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="folder to write the states to")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--solver-dir", help="folder holding nxopt23 and its table")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--old-states", help="saved old-run states (cube, distance, right_turns) to reproduce first")
    parser.add_argument("--brute-force-scramble", type=int, help="tiny trial: cubes made by this many random turns")
    parser.add_argument("--test-per-distance", type=int, default=100)
    parser.add_argument("--train-per-distance", type=int, default=1000)
    parser.add_argument("--follow-home", type=distance_list, default=FOLLOW_HOME_DISTANCES)
    parser.add_argument("--as-drawn", type=distance_list, default=AS_DRAWN_DISTANCES)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--give-up-after", type=int, default=2000,
                        help="a distance's training set is complete after this many random cubes in a row offer no new state")
    args = parser.parse_args(argv)

    if args.brute_force_scramble:
        solver = BruteForceSolver()

        def draw_cube(rng):
            return apply_turns(SOLVED, [rng.choice(TURNS) for _ in range(args.brute_force_scramble)])
    elif args.solver_dir:
        solver = PerfectSolver(args.solver_dir, threads=args.threads)
        draw_cube = None
    else:
        sys.exit("give --solver-dir, or --brute-force-scramble for a tiny trial")
    if args.old_states:
        check_old_states(solver, args.old_states)
    elif not args.brute_force_scramble:
        sys.exit("the real build must first reproduce the old run: give --old-states")

    rules = Rules(args.follow_home, args.as_drawn, args.give_up_after, allow_repeated_draws=draw_cube is not None)
    options = {"draw_cube": draw_cube} if draw_cube else {}
    test, train, summary = build_states(solver, args.seed, random.Random(args.seed), args.test_per_distance,
                                        args.train_per_distance, rules, batch_size=args.batch_size, **options)
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    write_jsonl(data / "test_states.jsonl", test)
    write_jsonl(data / "train_states.jsonl", train)
    summary["test_right_turns"] = right_turn_summary(test)
    summary["train_right_turns"] = right_turn_summary(train)
    (data / "build_summary.json").write_text(json.dumps(summary, indent=1))
    print(f"wrote {len(test)} test states and {len(train)} training states to {data}")
    print(f"random cubes used {summary['random_cubes_used']}, not used {summary['random_cubes_not_used']}; "
          f"solver seconds {summary['solver_seconds']:.1f}")
    print(f"training states per distance: {summary['training_count_by_distance']}")
    if summary["training_distances_left_short"]:
        print(f"training distances left short (too few new states close to solved): "
              f"{summary['training_distances_left_short']}")
    for distance, row in summary["test_right_turns"].items():
        print(f"distance {distance:2d}: {row['states']} test states, mean right turns {row['mean_right_turns']:.2f}, "
              f"share with one {row['share_with_one']:.2f}")


if __name__ == "__main__":
    main()
