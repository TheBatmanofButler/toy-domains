"""Stage 1: build the test and training problems, with depths and right moves from the shortest-proof search.

First the search must reproduce the earlier run's depth, right moves and counts on the saved earlier problems;
if it does not, nothing is built. After the build, the plain search must agree with it on the first test
problems of depth 2 and 3. Writes test_problems.jsonl, train_problems.jsonl and build_summary.json to --data.
For a tiny trial: --depths 2,3 --most-moves 3 --test-per-depth 3 --train-per-depth 5.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fe_ladder.identity_text import read_identity  # noqa: E402
from fe_ladder.problems import BuildError, build_problems, read_jsonl, write_jsonl  # noqa: E402
from fe_ladder.shortest import TEN_MINUTES, PlainSearch, solve  # noqa: E402


def depth_list(text):
    return tuple(int(part) for part in text.split(","))


def check_earlier_problems(path):
    """None if the search reproduces every saved earlier problem, else the first difference."""
    earlier = read_jsonl(path)
    for p in earlier:
        found = solve(read_identity(p["equation"]), read_identity(p["goal"]))
        got = (found.depth, found.right, found.proofs, found.sequences)
        wanted = (p["depth"], p["right_moves"], p["proofs"], p["sequences"])
        if got != wanted:
            return f"earlier problem {p['id']}: the search gives depth, right moves, proofs, sequences {got}; the earlier run {wanted}"
    print(f"the search reproduces the earlier run on all {len(earlier)} earlier problems")
    return None


def check_plain_search(test, how_many):
    """None if the plain search agrees on the first `how_many` test problems at each of depths 2 and 3."""
    checked = 0
    for depth in (2, 3):
        for p in [p for p in test if p["depth"] == depth][:how_many]:
            plain = PlainSearch().solve(read_identity(p["equation"]), read_identity(p["goal"]), depth)
            if (plain.depth, plain.right, plain.proofs, plain.sequences) != (p["depth"], p["right_moves"], p["proofs"], p["sequences"]):
                return f"{p['id']}: the plain search gives {plain}"
            checked += 1
    print(f"the plain search agrees on {checked} test problems of depth 2 and 3")
    return None


def depth_summary(problems):
    """Per depth: problems, mean right moves, mean options, share of problems shorter than their planted proof."""
    out = {}
    for depth in sorted({p["depth"] for p in problems}):
        at = [p for p in problems if p["depth"] == depth]
        planted = [len(p["planted"]["first_chain"]) + len(p["planted"]["second_chain"]) for p in at]
        out[depth] = {"problems": len(at), "mean_right_moves": sum(len(p["right_moves"]) for p in at) / len(at),
                      "mean_options": sum(len(p["options"]) for p in at) / len(at),
                      "mean_share_right": sum(len(p["right_moves"]) / len(p["options"]) for p in at) / len(at),
                      "share_shorter_than_planted": sum(p["depth"] < n for p, n in zip(at, planted)) / len(at)}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="folder to write the problems to")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--earlier-problems", help="saved earlier-run problems to reproduce first")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--test-per-depth", type=int, default=300)
    parser.add_argument("--train-per-depth", type=int, default=1000)
    parser.add_argument("--depths", type=depth_list, default=(2, 3, 4, 5))
    parser.add_argument("--most-moves", type=int, default=5)
    parser.add_argument("--most-attempts", type=int, default=1_000_000)
    parser.add_argument("--time-limit", type=float, default=TEN_MINUTES, help="seconds to solve one problem")
    parser.add_argument("--plain-check", type=int, default=20,
                        help="test problems at each of depths 2 and 3 to check against the plain search")
    args = parser.parse_args(argv)

    if args.earlier_problems:
        failure = check_earlier_problems(args.earlier_problems)
        if failure:
            sys.exit(f"STOP: {failure}")
    elif args.depths == (2, 3, 4, 5):
        sys.exit("the real build must first reproduce the earlier run: give --earlier-problems")
    try:
        test, train, summary = build_problems(args.seed, args.test_per_depth, args.train_per_depth, args.depths,
                                              args.most_moves, args.most_attempts, args.workers, args.time_limit)
    except BuildError as error:
        sys.exit(f"STOP: {error}")
    failure = check_plain_search(test, args.plain_check)
    if failure:
        sys.exit(f"STOP: {failure}")
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    write_jsonl(data / "test_problems.jsonl", test)
    write_jsonl(data / "train_problems.jsonl", train)
    summary["test_by_depth"], summary["train_by_depth"] = depth_summary(test), depth_summary(train)
    (data / "build_summary.json").write_text(json.dumps(summary, indent=1))
    print(f"wrote {len(test)} test problems and {len(train)} training problems to {data}")
    print(f"attempts {summary['attempts']}, by kind {summary['count_by_kind']}")
    print(f"seconds: build {summary['build_seconds']:.0f}, solving by kind {summary['solve_seconds_by_kind']}")
    print(f"training problems per depth: {summary['training_count_by_depth']}")
    if summary["training_depths_left_short"]:
        print(f"training depths left short: {summary['training_depths_left_short']}")
    for depth, row in summary["test_by_depth"].items():
        print(f"depth {depth}: {row['problems']} test problems, mean right moves {row['mean_right_moves']:.2f} of "
              f"{row['mean_options']:.2f} options (share right {row['mean_share_right']:.3f}), "
              f"shorter than the planted proof {row['share_shorter_than_planted']:.2f}")


if __name__ == "__main__":
    main()
