"""Stage 2's figures, from files.jsonl, problems.jsonl and settled.json only: the count in each bin, the three
main bins as shares of their total, the clauses needed by the files proved unaided, the right facts per problem,
the three main bins by subject area, and the files set aside because the two counts did not derive the same
facts for their axioms. Writes bins.json and prints the tables.
"""
import json
import statistics
from pathlib import Path

from tptp_count.bins import A_PROBLEM, BINS, MAIN, PROVED_UNAIDED, UNSETTLED
from tptp_count.prover import LIMIT

BAND = 20   # clauses needed are shown in bands of this width, up to the limit; the first band starts at 0, so
            # that no value can fall outside the table


class ReportError(ValueError):
    pass


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def bin_counts(files):
    counts = {name: 0 for name in BINS}
    for file in files:
        if file["bin"] not in counts:
            raise ReportError(f"{file['path']}: unknown bin {file['bin']!r}")
        counts[file["bin"]] += 1
    return counts


def main_shares(counts):
    total = sum(counts[name] for name in MAIN)
    return {name: (counts[name] / total if total else None) for name in MAIN}


def clauses_needed(files, problems):
    """For the files proved unaided: the clauses processed by the unaided call."""
    by_id = {p["id"]: p for p in problems}
    values = sorted(by_id[f["problem_id"]]["unaided"]["processed"] for f in files if f["bin"] == PROVED_UNAIDED)
    bands = {}
    for low in range(0, LIMIT, BAND):
        first = low + 1 if low else 0
        bands[f"{first}-{low + BAND}"] = sum(first <= v <= low + BAND for v in values)
    return {"count": len(values), "median": statistics.median(values) if values else None,
            "max": max(values) if values else None, "bands": bands, "values": values}


def right_facts(files, problems):
    """For each problem (bin "a problem"): how many of its 30 facts are right; how many problems have each
    number; and how many problems have an option whose call did not decide, for which the number is a lower
    bound (that option might have been right)."""
    by_id = {p["id"]: p for p in problems}
    in_bin = [by_id[f["problem_id"]] for f in files if f["bin"] == A_PROBLEM]
    per_problem = {problem["id"]: len(problem["right"]) for problem in in_bin}
    spread = {}
    for number in sorted(per_problem.values()):
        spread[str(number)] = spread.get(str(number), 0) + 1
    undecided = sum(1 for problem in in_bin if problem["undecided_options"])
    return {"per_problem": per_problem, "problems_with_this_many": spread, "problems_with_undecided_options": undecided}


def main_bins_by_area(files):
    areas = {}
    for file in files:
        if file["bin"] in MAIN:
            areas.setdefault(file["area"], {name: 0 for name in MAIN})[file["bin"]] += 1
    return {area: areas[area] for area in sorted(areas)}


def set_aside(files, settled):
    """The axiom sets where the two counts did not derive the same facts (from settled.json), the files set aside
    for that reason (from the final files), and the other files on those sets, which did not need the facts
    (proved unaided, or an unaided call that did not decide)."""
    on_them = sum(len(axiom_set["files"]) for axiom_set in settled["unsettled"])
    aside = sum(1 for f in files if f["why"] == UNSETTLED)
    return {"axiom_sets": len(settled["unsettled"]), "files": aside, "other_files_on_them": on_them - aside}


def report(data):
    data = Path(data)
    files, problems = read_jsonl(data / "files.jsonl"), read_jsonl(data / "problems.jsonl")
    if [f["problem_id"] for f in files if f["problem_id"]] != [p["id"] for p in problems]:
        raise ReportError("problems.jsonl does not hold exactly the files with a problem id, in order")
    settled = json.loads((data / "settled.json").read_text())
    counts = bin_counts(files)
    summary = {"files": len(files), "bins": counts, "main_shares": main_shares(counts),
               "clauses_needed_proved_unaided": clauses_needed(files, problems),
               "right_facts": right_facts(files, problems), "main_bins_by_area": main_bins_by_area(files),
               "set_aside_unsettled": set_aside(files, settled)}
    (data / "bins.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def tables(summary):
    """The printed tables, as text."""
    lines = [f"Files read: {summary['files']}", "", f"{'Bin':32} {'Files':>6}"]
    lines += [f"{name:32} {count:6d}" for name, count in summary["bins"].items()]
    aside = summary["set_aside_unsettled"]
    lines += [f"Axiom sets where the two counts did not derive the same facts: {aside['axiom_sets']}; "
              f"files set aside for that reason: {aside['files']}"
              + (f" (the other {aside['other_files_on_them']} files on those sets did not need the facts)"
                 if aside["other_files_on_them"] else "")]
    lines += ["", f"{'Main bin':32} {'Share':>6}"]
    lines += [f"{name:32} " + (f"{share:6.3f}" if share is not None else "   n/a")
              for name, share in summary["main_shares"].items()]
    needed = summary["clauses_needed_proved_unaided"]
    lines += ["", f"Clauses needed when proved unaided (limit {LIMIT}): {needed['count']} files, "
              f"median {needed['median']}, most {needed['max']}"]
    lines += [f"  {band:>9}: {count}" for band, count in needed["bands"].items()]
    lines += ["", "Right facts per problem (of 30): " +
              (", ".join(f"{n}: {c} problems" for n, c in summary["right_facts"]["problems_with_this_many"].items())
               or "no problems")]
    lines += [f"Problems with an option whose call did not decide (their count is a lower bound): "
              f"{summary['right_facts']['problems_with_undecided_options']}"]
    lines += ["", f"{'Area':6} " + " ".join(f"{name:>22}" for name in MAIN)]
    lines += [f"{area:6} " + " ".join(f"{row[name]:22d}" for name in MAIN)
              for area, row in summary["main_bins_by_area"].items()]
    return "\n".join(lines)
