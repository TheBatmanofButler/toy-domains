"""Oracle (generation only): E in auto mode, 60 s, with a proof object; extracts the pure-theory unit steps."""
from __future__ import annotations
import os, re, subprocess, time
from .terms import parse_eq, term_str, canon_eq, eq_vars
from .engine import eq_clause, skolemize_conjecture, EPROVER

ORACLE_CPU = 60


def oracle_args(cpu=ORACLE_CPU):
    return [EPROVER, "--auto", "--cpu-limit=%d" % cpu, "--proof-object", "--silent", "--memory-limit=4000"]


def _balanced_end(s, i):
    """index just past the parenthesis group starting at s[i] == '('"""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def _split_top(s, sep):
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and s.startswith(sep, i):
            return s[:i], s[i + len(sep):]
    return None


def parse_proof(out):
    """-> list of dict(name, role, body, eq or None, deps[list of names], rule) for the cnf steps of the proof"""
    steps = []
    in_proof = False
    for line in out.splitlines():
        if line.startswith("# SZS output start"):
            in_proof = True
            continue
        if line.startswith("# SZS output end"):
            in_proof = False
            continue
        if not in_proof or not line.startswith("cnf("):
            continue
        try:
            i1 = line.index(",")
            name = line[4:i1]
            i2 = line.index(",", i1 + 1)
            role = line[i1 + 1:i2].strip()
            j = line.index("(", i2)
            k = _balanced_end(line, j)
            body = line[j + 1:k - 1]
            just = line[k:]
        except ValueError:
            continue
        eq = None
        if "|" not in body and "$false" not in body and "!=" not in body:
            try:
                eq = parse_eq(body)
            except ValueError:
                eq = None
        deps = re.findall(r"\bc_\d+_\d+\b", just)
        rule = re.search(r"inference\((\w+)", just)
        steps.append(dict(name=name, role=role, body=body, eq=eq, deps=deps, rule=rule.group(1) if rule else "input"))
    return steps


def prove(axioms, conjecture, cpu=ORACLE_CPU, extra=()):
    """-> dict(proved, cpu_s, steps, n_steps).  extra: further equations given as axioms."""
    import time
    lines = [eq_clause("ax%d" % i, a) for i, a in enumerate(list(axioms) + list(extra))]
    lines.append(skolemize_conjecture(conjecture))
    fn = "/dev/shm/fol_or_%d.p" % os.getpid()
    with open(fn, "w") as f:
        f.write("\n".join(lines) + "\n")
    t = time.time()
    try:
        r = subprocess.run(oracle_args(cpu) + [fn], capture_output=True, text=True, timeout=cpu + 20)
    except subprocess.TimeoutExpired:
        return dict(proved=False, cpu_s=cpu + 20, steps=[], n_steps=0, timeout=True)
    finally:
        os.unlink(fn)
    out = r.stdout
    proved = "# Proof found!" in out or "SZS status Unsatisfiable" in out
    steps = parse_proof(out) if proved else []
    return dict(proved=proved, cpu_s=time.time() - t, steps=steps, n_steps=len(steps))


def proof_lemmas(steps):
    """pure-theory unit equations derived in a proof (role 'plain', no skolem constants, not an input axiom)"""
    out = []
    for s in steps:
        if s["role"] == "plain" and s["eq"] is not None and "skc" not in s["body"] and s["rule"] not in ("assume_negation", "fof_simplification"):
            if s["eq"][0] != s["eq"][1]:
                out.append(s["eq"])
    return out


def used_axiom_indices(steps):
    """indices (into the axiom list passed to prove) of the input axioms that occur in the proof object"""
    out = set()
    for s in steps:
        if s["rule"] == "input" and s["role"] in ("axiom", "hypothesis") and s["name"].startswith("ax"):
            try:
                out.add(int(s["name"][2:]))
            except ValueError:
                pass
    return sorted(out)
