"""Stage 2: the prover's key at the experiment's limit (prover.LIMIT, 4,000), then the simple programs.

`--limit N` makes the key at another limit instead, for looking at how the prover's verdicts move with the limit;
the experiment's runs use the default.

Before anything else it refuses to start under a shell limit on computing time or memory (such a limit reaches the
prover and can stop a call that would have finished), checks the prover's version and writes settings.json: the
seed, the limit, the prover's version and checksum, the fixed environment and the C library's version; a stage
started again carries on only with the same settings. The key's calls are made twice and settled
(mizar_ladder/settle.py): the prover's search changes from run to run, and a call on which the two runs disagree
decides nothing; the share of such calls is printed with the prover's bins and saved. A stopped stage started again
makes only the calls still missing. Writes prover_calls.jsonl, raw/calls/, settled.json, prover_key.jsonl,
program_picks.jsonl and programs_summary.json (with the programs counted together, mizar_ladder/together.py).
Check, from mizar_plan.md: guessing is 1 in 30. A failed check is printed first; then, before anything else, how
far options_only and recall sit above guessing.
"""
import argparse
import json
import os
import resource
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mizar_ladder import prover, prover_key, scoring, together  # noqa: E402
from mizar_ladder.library import Library, LibraryError  # noqa: E402
from mizar_ladder.problems import OPTIONS, read_jsonl, write_jsonl  # noqa: E402
from mizar_ladder.programs import (guessing, lookup, options_only, recall, search,  # noqa: E402
                                   surface_symbols, surface_trained)
from mizar_ladder.programs.common import Counts  # noqa: E402
from mizar_ladder.report import scores_text, together_text  # noqa: E402
from mizar_ladder.settle import SettleError  # noqa: E402

SHELL_LIMITS = {"computing time": resource.RLIMIT_CPU, "address space": resource.RLIMIT_AS,
                "data": resource.RLIMIT_DATA}


def shell_limits():
    """{name: "unlimited" or the limit} for this process's own limits on computing time and memory."""
    found = {}
    for name, which in SHELL_LIMITS.items():
        soft, _ = resource.getrlimit(which)
        found[name] = "unlimited" if soft == resource.RLIM_INFINITY else soft
    return found


def settings(seed, program, prover_program, limit=prover.LIMIT):
    return {"seed": seed, "limit": limit, "prover_version": prover.VERSION,
            "prover_checksum": prover.program_checksum(program),
            "prover_program_checksum": None if prover_program is None else prover.program_checksum(prover_program),
            "prover_environment": prover.ENVIRONMENT, "c_library": os.confstr("CS_GNU_LIBC_VERSION")}


def check_settings(path, found):
    """Writes settings.json, or stops if it holds other settings."""
    if path.exists():
        saved = json.loads(path.read_text())
        if saved != found:
            differing = sorted(k for k in set(saved) | set(found) if saved.get(k) != found.get(k))
            sys.exit(f"STOP: {path} holds results made with other settings: {', '.join(differing)}")
    path.write_text(json.dumps(found, indent=1))


def run_programs(test, train, calls, counts):
    picks = {"guessing": guessing.picks(test), "recall": recall.picks(test, counts),
             "lookup": lookup.picks(test, lookup.train(train, counts)),
             "surface_symbols": surface_symbols.picks(test, counts), "search": search.picks(test, calls)}
    picks["options_only"] = options_only.picks(test, options_only.train(train, counts), counts)
    trained = surface_trained.train(train, counts)
    picks["surface_trained"] = surface_trained.picks(test, trained, counts)
    summary = {"surface_trained_strength": trained["strength"],
               "surface_trained_cross_validation": {str(k): v for k, v in trained["cross_validation"].items()}}
    return picks, summary


