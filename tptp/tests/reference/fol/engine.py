"""The engine: E 2.6 with a fixed search strategy and a deterministic work limit.

closes(axioms, added_lemmas, conjecture) -> (closed, stats)

Determinism: the verdict depends only on the input text (axioms in the given order, then added lemmas in the
given order, then the conjecture) because the stopping rule is a processed-clauses limit, not wall-clock.  A CPU
limit exists only as a safety net; a call that hits it is counted (cpu_cap=True), is treated as 'not closed'.
"""
from __future__ import annotations
import os, re, subprocess, time, hashlib
from .terms import term_str, term_vars, subst, eq_vars

EPROVER = os.environ.get("EPROVER", "eprover")

# ---- the pinned engine command line (see SPEC.md proposal P1) -------------------------------------------------
DEFAULT_LIMIT = 80           # --processed-clauses-limit; set by calibration, SPEC P1
DEFAULT_CPU_CAP = 5          # seconds, safety net only
DEFAULT_TB_LIMIT = 1000000   # --tb-insert-limit: deterministic work cap against rewriting blow-ups


def engine_args(limit=DEFAULT_LIMIT, cpu_cap=DEFAULT_CPU_CAP, strategy="S1", tb_limit=None):
    tb = DEFAULT_TB_LIMIT if tb_limit is None else tb_limit
    base = [EPROVER, "--print-statistics", "--silent", "--cpu-limit=%d" % cpu_cap,
            "--processed-clauses-limit=%d" % limit, "--tb-insert-limit=%d" % tb, "--memory-limit=2000"]
    return base + STRATEGIES[strategy]


# fixed search strategies (no --auto / --auto-schedule).  explicit term ordering, literal selection, clause selection.
STRATEGIES = {
    # S1: KBO6, no literal selection (unit equational: nothing to select), 1:1 FIFO / smallest-weight given-clause selection
    "S1": ["-tKBO6", "-WNoSelection", "-H(1*FIFOWeight(ConstPrio),1*Clauseweight(ConstPrio,1,1,1))"],
    # S2: weight-only (greedy)
    "S2": ["-tKBO6", "-WNoSelection", "-H(1*Clauseweight(ConstPrio,1,1,1))"],
    # S3: FIFO only (breadth-first)
    "S3": ["-tKBO6", "-WNoSelection", "-H(1*FIFOWeight(ConstPrio))"],
    # S4: conjecture-relative symbol weight mix
    "S4": ["-tKBO6", "-WNoSelection",
           "-H(1*FIFOWeight(ConstPrio),4*ConjectureRelativeSymbolWeight(ConstPrio,0.1,100,100,100,100,1.5,1.5,1.5))"],
}

# ---- problem text -------------------------------------------------------------------------------------------
def eq_clause(name, eq, role="axiom"):
    return "cnf(%s,%s,(%s=%s))." % (name, role, term_str(eq[0]), term_str(eq[1]))


def skolemize_conjecture(eq):
    """universal conjecture  l = r  ->  negated conjecture  l[sk_i/X_i] != r[sk_i/X_i]"""
    vs = eq_vars(eq)
    m = {v: ("skc%d" % i,) for i, v in enumerate(vs)}
    return "cnf(goal,negated_conjecture,(%s!=%s))." % (term_str(subst(eq[0], m)), term_str(subst(eq[1], m)))


def problem_text(axioms, lemmas, conjecture, ax_names=None):
    """axioms, lemmas: lists of equations (kept in the order given); conjecture: an equation."""
    lines = [eq_clause("ax%d" % i, a) for i, a in enumerate(axioms)]
    lines += [eq_clause("lem%d" % i, l, "lemma") for i, l in enumerate(lemmas)]
    lines.append(skolemize_conjecture(conjecture))
    return "\n".join(lines) + "\n"


