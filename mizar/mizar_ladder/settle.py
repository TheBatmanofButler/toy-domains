"""Settles two runs of the same set of prover calls into the final files.

In its automatic mode the prover's search is not the same from one run to the next: its clause counts change,
and now and then its verdict. Nothing is done to force it to repeat itself; the two runs measure how steady it is.
A call is settled when both runs give the same ending and, when both proved the theorem, agree on whether the
option is among the facts the proof uses. Otherwise it is unsettled: its final ending is the word "unsettled",
with both runs' endings beside it, its used facts and counts are null (both runs' records stay under raw/), and it
decides nothing. Clause counts, and which other facts a proof uses, are not compared; a settled call's record is
the first run's. Nothing here stops the stage. Reads only the two runs'
files; starts no prover.
"""
import json
import shutil
from pathlib import Path

from mizar_ladder import prover
from mizar_ladder.calls import FIELDS, read_records

UNSETTLED = "unsettled"
OUTPUTS = ("prover_calls.jsonl", "settled.json")
ENDINGS_DIFFERED, USE_DIFFERED = "the endings differed", "the use of the option differed"


class SettleError(RuntimeError):
    pass


def decided(record):
    """True when a final call decided: a deciding ending, the same in both runs."""
    return record["ending"] in prover.DECIDING


def option_used(record):
    return record["option_name"] is not None and record["option_name"] in record["used"]


def why_unsettled(one, two):
    """None when the two runs agree on the call; otherwise which way they differed."""
    if one["ending"] != two["ending"]:
        return ENDINGS_DIFFERED
    if one["ending"] == prover.PROVED and option_used(one) != option_used(two):
        return USE_DIFFERED
    return None


def settle(first, second, out):
    """Writes the final prover_calls.jsonl, raw/calls/ (the first run's outputs) and settled.json into `out`,
    after clearing what an earlier settling wrote there. Returns the final records. Stops (SettleError) only if
    the two runs are not runs of the same calls."""
    first, second, out = Path(first), Path(second), Path(out)
    for name in OUTPUTS:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "raw" / "calls", ignore_errors=True)
    a, b = read_records(first / "prover_calls.jsonl"), read_records(second / "prover_calls.jsonl")
    if [(r["problem_id"], r["option"]) for r in a] != [(r["problem_id"], r["option"]) for r in b]:
        raise SettleError("the two runs made different calls")
    final, unsettled = [], []
    for one, two in zip(a, b):
        why = why_unsettled(one, two)
        if why is None:
            final.append(one)
            continue
        cleared = {field: None for field in FIELDS if field != "ending"}
        final.append({**one, **cleared, "ending": UNSETTLED, "endings": [one["ending"], two["ending"]]})
        unsettled.append({"problem_id": one["problem_id"], "option": one["option"],
                          "option_name": one["option_name"], "why": why, "endings": [one["ending"], two["ending"]]})
    calls = out / "raw" / "calls"
    calls.mkdir(parents=True, exist_ok=True)
    for path in sorted((first / "raw" / "calls").glob("*.jsonl.gz")):
        shutil.copyfile(path, calls / path.name)
    (out / "prover_calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in final))
    (out / "settled.json").write_text(json.dumps(summary(len(final), unsettled), indent=1) + "\n")
    return final


def summary(calls, unsettled):
    """What settled.json holds: the number of calls, of unsettled calls and their share, by the way they
    differed, and the unsettled calls by problem, option number and the option's fact name."""
    differed = {why: sum(u["why"] == why for u in unsettled) for why in (ENDINGS_DIFFERED, USE_DIFFERED)}
    return {"calls": calls, "unsettled": len(unsettled), "unsettled_share": len(unsettled) / calls if calls else None,
            "by_way": differed, "unsettled_calls": unsettled}
