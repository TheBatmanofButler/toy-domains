"""Makes the saved test material in tests/fixtures/ from the earlier single-fact pilot's files and the pinned
prover. Run once, with python3 -I, from any folder:

    python3 -I tests/reference/make_fixtures.py --pilot PILOT_FOLDER --prover PROVER --out tests/fixtures

PILOT_FOLDER is the single-fact pilot's folder (with work/theories.json and raw/run/). The earlier code used
here is the copy in this folder (fol/, label_h.py); nothing is imported from the pilot's folder. Choices are made
with random.Random(SEED). The prover is run 120 times for the derived facts and 6 times for the endings.
"""
import argparse
import gzip
import json
import os
import random
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from tptp_count.prover import ENVIRONMENT  # noqa: E402

SEED = 20261112


def pilot_records(pilot):
    with gzip.open(pilot / "raw/run/goals.jsonl.gz", "rt") as f:
        return [json.loads(line) for line in f]


def pilot_outputs(pilot, wanted):
    """{(theory, gi): {call key: output}} for the wanted (theory, gi) pairs."""
    found = {}
    with gzip.open(pilot / "raw/run/raw_calls.jsonl.gz", "rt") as f:
        for line in f:
            record = json.loads(line)
            if (record["theory"], record["gi"]) in wanted:
                found[(record["theory"], record["gi"])] = record["raw"]
    return found


def make_pilot_calls(pilot, theories, rng):
    """200 calls at the limit of 160: 25 problems whose 30 options were all tried (the unaided call and 6
    options each) and 25 whose unaided call proved the goal (that call), with the input as the pilot built it."""
    import label_h
    from fol.engine import skolemize_conjecture
    from fol.terms import parse_eq
    records = pilot_records(pilot)
    tried = sorted((r for r in records if "s160" in r), key=lambda r: (r["theory"], r["gi"]))
    closed = sorted((r for r in records if r["status"] == "base_closes_160"), key=lambda r: (r["theory"], r["gi"]))
    chosen = [(r, [None] + sorted(rng.sample(range(30), 6))) for r in rng.sample(tried, 25)]
    chosen += [(r, [None]) for r in rng.sample(closed, 25)]
    outputs = pilot_outputs(pilot, {(r["theory"], r["gi"]) for r, _ in chosen})
    calls = []
    for record, numbers in chosen:
        theory = theories[record["theory"]]
        goal = parse_eq(theory["goals"][record["gi"]])
        options = label_h.draw(theory, record["gi"])
        assert options == record.get("cands", options), "the pilot's draw does not rebuild"
        caller = label_h.Caller([parse_eq(a) for a in theory["axioms"]], [parse_eq(o) for o in options], goal)
        denied = skolemize_conjecture(goal)
        for number in numbers:
            ids = () if number is None else (number,)
            # exactly the text label_h.Caller.call writes to the prover's input file
            text = "\n".join(caller.ax + [caller.cl[i] for i in sorted(ids)] + [caller.goal]) + "\n"
            result = record["base160"] if number is None else record["s160"][number]
            key = "160|" + (",".join(map(str, ids)) or "base")
            calls.append({"theory": record["theory"], "gi": record["gi"], "area": theory["domain"], "call": key,
                          "axioms": theory["axioms"], "option": None if number is None else options[number],
                          "goal_denied": denied[len("cnf(goal,negated_conjecture,("):-len(")).")],
                          "pilot_input": text, "pilot_result": result, "pilot_output": outputs[(record["theory"], record["gi"])][key]})
    return calls