# ---- running ------------------------------------------------------------------------------------------------
_STAT_KEYS = {
    "processed": re.compile(r"^# Processed clauses\s*:\s*(\d+)", re.M),
    "generated": re.compile(r"^# Generated clauses\s*:\s*(\d+)", re.M),
    "unprocessed": re.compile(r"^# Current number of unprocessed clauses:\s*(\d+)", re.M),
    "cur_processed": re.compile(r"^# Current number of processed clauses\s*:\s*(\d+)", re.M),
    "tb_inserts": re.compile(r"^# Termbank termtop insertions\s*:\s*(\d+)", re.M),
    "paramod": re.compile(r"^# Paramodulations\s*:\s*(\d+)", re.M),
}
_PROOF = re.compile(r"^# Proof found!", re.M)
_SAT = re.compile(r"^# No proof found!", re.M)
_CPU = re.compile(r"Resource limit exceeded \(time\)|SZS status ResourceOut.*time|CPU time limit", re.M)


def parse_output(out, rc):
    """-> (closed, stats dict).  stats has processed, generated, unprocessed, cur_processed, tb_inserts, paramod,
    status in {'proof','limit','saturated','cpu_cap','error'}, cpu_cap bool."""
    st = {}
    for k, rx in _STAT_KEYS.items():
        m = rx.search(out)
        st[k] = int(m.group(1)) if m else None
    if _PROOF.search(out):
        st["status"] = "proof"
    elif _CPU.search(out):
        st["status"] = "cpu_cap"
    elif _SAT.search(out):
        st["status"] = "saturated"      # saturated without proof => the negated conjecture is consistent with the set (shouldn't happen for theorems)
    elif "Resource limit exceeded" in out or "ResourceOut" in out or st["processed"] is not None:
        st["status"] = "limit"
    else:
        st["status"] = "error"
    st["cpu_cap"] = st["status"] == "cpu_cap"
    return st["status"] == "proof", st


def run_text(text, args, tmpdir="/dev/shm", tag=None, timeout=None):
    fn = os.path.join(tmpdir, "fol_%d_%s.p" % (os.getpid(), tag or "x"))
    with open(fn, "w") as f:
        f.write(text)
    try:
        r = subprocess.run(args + [fn], capture_output=True, text=True, timeout=timeout)
    finally:
        try:
            os.unlink(fn)
        except OSError:
            pass
    return parse_output(r.stdout + r.stderr, r.returncode)


def closes(axioms, added_lemmas, conjecture, limit=DEFAULT_LIMIT, strategy="S1", cpu_cap=DEFAULT_CPU_CAP):
    """The engine call of the brief: -> (closed, stats)."""
    return run_text(problem_text(axioms, added_lemmas, conjecture), engine_args(limit, cpu_cap, strategy))


class Prepared:
    """One problem with its 30 candidates pre-rendered: call(idset) for sorted ids is cheap."""

    def __init__(self, axioms, cands, conjecture, limit=DEFAULT_LIMIT, strategy="S1", cpu_cap=DEFAULT_CPU_CAP, tmpdir="/dev/shm"):
        self.args = engine_args(limit, cpu_cap, strategy)
        self.ax = [eq_clause("ax%d" % i, a) for i, a in enumerate(axioms)]
        self.cl = [eq_clause("lem%d" % i, c, "lemma") for i, c in enumerate(cands)]
        self.goal = skolemize_conjecture(conjecture)
        self.tmpdir = tmpdir
        self.n_calls = 0
        self.n_cpu_cap = 0

    def text(self, ids):
        return "\n".join(self.ax + [self.cl[i] for i in sorted(ids)] + [self.goal]) + "\n"

    def call(self, ids):
        self.n_calls += 1
        closed, st = run_text(self.text(ids), self.args, self.tmpdir)
        if st["cpu_cap"]:
            self.n_cpu_cap += 1
        return closed, st


def engine_fingerprint(limit=DEFAULT_LIMIT, strategy="S1"):
    return hashlib.sha256(" ".join(engine_args(limit, DEFAULT_CPU_CAP, strategy)).encode()).hexdigest()[:16]
