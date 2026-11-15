"""Terms and equations.

Term  = variable (str, starts with an uppercase letter) | tuple (fname, arg1, ..., argn)  (constants are 1-tuples).
Equation = (lhs, rhs); all variables implicitly universally quantified.
This is the unit-equational fragment (UEQ); see SPEC.md for why.
"""
from __future__ import annotations
import re
from itertools import permutations

# ------------------------------------------------------------------ basics
def is_var(t):
    return isinstance(t, str)


def term_vars(t, acc=None):
    """variables in order of first occurrence (left-to-right, depth-first)"""
    if acc is None:
        acc = []
    if is_var(t):
        if t not in acc:
            acc.append(t)
    else:
        for a in t[1:]:
            term_vars(a, acc)
    return acc


def eq_vars(eq):
    acc = []
    term_vars(eq[0], acc)
    term_vars(eq[1], acc)
    return acc


def term_size(t):
    """number of symbol occurrences (vars and functions)"""
    if is_var(t):
        return 1
    return 1 + sum(term_size(a) for a in t[1:])


def term_depth(t):
    if is_var(t):
        return 0
    return 1 + max((term_depth(a) for a in t[1:]), default=0)


def term_syms(t, acc=None):
    """function symbols -> arity, as dict"""
    if acc is None:
        acc = {}
    if not is_var(t):
        acc[t[0]] = len(t) - 1
        for a in t[1:]:
            term_syms(a, acc)
    return acc


def eq_syms(eq):
    acc = {}
    term_syms(eq[0], acc)
    term_syms(eq[1], acc)
    return acc


def eq_size(eq):
    return term_size(eq[0]) + term_size(eq[1])


def subst(t, s):
    if is_var(t):
        return s.get(t, t)
    return (t[0],) + tuple(subst(a, s) for a in t[1:])


def rename_syms(t, m):
    if is_var(t):
        return t
    return (m.get(t[0], t[0]),) + tuple(rename_syms(a, m) for a in t[1:])


def eq_rename_syms(eq, m):
    return (rename_syms(eq[0], m), rename_syms(eq[1], m))


def match(pat, t, s=None):
    """one-way matching: substitution s with s(pat) == t, or None"""
    if s is None:
        s = {}
    if is_var(pat):
        if pat in s:
            return s if s[pat] == t else None
        s[pat] = t
        return s
    if is_var(t) or pat[0] != t[0] or len(pat) != len(t):
        return None
    for p, a in zip(pat[1:], t[1:]):
        if match(p, a, s) is None:
            return None
    return s


def positions(t, pos=()):
    yield pos
    if not is_var(t):
        for i, a in enumerate(t[1:], 1):
            yield from positions(a, pos + (i,))


def subterm(t, pos):
    for i in pos:
        t = t[i]
    return t


def replace_at(t, pos, new):
    if not pos:
        return new
    i = pos[0]
    return t[:i] + (replace_at(t[i], pos[1:], new),) + t[i + 1:]


# ------------------------------------------------------------------ printing / parsing (TPTP functional syntax)
def term_str(t):
    if is_var(t):
        return t
    if len(t) == 1:
        return t[0]
    return t[0] + "(" + ",".join(term_str(a) for a in t[1:]) + ")"


def eq_str(eq):
    return term_str(eq[0]) + "=" + term_str(eq[1])


_tok = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*|\(|\)|,|!=|=)")


def parse_term(s, pos=0):
    m = _tok.match(s, pos)
    if not m:
        raise ValueError("parse error at %d in %r" % (pos, s))
    name = m.group(1)
    if not (name[0].isalpha() or name[0] == "_"):
        raise ValueError("expected symbol at %d in %r" % (pos, s))
    pos = m.end()
    m2 = _tok.match(s, pos)
    if m2 and m2.group(1) == "(":
        pos = m2.end()
        args = []
        while True:
            a, pos = parse_term(s, pos)
            args.append(a)
            m3 = _tok.match(s, pos)
            pos = m3.end()
            if m3.group(1) == ")":
                break
            if m3.group(1) != ",":
                raise ValueError("expected , or ) at %d in %r" % (pos, s))
        return (name,) + tuple(args), pos
    if name[0].isupper():
        return name, pos
    return (name,), pos


def parse_eq(s):
    l, pos = parse_term(s, 0)
    m = _tok.match(s, pos)
    if not m or m.group(1) != "=":
        raise ValueError("expected = in %r" % s)
    r, pos = parse_term(s, m.end())
    if s[pos:].strip():
        raise ValueError("trailing junk in %r" % s)
    return (l, r)


# ------------------------------------------------------------------ canonical forms
def _rename_vars_first_occurrence(eq, prefix="X"):
    vs = eq_vars(eq)
    m = {v: "%s%d" % (prefix, i) for i, v in enumerate(vs)}
    return (subst(eq[0], m), subst(eq[1], m))


def canon_eq(eq):
    """Exact canonical form of an equation up to variable renaming and swapping sides:
    rename variables by first occurrence in (l,r) and in (r,l); take the lexicographically smaller string pair."""
    a = _rename_vars_first_occurrence(eq)
    b = _rename_vars_first_occurrence((eq[1], eq[0]))
    return a if (term_str(a[0]), term_str(a[1])) <= (term_str(b[0]), term_str(b[1])) else b


def canon_eq_str(eq):
    c = canon_eq(eq)
    return term_str(c[0]) + "=" + term_str(c[1])


def is_trivial(eq):
    return eq[0] == eq[1]


def is_instance_of(eq, ax):
    """True iff eq is an instance of ax (either orientation): exists s with s(ax.l)=eq.l, s(ax.r)=eq.r (or swapped)."""
    for (a, b) in ((ax[0], ax[1]), (ax[1], ax[0])):
        s = match(a, eq[0], {})
        if s is not None and match(b, eq[1], s) is not None:
            return True
    return False


# ------------------------------------------------------------------ symbol-abstracted shape
def shape_term(t, vmap, smap):
    """symbols -> arity-indexed placeholders (f1_2 = 2nd distinct binary symbol by first occurrence), vars canonicalised."""
    if is_var(t):
        if t not in vmap:
            vmap[t] = "x%d" % len(vmap)
        return vmap[t]
    ar = len(t) - 1
    key = t[0]
    if key not in smap:
        smap[key] = "f%d_%d" % (ar, sum(1 for k, v in smap.items() if v.startswith("f%d_" % ar)))
    return smap[key] if ar == 0 else smap[key] + "(" + ",".join(shape_term(a, vmap, smap) for a in t[1:]) + ")"


def shape_eq(eq):
    """Shape of an equation: min over the two side orders of the abstracted string (symbols by first occurrence per arity)."""
    outs = []
    for l, r in ((eq[0], eq[1]), (eq[1], eq[0])):
        vm, sm = {}, {}
        outs.append(shape_term(l, vm, sm) + "=" + shape_term(r, vm, sm))
    return min(outs)
