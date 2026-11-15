"""Isomorphism / canonical form of problems.

Two problems are isomorphic iff a bijection of function symbols (arity preserving), a renaming of variables in each
equation, swapping the sides of equations, and a reordering of axioms / candidates map one onto the other (the
conjecture onto the conjecture).  Exact canonical form: symbols are first partitioned by an isomorphism-invariant colour
(arity, occurrence counts in axioms / conjecture / candidates, refined once by the multiset of co-occurring colours); all
bijections consistent with the colour classes are enumerated (<= MAX_PERM) and the lexicographically smallest
serialisation wins.  If the enumeration would exceed MAX_PERM the function falls back to a strong invariant hash and
reports exact=False.
"""
from __future__ import annotations
import hashlib
from itertools import permutations, product
from collections import Counter
from math import factorial
from .terms import *

MAX_PERM = 5040


def _occ(t, c):
    if not is_var(t):
        c[t[0]] += 1
        for a in t[1:]:
            _occ(a, c)


def _colours(axioms, conj, cands):
    syms = {}
    for e in list(axioms) + [conj] + list(cands):
        syms.update(eq_syms(e))
    parts = {"A": axioms, "C": [conj], "L": cands}
    occ = {}
    for tag, eqs in parts.items():
        c = Counter()
        for e in eqs:
            _occ(e[0], c)
            _occ(e[1], c)
        occ[tag] = c
    col = {s: (syms[s], occ["A"][s], occ["C"][s], occ["L"][s]) for s in syms}
    # one refinement round: multiset of (colour of co-occurring symbols) over all equations
    co = {s: [] for s in syms}
    for e in list(axioms) + [conj] + list(cands):
        ss = set(eq_syms(e))
        for s in ss:
            co[s].append(tuple(sorted(col[x] for x in ss if x != s)))
    col2 = {s: (col[s], tuple(sorted(co[s]))) for s in syms}
    return syms, col2


def _serialise(mapping, axioms, conj, cands):
    def f(e):
        return canon_eq_str(eq_rename_syms(e, mapping))
    return "A:" + ";".join(sorted(f(a) for a in axioms)) + "|C:" + f(conj) + "|L:" + ";".join(sorted(f(c) for c in cands))


def canonical_form(axioms, conj, cands):
    """-> (canonical string, exact: bool)"""
    syms, col = _colours(axioms, conj, cands)
    classes = {}
    for s, c in col.items():
        classes.setdefault(c, []).append(s)
    order = sorted(classes, key=repr)
    nperm = 1
    for c in order:
        nperm *= factorial(len(classes[c]))
    names = {}
    base = 0
    for c in order:
        names[c] = ["s%03d" % (base + i) for i in range(len(classes[c]))]
        base += len(classes[c])
    if nperm > MAX_PERM:
        m = {}
        for c in order:
            for s, nm in zip(sorted(classes[c]), names[c]):
                m[s] = nm
        h = hashlib.sha256(_serialise(m, axioms, conj, cands).encode()).hexdigest()
        return "INV:" + h, False
    best = None
    choices = [list(permutations(classes[c])) for c in order]
    for combo in product(*choices):
        m = {}
        for c, perm in zip(order, combo):
            for s, nm in zip(perm, names[c]):
                m[s] = nm
        ser = _serialise(m, axioms, conj, cands)
        if best is None or ser < best:
            best = ser
    return best, True


def canon_hash(axioms, conj, cands):
    cf, exact = canonical_form(axioms, conj, cands)
    return hashlib.sha256(cf.encode()).hexdigest()[:20], exact


def theory_conj_hash(axioms, conj):
    """cluster key: isomorphism class of (theory, conjecture) ignoring candidates"""
    cf, exact = canonical_form(axioms, conj, [])
    return hashlib.sha256(cf.encode()).hexdigest()[:20], exact
