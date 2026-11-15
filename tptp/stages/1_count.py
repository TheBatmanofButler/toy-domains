"""Stage 1: read the library and count, twice, and settle the two counts. Before anything else, refuses to start
if this process has a shell limit on computing time or memory, since such a limit reaches the prover and can
change how its runs end. Before anything is counted, checks the prover's version and runs the earlier pilot's
200 calls, comparing endings and counts, and stops on any difference: that is what shows the prover behaves here
as it did for the pilot. Then makes the count into --data/first/ and again into --data/second/ (each can be
stopped and started again on its own), settles the two into the final files in --data (settle.py: an axiom set
whose facts differ between the counts is not used, and any other difference stops the stage), and runs the
plan's other checks on the final files: a repeat of one call in twenty, every file in exactly one bin, and no
call that did not decide counted as "does not prove". A failed check is printed first and the stage ends with an
error. Writes files.jsonl, problems.jsonl, derived_facts.jsonl, calls/, settled.json and stage1_checks.json to
--data. The time taken is printed at the end only, so that no file written depends on it.

With --settle FIRST SECOND, two finished count folders are only settled into --data: no prover is started.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tptp_count import checks, prover  # noqa: E402
from tptp_count.count import count, shell_limits  # noqa: E402
from tptp_count.settle import SettleError, settle  # noqa: E402


def _print_failures(name, failures):
    print(f"CHECK FAILED: {name} ({len(failures)}):")
    print("\n".join(f"  {line}" for line in failures[:20]))


def main(argv=None):
    started = time.monotonic()
    try:
        return _stage(argv)
    finally:
        print(f"time taken: {time.monotonic() - started:.0f} s")


def _settle(first, second, data):
    """Settles the two counts into `data`; None if they do not agree."""
    try:
        settled = settle(first, second, data)
    except SettleError as failure:
        _print_failures("the two counts agree", [str(failure)])
        return None
    print(f"settled: {len(settled['unsettled'])} axiom sets unsettled "
          f"({sum(len(s['files']) for s in settled['unsettled'])} files on them); "
          f"{len(settled['cut off differently'])} with no usable list in either count cut off differently")
    for axiom_set in settled["unsettled"]:
        print(f"  unsettled: {axiom_set['first_file']} ({', '.join(axiom_set['files'])})")
    for first_file in settled["cut off differently"]:
        print(f"  cut off differently: {first_file}")
    return settled


def _stage(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", help="the TPTP library's folder (holding Problems/ and Axioms/)")
    parser.add_argument("--data", required=True, help="folder to write to")
    parser.add_argument("--prover", help="command that starts the pinned prover")
    parser.add_argument("--prover-program", help="the prover program behind --prover, when --prover is a start "
                                                 "script; its checksum is recorded too")
    parser.add_argument("--pilot-calls", help="the earlier pilot's saved calls, pilot_calls.jsonl.gz")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--settle", nargs=2, metavar=("FIRST", "SECOND"),
                        help="only settle these two finished count folders into --data")
    args = parser.parse_args(argv)
    if args.settle:
        Path(args.data).mkdir(parents=True, exist_ok=True)
        return 0 if _settle(*args.settle, args.data) is not None else 1
    missing = [name for name in ("library", "prover", "pilot_calls", "seed") if getattr(args, name) is None]
    if missing:
        parser.error("these are needed to count: " + ", ".join("--" + name.replace("_", "-") for name in missing))

    limited = {name: limit for name, limit in shell_limits().items() if limit != "unlimited"}
    if limited:
        print("REFUSED: the shell limits " + ", ".join(f"{name} to {limit}" for name, limit in limited.items())
              + "; start the stage where these are unlimited (ulimit -t, -v, -d)")
        return 1
    prover.check_version(args.prover)
    pilot = checks.pilot_calls(args.pilot_calls, args.prover)
    if pilot:
        _print_failures("pilot calls, before counting", pilot)
        return 1
    print("check held: pilot calls, before counting")
    data = Path(args.data)
    for folder in (data / "first", data / "second"):
        count(args.library, folder, args.prover, args.seed, args.workers, args.prover_program)
    if _settle(data / "first", data / "second", data) is None:
        return 1
    results = {"repeat of one call in twenty": checks.repeat(data, args.prover),
               "every file in exactly one bin": checks.one_bin_each(args.library, data),
               "no call that did not decide counted as does not prove": checks.no_silent_does_not_prove(data)}
    (data / "stage1_checks.json").write_text(
        json.dumps({"pilot calls, before counting": pilot, **results}, indent=1) + "\n")
    failed = [name for name, failures in results.items() if failures]
    for name in failed:
        _print_failures(name, results[name])
    for name in results:
        if name not in failed:
            print(f"check held: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