def disagreement(data):
    """The share of the key's calls on which the two runs disagreed, and how."""
    key = json.loads((data / "settled.json").read_text())
    return {"key": key["unsettled_share"], "key_calls": key["calls"], "key_by_way": key["by_way"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--prover", required=True, help="command that starts the pinned prover")
    parser.add_argument("--prover-program", help="the prover program behind --prover, when it is a start script")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=prover.LIMIT,
                        help=f"processed-clause limit of the key (the experiment's is {prover.LIMIT})")
    parser.add_argument("--checksums", help="JSON {file: sha256} to check against instead of README.md "
                                            "(for the made-up library in the tests)")
    args = parser.parse_args(argv)
    limited = {name: limit for name, limit in shell_limits().items() if limit != "unlimited"}
    if limited:
        sys.exit("REFUSED: the shell limits " + ", ".join(f"{n} to {v}" for n, v in limited.items())
                 + "; start the stage where these are unlimited (ulimit -t, -v, -d)")
    data = Path(args.data)
    try:
        prover.check_version(args.prover)
        library = Library(args.library, json.loads(Path(args.checksums).read_text()) if args.checksums else None)
    except (prover.ProverError, LibraryError) as error:
        sys.exit(f"STOP: {error}")
    found = settings(args.seed, args.prover, args.prover_program, args.limit)
    check_settings(data / "settings.json", found)
    test, train = read_jsonl(data / "test_problems.jsonl"), read_jsonl(data / "train_problems.jsonl")
    try:
        key = prover_key.run(library, test, args.limit, data, args.prover, args.workers)
    except SettleError as error:
        sys.exit(f"STOP: settling the prover's calls: {error}")
    calls = read_jsonl(data / "prover_calls.jsonl")
    picks, summary = run_programs(test, train, calls, Counts.for_test_set(library, test))
    lines = [{"problem_id": p["id"], "program": name, "weights": weights,
              "score": scoring.score_pick(weights, scoring.right_options(p))}
             for name, found_picks in picks.items() for p, weights in zip(test, found_picks)]
    write_jsonl(data / "program_picks.jsonl", lines)
    by_row = scoring.scores_by_row(test, lines)
    counted = together.counted_together(test, lines)
    failed = []
    if abs(by_row[scoring.ALL]["programs"]["guessing"] - 1 / OPTIONS) > 1e-9:
        failed.append(f"guessing scores {by_row[scoring.ALL]['programs']['guessing']}, not 1/30")
    bins = {name: sum(line["bin"] == name for line in key) for name in prover_key.BINS}
    held_back_nothing_left = sum(line["held_back_ending"] == prover.NOTHING_LEFT for line in key)
    disagreed = disagreement(data)
    (data / "programs_summary.json").write_text(json.dumps(
        {"limit": args.limit, "scores": by_row, "counted_together": counted, "prover_bins": bins,
         "runs_disagreed": disagreed, "failed_checks": failed,
         "held_back_call_nothing_left": held_back_nothing_left, **summary}, indent=1))
    for problem in failed:
        print(f"FAILED CHECK: {problem}")
    every = by_row[scoring.ALL]
    for name in ("options_only", "recall"):
        print(f"{name} sits {every['programs'][name] - every['programs']['guessing']:+.3f} above guessing "
              f"({every['programs'][name]:.3f} against {every['programs']['guessing']:.3f})")
    print(f"limit: {args.limit} processed clauses"
          + (" (the experiment's)" if args.limit == prover.LIMIT else f" (not the experiment's {prover.LIMIT})"))
    print("prover bins: " + ", ".join(f"{name} {count}" for name, count in bins.items()))
    print(f"calls on which the two runs disagreed: {disagreed['key']:.3f} of the key's {disagreed['key_calls']}")
    print(f"problems whose call with the held-back fact ended as nothing left: {held_back_nothing_left}")
    print(scores_text(by_row))
    print("Counted together (a program gets a problem: more than half its weight on the right option; guessing "
          "left out of at least one)")
    print(together_text(counted))
    if failed:
        sys.exit("STOP: checks on the programs or the prover failed (see above)")


if __name__ == "__main__":
    main()