def make_borderline_calls(pilot, theories, rng, term_cap=1_000_000):
    """50 borderline calls at the limit of 160, for the test that the caller's environment does not reach the
    prover: 25 drawn from the calls that proved in 140 or more processed clauses, and 25 from those that stopped
    at the limit of 160 (with fewer term insertions than the term cap, which the pilot also read as the limit).
    Such calls are the ones a change in the prover's search moves across an ending."""
    import label_h
    from fol.engine import skolemize_conjecture
    from fol.terms import parse_eq
    proved, limit = [], []
    for record in sorted(pilot_records(pilot), key=lambda r: (r["theory"], r["gi"])):
        results = ([(None, record["base160"])] if "base160" in record else []) + list(enumerate(record.get("s160") or []))
        for number, result in results:
            if result["status"] == "proof" and result["processed"] >= 140:
                proved.append((record, number))
            elif result["status"] == "limit" and result["processed"] == 160 and result["tb"] < term_cap:
                limit.append((record, number))
    calls = []
    for record, number in rng.sample(proved, 25) + rng.sample(limit, 25):
        theory = theories[record["theory"]]
        goal = parse_eq(theory["goals"][record["gi"]])
        options = label_h.draw(theory, record["gi"])
        assert options == record.get("cands", options), "the pilot's draw does not rebuild"
        denied = skolemize_conjecture(goal)
        calls.append({"theory": record["theory"], "gi": record["gi"], "area": theory["domain"],
                      "call": "160|" + ("base" if number is None else str(number)), "axioms": theory["axioms"],
                      "option": None if number is None else options[number],
                      "goal_denied": denied[len("cnf(goal,negated_conjecture,("):-len(")).")],
                      "pilot_result": record["base160"] if number is None else record["s160"][number]})
    return calls


def make_pilot_equations(pilot, theories, rng):
    """1,000 equations from the pilot's saved problems, each with the earlier code's key (canon_eq_str), its
    key as a one-equation axiom set (canon.canonical_form), size, variables, and whether it is an instance of
    a second equation from the same axiom set."""
    from fol.canon import canonical_form
    from fol.terms import canon_eq_str, eq_size, eq_vars, is_instance_of, parse_eq
    pool = []
    for key in sorted(theories):
        theory = theories[key]
        texts = theory["axioms"] + theory["goals"] + [text for _, text in theory["U"]]
        pool += [(key, text) for text in texts]
    for record in pilot_records(pilot):
        pool += [(record["theory"], text) for text in record.get("cands", [])]
    by_theory = {}
    for key, text in pool:
        by_theory.setdefault(key, []).append(text)
    rows = []
    for key, text in rng.sample(pool, 1000):
        other = rng.choice(by_theory[key] + theories[key]["axioms"])
        equation = parse_eq(text)
        form, exact = canonical_form([equation], ("X", "X"), [])
        rows.append({"equation": text, "pilot_key": canon_eq_str(equation), "pilot_set_key": form,
                     "pilot_set_key_exact": exact, "size": eq_size(equation), "variables": eq_vars(equation),
                     "other": other, "instance_of_other": is_instance_of(equation, parse_eq(other))})
    return rows


def _streaming_run(arguments, capture_output=True, text=True):
    """Stands in for subprocess.run inside the copied harvest code: the same lines reach it, but only those it
    reads (clause lines of at most 220 characters, the first 1,501), since some runs print gigabytes. The prover
    is started in the code's fixed environment, as every prover run is."""
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                               env=ENVIRONMENT)
    kept = []
    for line in process.stdout:
        line = line.rstrip("\n")
        if len(line) <= 220 and line.startswith("cnf(") and len(kept) <= 1500:
            kept.append(line)
    process.wait()
    return types.SimpleNamespace(stdout="\n".join(kept), returncode=process.returncode)


def make_pilot_derived(theories, rng, prover):
    """For 20 axiom sets: the pilot's harvest, filtered as its bank was before any topping-up. The prover is
    started in the code's fixed environment (tptp_count.prover.ENVIRONMENT): E 2.6's search depends on the C
    library's memory settings, and with one of them set the result no longer holds every fact of the pilot's
    saved banks."""
    os.environ["EPROVER"] = prover
    import fol.harvest
    from fol.terms import canon_eq_str, eq_size, eq_str, eq_vars, is_instance_of, parse_eq
    fol.harvest.subprocess = types.SimpleNamespace(run=_streaming_run)
    fol.harvest.EPROVER = prover
    rows = []
    for key in rng.sample(sorted(theories), 20):
        axioms = [parse_eq(a) for a in theories[key]["axioms"]]
        axiom_keys = {canon_eq_str(a) for a in axioms}
        facts, seen = [], set()
        for fact in fol.harvest.harvest(axioms):   # build.make_bank's add(), without gen.nice (keys are unchanged)
            k = canon_eq_str(fact)
            if (k in seen or k in axiom_keys or fact[0] == fact[1] or not 5 <= eq_size(fact) <= 16
                    or len(eq_vars(fact)) > 4 or any(is_instance_of(fact, a) for a in axioms)):
                continue
            seen.add(k)
            facts.append(eq_str(fact))
        saved = {k for k, _ in theories[key]["U"]}
        rows.append({"theory": key, "area": theories[key]["domain"], "axioms": theories[key]["axioms"],
                     "pilot_facts": facts, "in_saved_bank": sum(canon_eq_str(parse_eq(f)) in saved for f in facts),
                     "saved_bank_size": len(saved)})
        print(f"derived: {key} {len(facts)} facts", flush=True)
    return rows


