"""Settles two counts of the same library into the final files (settled point 9 of the specification).

Whether a deriving run reaches the 60-second cap can change from one count to the next, so an axiom set can have
a usable list of facts in one count and none in the other. Such a set is unsettled and nothing derived from it
is used. Everything else must be the same in both counts, or settling stops. Reads only the two counts' files.
"""
import gzip
import json
import shutil
from pathlib import Path

from tptp_count.bins import bin_of
from tptp_count.prover import DECIDING, PROVED

# For an axiom set with no usable list in both counts, which of its deriving runs were cut off (its line's "runs",
# "not_finished" and "printed", and its output under calls/) may differ and is not compared: a run at the time
# cap finishes in one count and not in the next. Such sets are named in settled.json.
FINAL = ("files.jsonl", "problems.jsonl", "derived_facts.jsonl", "settled.json")


class SettleError(RuntimeError):
    pass


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _read_count(folder):
    folder = Path(folder)
    work = {}
    for path in sorted((folder / "work" / "problems").glob("*.json")):
        result = json.loads(path.read_text())
        if "axiom_set" not in result:
            raise SettleError(f"{path}: no axiom set number in the saved result; make this count again")
        work[result["path"]] = result
    return {"folder": folder, "files": _jsonl(folder / "files.jsonl"),
            "problems": {p["id"]: p for p in _jsonl(folder / "problems.jsonl")},
            "sets": _jsonl(folder / "derived_facts.jsonl"), "work": work}


def _calls(count, name):
    """A file under calls/ as bytes, or None if there is none."""
    path = count["folder"] / "calls" / f"{name}.jsonl.gz"
    return path.read_bytes() if path.exists() else None


def _unaided_call(count, problem_id):
    """The first line of a problem's calls/ file: its unaided call, with its full output."""
    with gzip.open(count["folder"] / "calls" / f"{problem_id}.jsonl.gz", "rt") as f:
        return json.loads(f.readline())


def _settle_sets(a, b):
    """-> (numbers of the unsettled sets, first files of the sets cut off differently)."""
    if [(s["first_file"], s["axioms"]) for s in a["sets"]] != [(s["first_file"], s["axioms"]) for s in b["sets"]]:
        raise SettleError("the two counts hold different axiom sets")
    unsettled, cut_off_differently = [], []
    for set_a, set_b in zip(a["sets"], b["sets"]):
        number, name = set_a["axiom_set"], f"axiom set {set_a['axiom_set']} ({set_a['first_file']})"
        output_a, output_b = _calls(a, f"axiom_set_{number}"), _calls(b, f"axiom_set_{number}")
        if (set_a["facts"] is None) != (set_b["facts"] is None):
            unsettled.append(number)
        elif set_a["facts"] is None:
            # the set's other fields (its number, first file and axioms, and facts None) are the same here
            if set_a != set_b or output_a != output_b:
                cut_off_differently.append(set_a["first_file"])
        elif set_a["facts"] != set_b["facts"]:
            raise SettleError(f"{name}: the two counts derived two different lists of facts")
        elif set_a != set_b or output_a != output_b:
            raise SettleError(f"{name}: its deriving runs differ between the two counts")
    return unsettled, cut_off_differently


def _unsettled_file(a, b, file):
    """The final (files.jsonl line, problems.jsonl line, calls/ bytes) of a file on an unsettled set."""
    result_a, result_b = a["work"][file["path"]], b["work"][file["path"]]
    problem_id = result_a["id"]
    unaided_a, unaided_b = _unaided_call(a, problem_id), _unaided_call(b, problem_id)
    if (result_a["unaided"], unaided_a) != (result_b["unaided"], unaided_b):
        raise SettleError(f"{file['path']}: its unaided call differs between the two counts")
    if unaided_a["ending"] == PROVED or unaided_a["ending"] not in DECIDING:
        # the facts were not needed: both counts wrote the same lines
        return file, a["problems"][problem_id], _calls(a, problem_id)
    bin_name, why = bin_of(True, file["status"], None, unaided_a["ending"], unsettled=True)
    line = {**file, "bin": bin_name, "why": why, "problem_id": problem_id}
    problem = {k: result_a[k] for k in ("id", "path", "area", "axioms", "goal", "unaided", "seed")}
    return line, problem, gzip.compress((json.dumps(unaided_a) + "\n").encode(), mtime=0)


def settle(first, second, out):
    """Writes the final files.jsonl, problems.jsonl, derived_facts.jsonl (where an unsettled set's record has
    "unsettled": true and no facts), calls/ and settled.json into `out`,
    from the counts in `first` and `second`, again from scratch each time. Raises SettleError, naming the set or
    the file, where the two counts differ in anything but an unsettled set or which runs of a set with no usable
    list in either count were cut off."""
    a, b = _read_count(first), _read_count(second)
    if [f["path"] for f in a["files"]] != [f["path"] for f in b["files"]]:
        raise SettleError("the two counts read different files")
    unsettled, cut_off_differently = _settle_sets(a, b)
    on_unsettled = {path for path, result in a["work"].items() if result["axiom_set"] in unsettled}
    if on_unsettled != {path for path, result in b["work"].items() if result["axiom_set"] in unsettled}:
        raise SettleError("the two counts put different files on the unsettled axiom sets")
    out = Path(out)
    for name in FINAL:
        (out / name).unlink(missing_ok=True)
    shutil.rmtree(out / "calls", ignore_errors=True)
    (out / "calls").mkdir(parents=True)
    file_lines, problem_lines = [], []
    for file_a, file_b in zip(a["files"], b["files"]):
        problem_id = file_a["problem_id"]
        if file_a["path"] in on_unsettled:
            line, problem, calls = _unsettled_file(a, b, file_a)
            problem_id = problem["id"]
        else:
            line, problem, calls = file_a, a["problems"].get(problem_id), _calls(a, Path(file_a["path"]).stem)
            if (file_a, problem, calls) != (file_b, b["problems"].get(file_b["problem_id"]),
                                            _calls(b, Path(file_b["path"]).stem)):
                raise SettleError(f"{file_a['path']}: differs between the two counts")
        file_lines.append(line)
        if line["problem_id"] is not None:
            problem_lines.append(problem)
        if calls is not None:
            (out / "calls" / f"{Path(file_a['path']).stem}.jsonl.gz").write_bytes(calls)
    for axiom_set in a["sets"]:
        output = _calls(a, f"axiom_set_{axiom_set['axiom_set']}")
        if output is not None:
            (out / "calls" / f"axiom_set_{axiom_set['axiom_set']}.jsonl.gz").write_bytes(output)
    # An unsettled set's facts are not used, so the final record shows none; each count's own record stays in
    # that count's folder.
    sets = [{**s, "facts": None, "unsettled": True} if s["axiom_set"] in unsettled else s for s in a["sets"]]
    for name, lines in (("files.jsonl", file_lines), ("problems.jsonl", problem_lines),
                        ("derived_facts.jsonl", sets)):
        (out / name).write_text("".join(json.dumps(line) + "\n" for line in lines))
    settled = {"unsettled": [{"axiom_set": n, "first_file": a["sets"][n]["first_file"],
                              "files": sorted(p for p in on_unsettled if a["work"][p]["axiom_set"] == n)}
                             for n in unsettled],
               "cut off differently": cut_off_differently}
    (out / "settled.json").write_text(json.dumps(settled, indent=1) + "\n")
    return settled
