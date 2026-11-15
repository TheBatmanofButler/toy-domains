"""Theorem harvesting: unit equations that E derives (processed + unprocessed positive units) when saturating a theory
with several explicit strategies.  Every harvested equation is a consequence of the theory (E is sound); candidates
that enter a problem are additionally re-proved by the oracle (build.verify)."""
from __future__ import annotations
import os, subprocess, re
from .terms import *
from .engine import eq_clause, STRATEGIES, EPROVER

MAX_LINES = 1500
HARVEST_RUNS = [
    ("S3", 150, "KBO6"), ("S4", 150, "KBO6"), ("S1", 200, "KBO6"), ("S3", 150, "LPO4"), ("S1", 120, "LPO4"), ("S2", 200, "KBO6"),
]


def _eq_from_cnf_line(line):
    if not line.startswith("cnf("):
        return None
    try:
        i1 = line.index(",")
        i2 = line.index(",", i1 + 1)
        j = line.index("(", i2)
        depth = 0
        for k in range(j, len(line)):
            if line[k] == "(":
                depth += 1
            elif line[k] == ")":
                depth -= 1
                if depth == 0:
                    break
        body = line[j + 1:k]
        if "|" in body or "!=" in body or "$" in body:
            return None
        return parse_eq(body)
    except (ValueError, IndexError):
        return None


def harvest(axioms, runs=HARVEST_RUNS, cpu=20, tag="h"):
    """-> list of equations (cleaned of trivial ones, deduplicated canonically; axioms and instances removed)"""
    txt = "\n".join(eq_clause("ax%d" % i, a) for i, a in enumerate(axioms)) + "\n"
    fn = "/dev/shm/fol_h_%d_%s.p" % (os.getpid(), tag)
    open(fn, "w").write(txt)
    seen, out = set(), []
    ax_keys = {canon_eq_str(a) for a in axioms}
    try:
        for strat, lim, order in runs:
            args = [EPROVER, "--silent", "-t" + order, "-WNoSelection", "--processed-clauses-limit=%d" % lim,
                    "--print-saturated=eE", "--cpu-limit=%d" % cpu, "--memory-limit=2000"] + STRATEGIES[strat][2:]
            r = subprocess.run(args + [fn], capture_output=True, text=True)
            nline = 0
            for line in r.stdout.splitlines():
                if len(line) > 220 or not line.startswith("cnf("):
                    continue
                nline += 1
                if nline > MAX_LINES:
                    break
                eq = _eq_from_cnf_line(line)
                if eq is None or eq[0] == eq[1]:
                    continue
                k = canon_eq_str(eq)
                if k in seen or k in ax_keys:
                    continue
                if any(is_instance_of(eq, ax) for ax in axioms):
                    continue
                seen.add(k)
                out.append(eq)
    finally:
        os.unlink(fn)
    return out
