"""Minimal TPTP reader for unit-equational (UEQ) CNF problems, and corpus statistics for R / R'."""
from __future__ import annotations
import os, re, hashlib
from .terms import *

_COMMENT = re.compile(r"%.*$", re.M)


def _balanced_end(s, i):
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def read_formulas(path, root, seen=None):
    """-> list of (kind, name, role, body) for cnf/fof formulas, includes resolved (axiom files read once per call chain)"""
    if seen is None:
        seen = set()
    txt = open(path, errors="ignore").read()
    txt = _COMMENT.sub("", txt)
    out = []
    pos = 0
    pat = re.compile(r"\b(cnf|fof|include)\s*\(")
    while True:
        m = pat.search(txt, pos)
        if not m:
            break
        j = m.end() - 1
        k = _balanced_end(txt, j)
        if k < 0:
            break
        inner = txt[j + 1:k - 1]
        pos = k
        if m.group(1) == "include":
            fn = inner.split(",")[0].strip().strip("'")
            p2 = os.path.join(root, fn)
            if os.path.exists(p2) and p2 not in seen:
                seen.add(p2)
                out.extend(read_formulas(p2, root, seen))
            continue
        parts = inner.split(",", 2)
        if len(parts) < 3:
            continue
        name, role, body = parts[0].strip(), parts[1].strip(), parts[2].strip()
        # strip trailing annotation (only if top-level comma)
        depth = 0
        for i, ch in enumerate(body):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                body = body[:i]
                break
        out.append((m.group(1), name, role, body.strip()))
    return out


def _strip_parens(b):
    b = b.strip()
    while b.startswith("(") and _balanced_end(b, 0) == len(b):
        b = b[1:-1].strip()
    return b


def _top_split(s, sep):
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and s.startswith(sep, i):
            return s[:i], s[i + len(sep):]
    return None


def parse_unit_eq_body(body):
    """body of a cnf: 'l = r' -> ('eq', (l,r)); 'l != r' -> ('neq', (l,r)); else None"""
    b = _strip_parens(body)
    if "|" in b and _top_split(b, "|") is not None:
        return None
    sp = _top_split(b, "!=")
    try:
        if sp is not None:
            return ("neq", (parse_term(sp[0].strip())[0], parse_term(sp[1].strip())[0]))
        if b.startswith("~"):
            sp = _top_split(_strip_parens(b[1:]), "=")
            if sp is not None:
                return ("neq", (parse_term(sp[0].strip())[0], parse_term(sp[1].strip())[0]))
            return None
        sp = _top_split(b, "=")
        if sp is not None:
            return ("eq", (parse_term(sp[0].strip())[0], parse_term(sp[1].strip())[0]))
    except (ValueError, IndexError):
        return None
    return None


def term_consts(t, acc=None):
    if acc is None:
        acc = []
    if not is_var(t):
        if len(t) == 1 and t[0] not in acc:
            acc.append(t[0])
        for a in t[1:]:
            term_consts(a, acc)
    return acc


def read_ueq_problem(path, root):
    """-> dict(ok, reason, axioms, conj, name).  Requires: every formula a cnf unit equation, exactly one negated
    conjecture that is a single disequality whose constants (skolem) occur nowhere else; the conjecture becomes the
    universal equation obtained by replacing those constants by variables."""
    fs = read_formulas(path, root)
    axioms, negs = [], []
    for kind, name, role, body in fs:
        if kind != "cnf":
            return dict(ok=False, reason="fof")
        p = parse_unit_eq_body(body)
        if p is None:
            return dict(ok=False, reason="nonunit")
        if role == "negated_conjecture":
            if p[0] != "neq":
                return dict(ok=False, reason="neg_conj_not_diseq")
            negs.append(p[1])
        else:
            if p[0] != "eq":
                return dict(ok=False, reason="axiom_not_eq")
            axioms.append(p[1])
    if len(negs) != 1:
        return dict(ok=False, reason="n_neg=%d" % len(negs))
    l, r = negs[0]
    cs = term_consts(l)
    term_consts(r, cs)
    ax_consts = set()
    for a in axioms:
        for c in term_consts(a[0]) + term_consts(a[1]):
            ax_consts.add(c)
    sk = [c for c in cs if c not in ax_consts]
    # a constant of the conjecture that also occurs in the axioms is a theory constant (e.g. identity), kept
    m = {}
    vn = ["X", "Y", "Z", "U", "V", "W", "A", "B", "C", "D", "E1", "F1", "G1", "H1"]
    for i, c in enumerate(sk):
        if i >= len(vn):
            return dict(ok=False, reason="too_many_vars")
        m[c] = vn[i]

    def cv(t):
        if is_var(t):
            return t
        if len(t) == 1 and t[0] in m:
            return m[t[0]]
        return (t[0],) + tuple(cv(a) for a in t[1:])
    conj = (cv(l), cv(r))
    # axioms must be dedup'd by canonical form but keep order
    seen, ax2 = set(), []
    for a in axioms:
        k = canon_eq_str(a)
        if k not in seen:
            seen.add(k)
            ax2.append(a)
    return dict(ok=True, reason="", axioms=ax2, conj=conj, name=os.path.basename(path)[:-2], n_skolem=len(sk))


def corpus_shapes(paths, root):
    """shape frequencies of all unit equations (axioms, hypotheses, conjectures) in the given problem files.
    Axiom files included by many problems count once per including problem."""
    from collections import Counter
    c = Counter()
    for p in paths:
        try:
            fs = read_formulas(p, root)
        except Exception:
            continue
        for kind, name, role, body in fs:
            if kind != "cnf":
                continue
            r = parse_unit_eq_body(body)
            if r is None:
                continue
            l, rr = r[1]
            if is_var(l) and is_var(rr):
                continue
            c[shape_eq((l, rr))] += 1
    return c