def make_endings(pilot_calls, theories, prover):
    """One real output of every ending: proved and clause limit from the pilot's kept outputs; the others made
    once with the pinned prover, with the caps changed where the real ones are too far to reach."""
    from tptp_count.equations import read_equation
    from tptp_count.prover import command, input_text
    endings = []
    for wanted, status in (("proved", "proof"), ("clause limit", "limit")):
        call = next(c for c in pilot_calls if c["pilot_result"]["status"] == status)
        endings.append({"ending": wanted, "made_with": f"pilot output {call['theory']} {call['gi']} {call['call']}",
                        "arguments": None, "input": call["pilot_input"], "output": call["pilot_output"]})
    heavy = next(t for t in theories.values() if t["domain"] == "LDA")   # its runs build terms fast
    heavy_axioms = [read_equation(a) for a in heavy["axioms"]]
    goal = read_equation("f(f(a,b),c)=f(a,f(b,c))")
    uncapped = [part for part in command() if not part.startswith(("--tb-insert-limit", "--cpu-limit",
                                                                   "--processed-clauses-limit"))]
    made = [
        ("nothing left", command(), input_text([read_equation("f(X)=X")], None, read_equation("a=b"))),
        ("term cap", command(), input_text(heavy_axioms, None, goal)),
        ("time cap", uncapped + ["--cpu-limit=1"], input_text(heavy_axioms, None, goal)),
        ("memory cap", [p for p in command() if not p.startswith("--memory-limit")] + ["--memory-limit=1"],
         input_text(heavy_axioms, None, goal)),
        ("unreadable", command(), "cnf(ax0,axiom,(f(X)=X).\n"),
    ]
    for wanted, arguments, text in made:
        done = subprocess.run([prover, *arguments, "-"], input=text, capture_output=True, text=True, env=ENVIRONMENT)
        endings.append({"ending": wanted, "made_with": "pinned prover", "arguments": arguments, "input": text,
                        "output": done.stdout + done.stderr})
    return endings


def write_jsonl_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", required=True, type=Path)
    parser.add_argument("--prover", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--only", choices=["calls", "equations", "derived", "endings", "borderline"])
    args = parser.parse_args()
    theories = {t["key"]: t for t in json.loads((args.pilot / "work/theories.json").read_text())}
    calls = make_pilot_calls(args.pilot, theories, random.Random(SEED))
    if args.only in (None, "calls"):
        write_jsonl_gz(args.out / "pilot_calls.jsonl.gz", calls)
    if args.only in (None, "equations"):
        write_jsonl_gz(args.out / "pilot_equations.jsonl.gz", make_pilot_equations(args.pilot, theories, random.Random(SEED)))
    if args.only in (None, "derived"):
        rows = make_pilot_derived(theories, random.Random(SEED), args.prover)
        (args.out / "pilot_derived.json").write_text(json.dumps(rows, indent=1, sort_keys=True))
    if args.only in (None, "endings"):
        (args.out / "endings.json").write_text(json.dumps(make_endings(calls, theories, args.prover), indent=1))
    if args.only in (None, "borderline"):
        write_jsonl_gz(args.out / "borderline_calls.jsonl.gz", make_borderline_calls(args.pilot, theories,
                                                                                      random.Random(SEED)))


if __name__ == "__main__":
    main()
