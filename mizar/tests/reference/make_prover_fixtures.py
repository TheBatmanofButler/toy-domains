"""Makes the saved prover outputs under tests/fixtures/. Run once by hand, with the real library and the pinned
prover; the tests only read what it wrote.

    python3 -I tests/reference/make_prover_fixtures.py --library FOLDER --prover PROGRAM

Every call is built as the code builds it (problems.Builder with seed 20261112, calls.facts_of,
prover.input_text) and run in the fixed environment, as the code runs it, but the output is kept as the prover printed it: with the
lines on time and memory used and the input file's name, so that the tests can check they are taken out.
1. `endings.json.gz`: one real output of every ending that can be produced on these problems, with the limit,
   the arguments, the input and the input file's name. The memory cap is made with a cap of 1 MB, since the
   real cap is not reached; every other one with the pinned command line. "unreadable" is the prover's answer to
   an input with a syntax error. One more clause-limit output is of a whole problem file (t47_knaster, not a
   problem of the experiment), where the processed clauses printed exceed the limit.
2. `proofs.json.gz`: three real proofs, with the facts each uses, read here by a plainer method than
   prover.used_facts: every line between the SZS output lines that starts "fof(" and has the role axiom.
3. `input_text_fixed_problem.txt`: the input for the fixed problem (tests/fixtures/fixed_problem.json) with its
   held-back fact as the option, saved after it was read by eye; and `input_parts_fixed_problem.json`, the facts,
   option and theorem it was made from, read from the library, so the test needs no library.
"""
import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "fixtures"
sys.path.insert(0, str(HERE.parent.parent))

from mizar_ladder import prover  # noqa: E402
from mizar_ladder.calls import facts_of  # noqa: E402
from mizar_ladder.library import Library  # noqa: E402
from mizar_ladder.problems import Builder  # noqa: E402

# (ending expected, theorem, with the held-back fact?, limit, how it was made)
CALLS = [
    ("proved", "t43_xtuple_0", True, 250, "pinned command"),
    ("nothing left", "t43_xtuple_0", False, 250, "pinned command"),
    ("clause limit", "t54_card_3", False, 250, "pinned command"),
    # The whole problem file of t47_knaster: 386 initial clauses, and more clauses processed than the limit.
    ("clause limit", "t47_knaster", None, 250, "pinned command"),
    ("term cap", "t54_card_3", False, 64000, "pinned command"),
    ("time cap", "t6_domain_1", True, 4000, "pinned command"),
    ("memory cap", "t70_zfmisc_1", True, 4000, "memory cap of 1 MB"),
]
PROOFS = [("t70_zfmisc_1", True, 4000), ("t43_xtuple_0", True, 250), ("t90_card_3", False, 64000)]


def run(program, arguments, text):
    with tempfile.NamedTemporaryFile("w", suffix=".p", delete=False) as f:
        f.write(text)
    done = subprocess.run([program, *arguments, f.name], capture_output=True, text=True, env=prover.ENVIRONMENT)
    Path(f.name).unlink()
    return done.stdout + done.stderr, f.name


def the_input(builder, library, theorem, with_held_back):
    if with_held_back is None:
        statement, names = library.problem_file(theorem)
        return prover.input_text([(n, library.statement(n)) for n in names], None, (theorem, statement)), None
    problem = builder.problem(builder.classify(theorem), "fixture")
    facts, statement = facts_of(library, problem)
    held = problem["options"][problem["held_back"] - 1]["name"]
    return prover.input_text(facts, (held, library.statement(held)) if with_held_back else None, statement), held


def plain_used(output):
    proof = output.split("# SZS output start CNFRefutation", 1)[1].split("# SZS output end CNFRefutation", 1)[0]
    names = [line[4:].split(",", 1)[0] for line in proof.splitlines()
             if line.startswith("fof(") and line.split(",", 2)[1].strip() == "axiom"]
    return list(dict.fromkeys(names))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--prover", required=True)
    args = parser.parse_args()
    library = Library(args.library)
    builder = Builder(library, 20261112)
    prover.check_version(args.prover)
    endings = []
    for ending, theorem, with_held_back, limit, made_with in CALLS:
        text, _ = the_input(builder, library, theorem, with_held_back)
        arguments = prover.command(limit)
        if made_with == "memory cap of 1 MB":
            arguments = [a if not a.startswith("--memory-limit=") else "--memory-limit=1" for a in arguments]
        output, path = run(args.prover, arguments, text)
        endings.append({"ending": ending, "theorem": theorem, "with_held_back": with_held_back, "limit": limit,
                        "made_with": made_with, "arguments": arguments, "input_name": path, "input": text,
                        "output": output})
    text = "fof(broken, axiom, p(.\nfof(t1_x, conjecture, q).\n"
    output, path = run(args.prover, prover.command(250), text)
    endings.append({"ending": "unreadable", "theorem": None, "with_held_back": False, "limit": 250,
                    "made_with": "an input with a syntax error", "arguments": prover.command(250),
                    "input_name": path, "input": text, "output": output})
    (FIXTURES / "endings.json.gz").write_bytes(gzip.compress(json.dumps(endings).encode(), mtime=0))
    proofs = []
    for theorem, with_held_back, limit in PROOFS:
        text, held = the_input(builder, library, theorem, with_held_back)
        output, path = run(args.prover, prover.command(limit), text)
        proofs.append({"theorem": theorem, "held_back": held, "with_held_back": with_held_back, "limit": limit,
                       "input_name": path, "output": output, "used": plain_used(output)})
    (FIXTURES / "proofs.json.gz").write_bytes(gzip.compress(json.dumps(proofs).encode(), mtime=0))
    fixed = json.loads((FIXTURES / "fixed_problem.json").read_text())
    facts, statement = facts_of(library, fixed)
    held = fixed["options"][fixed["held_back"] - 1]["name"]
    parts = {"facts": facts, "option": [held, library.statement(held)], "theorem": list(statement)}
    (FIXTURES / "input_parts_fixed_problem.json").write_text(json.dumps(parts, indent=1))
    (FIXTURES / "input_text_fixed_problem.txt").write_text(
        prover.input_text(facts, (held, library.statement(held)), statement))


if __name__ == "__main__":
    main()
