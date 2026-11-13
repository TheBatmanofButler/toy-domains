"""A copy of the earlier run's fe/core.py, used by the tests only, as a second opinion on identities.py and proof.py.
Only this first line of its description was changed. Its own description follows.

Exact core: identities over f-atoms and monomial atoms, 12 substitutions, canonicalisation,
candidate sets with class dedup, exact Q-span engine, isomorphism key, tiny parser / printer.

Atoms (hashable tuples, global order = tuple order):
    f-atom      (0, a, b, c)   meaning f(a*x + b*y + c)   a,b,c Fraction
    monomial    (1, i, j)      meaning x^i y^j            (i+j <= 4), (1,0,0) is the constant 1
Identity: canonical tuple of (atom, Fraction) pairs, sorted by atom, first coefficient == 1, no zeros.
The relation is  sum coeff*atom = 0.
"""
from __future__ import annotations

import re
from fractions import Fraction as Fr
from functools import lru_cache
from heapq import heapify, heappop, heappush

ONE = Fr(1)
ZERO = Fr(0)

# ----------------------------------------------------------------------------- substitutions
# sigma index 1..12 -> (X, Y) where X, Y are linear forms (p, q, r) = p*x + q*y + r replacing x and y simultaneously.
_Z = (ZERO, ZERO, ZERO)
SIGMAS = {
    1: ((ZERO, ZERO, ZERO), (ZERO, ZERO, ZERO)),    # x=0, y=0
    2: ((ONE, ZERO, ZERO), (ZERO, ZERO, ZERO)),     # y=0
    3: ((ZERO, ZERO, ZERO), (ZERO, ONE, ZERO)),     # x=0
    4: ((ONE, ZERO, ZERO), (ONE, ZERO, ZERO)),      # y=x
    5: ((ONE, ZERO, ZERO), (-ONE, ZERO, ZERO)),     # y=-x
    6: ((ZERO, ONE, ZERO), (ONE, ZERO, ZERO)),      # swap x,y
    7: ((ONE, ZERO, ZERO), (ZERO, ZERO, ONE)),      # y=1
    8: ((ONE, ONE, ZERO), (ZERO, -ONE, ZERO)),      # x=x+y, y=-y (simultaneous)
    9: ((ONE, ZERO, ZERO), (ONE, ONE, ZERO)),       # y=x+y
    10: ((ZERO, ZERO, ONE), (ZERO, ONE, ZERO)),     # x=1
    11: ((-ONE, ZERO, ZERO), (ZERO, ONE, ZERO)),    # x=-x
    12: ((ONE, ZERO, ZERO), (ZERO, -ONE, ZERO)),    # y=-y
}
SIGMA_NAMES = {1: "x=0,y=0", 2: "y=0", 3: "x=0", 4: "y=x", 5: "y=-x", 6: "swap x,y", 7: "y=1",
               8: "x=x+y,y=-y", 9: "y=x+y", 10: "x=1", 11: "x=-x", 12: "y=-y"}
NSIG = 12     # active vocabulary size: 12 (original run, default) or 13 (deep run); see set_vocab
SIGMAS[13] = ((ONE, -ONE, ZERO), (ONE, ONE, ZERO))     # sigma13: x -> x-y, y -> x+y (simultaneous); deep run only
SIGMA_NAMES[13] = "x=x-y,y=x+y"


def set_vocab(n):
    """select the active vocabulary: 12 (original, default) or 13 (deep: adds sigma13). Affects core.candidates and every function
    that iterates range(1, NSIG+1) at call time. The original run never calls this."""
    global NSIG
    if n not in (12, 13):
        raise ValueError(n)
    NSIG = n
CONST_SIGMAS = (1, 2, 3, 7, 10)   # "sigma introduces a constant"


def _poly_mul(P, Q):
    out = {}
    for (i, j), c in P.items():
        for (k, l), d in Q.items():
            key = (i + k, j + l)
            out[key] = out.get(key, ZERO) + c * d
    return {k: v for k, v in out.items() if v}


def _form_poly(form):
    p, q, r = form
    d = {}
    if p: d[(1, 0)] = p
    if q: d[(0, 1)] = q
    if r: d[(0, 0)] = r
    return d


@lru_cache(maxsize=None)
def _mono_image(sigma, i, j):
    X, Y = SIGMAS[sigma]
    P = {(0, 0): ONE}
    for _ in range(i): P = _poly_mul(P, _form_poly(X))
    for _ in range(j): P = _poly_mul(P, _form_poly(Y))
    return tuple(P.items())


# ----------------------------------------------------------------------------- canonicalisation
def _rename_y_to_x(vec):
    """swap x,y in every atom of a dict vector"""
    out = {}
    for at, c in vec.items():
        if at[0] == 0:
            out[(0, at[2], at[1], at[3])] = c
        else:
            out[(1, at[2], at[1])] = c
    return out


def _uses(vec):
    ux = uy = False
    for at in vec:
        if at[0] == 0:
            if at[1]: ux = True
            if at[2]: uy = True
        else:
            if at[1]: ux = True
            if at[2]: uy = True
    return ux, uy


def canon(vec):
    """dict atom->coef -> canonical identity tuple, or None if trivial (all zero)."""
    vec = {a: c for a, c in vec.items() if c}
    if not vec:
        return None
    ux, uy = _uses(vec)
    if uy and not ux:
        vec = _rename_y_to_x(vec)
    items = sorted(vec.items())
    lead = items[0][1]
    if lead != 1:
        return tuple((a, c / lead) for a, c in items)
    return tuple(items)


def swap_identity(ident):
    return canon(_rename_y_to_x_force(dict(ident)))


def _rename_y_to_x_force(vec):
    return _rename_y_to_x(vec)


def apply_sigma(ident, sigma):
    """apply substitution to canonical identity; returns canonical identity or None (trivial)."""
    return _apply(ident, sigma)


@lru_cache(maxsize=2_000_000)
def _apply(ident, sigma):
    X, Y = SIGMAS[sigma]
    out = {}
    for at, c in ident:
        if at[0] == 0:
            _, a, b, k = at
            na = a * X[0] + b * Y[0]
            nb = a * X[1] + b * Y[1]
            nk = a * X[2] + b * Y[2] + k
            key = (0, na, nb, nk)
            out[key] = out.get(key, ZERO) + c
        else:
            _, i, j = at
            for (u, v), d in _mono_image(sigma, i, j):
                key = (1, u, v)
                out[key] = out.get(key, ZERO) + c * d
    return canon(out)


# ----------------------------------------------------------------------------- candidates
class Cand:
    __slots__ = ("i", "sigma", "result", "members")

    def __init__(self, i, sigma, result, members):
        self.i, self.sigma, self.result, self.members = i, sigma, result, members

    def __repr__(self):
        return f"Cand({self.i},s{self.sigma})"


def candidates(ids):
    """ids: sequence of canonical identities (numbered 1..n in order). Returns list of Cand (classes), rep = smallest (i,sigma)."""
    have = set(ids)
    by = {}
    order = []
    for ii, ident in enumerate(ids, 1):
        for s in range(1, NSIG + 1):
            r = _apply(ident, s)
            if r is None or r in have:
                continue
            if r in by:
                by[r].members.append((ii, s))
            else:
                c = Cand(ii, s, r, [(ii, s)])
                by[r] = c
                order.append(c)
    return order


# ----------------------------------------------------------------------------- exact engine (Q-span)
_ATOM_ID = {}


def _aid(at):
    v = _ATOM_ID.get(at)
    if v is None:
        v = _ATOM_ID[at] = len(_ATOM_ID)
    return v


@lru_cache(maxsize=1_000_000)
def _ivec(ident):
    return {_aid(a): c for a, c in ident}


class Span:
    """Immutable-ish echelon basis over Q. rows: pivot(atom id, the row's smallest id) -> row dict (pivot coef 1)."""
    __slots__ = ("rows",)

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else {}

    def reduce(self, vec):
        """eliminate every pivot atom from vec (returns new dict, no pivot atoms inside)."""
        rows = self.rows
        v = dict(vec)
        if not rows:
            return v
        heap = [a for a in v if a in rows]
        if not heap:
            return v
        heapify(heap)
        done = set()
        while heap:
            a = heappop(heap)
            if a in done:
                continue
            done.add(a)
            c = v.get(a)
            if not c:
                continue
            for b, d in rows[a].items():
                nv = v.get(b, ZERO) - c * d
                if nv:
                    v[b] = nv
                    if b in rows and b not in done and b != a:
                        heappush(heap, b)
                else:
                    v.pop(b, None)
        return v

    def add_ivec(self, vec):
        r = self.reduce(vec)
        if not r:
            return self
        p = min(r)
        lead = r[p]
        if lead != 1:
            r = {a: c / lead for a, c in r.items()}
        nr = dict(self.rows)
        nr[p] = r
        return Span(nr)

    def add(self, ident):
        return self.add_ivec(_ivec(ident))

    def contains(self, ident):
        return not self.reduce(_ivec(ident))


def span_of(ids):
    s = Span()
    for x in ids:
        s = s.add(x)
    return s


def _normalise(r):
    p = min(r)
    lead = r[p]
    return p, {a: c / lead for a, c in r.items()}


def engine_closes(ids, goal):
    """the engine: goal in Q-span of identities"""
    return span_of(ids).contains(goal)


def closing_results(ids, goal, span=None, cands=None):
    """set of candidate results r (identities) such that engine closes on ids+[r] (single move closes). Fast residual test."""
    sp = span if span is not None else span_of(ids)
    rho = sp.reduce(_ivec(goal))
    if not rho:
        return None   # already closes
    pr, nr = _normalise(rho)
    out = set()
    cs = cands if cands is not None else candidates(ids)
    for c in cs:
        v = sp.reduce(_ivec(c.result))
        if not v or min(v) != pr:
            continue
        lead = v[pr]
        if len(v) != len(nr):
            continue
        ok = True
        for a, x in v.items():
            if nr.get(a) is None or x / lead != nr[a]:
                ok = False
                break
        if ok:
            out.add(c.result)
    return out


# ----------------------------------------------------------------------------- parser / printer
_TOK = re.compile(r"\s*(\d+\.?\d*|[xyf()+\-*/^=]|\*\*)")


def _tokens(s):
    s = s.replace("**", "^")
    pos, out = 0, []
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            if s[pos:].strip() == "":
                break
            raise ValueError(f"bad token at {s[pos:]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


class _P:
    def __init__(self, toks):
        self.t, self.k = toks, 0

    def peek(self):
        return self.t[self.k] if self.k < len(self.t) else None

    def eat(self, x=None):
        v = self.peek()
        if x is not None and v != x:
            raise ValueError(f"expected {x} got {v}")
        self.k += 1
        return v

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.eat()
            w = self.term()
            v = _vadd(v, w, 1 if op == "+" else -1)
        return v

    def term(self):
        if self.peek() == "-":
            self.eat()
            return _vscale(self.term(), Fr(-1))
        if self.peek() == "+":
            self.eat()
            return self.term()
        v = self.power()
        while self.peek() in ("*", "/") or self.peek() in ("x", "y", "f", "("):
            if self.peek() == "/":
                self.eat()
                d = self.power()
                c = _as_const(d)
                v = _vscale(v, 1 / c)
            else:
                if self.peek() == "*":
                    self.eat()
                w = self.power()
                v = _vmul(v, w)
        return v

    def power(self):
        v = self.atom()
        if self.peek() == "^":
            self.eat()
            n = int(self.eat())
            r = {(1, 0, 0): ONE}
            for _ in range(n):
                r = _vmul(r, v)
            return r
        return v

    def atom(self):
        t = self.eat()
        if t is None:
            raise ValueError("unexpected end")
        if t == "(":
            v = self.expr()
            self.eat(")")
            return v
        if t == "x":
            return {(1, 1, 0): ONE}
        if t == "y":
            return {(1, 0, 1): ONE}
        if t == "f":
            self.eat("(")
            a = self.expr()
            self.eat(")")
            form = _as_form(a)
            return {(0,) + form: ONE}
        return {(1, 0, 0): Fr(t)}


def _vadd(a, b, s=1):
    o = dict(a)
    for k, c in b.items():
        o[k] = o.get(k, ZERO) + s * c
    return {k: c for k, c in o.items() if c}


def _vscale(a, c):
    return {k: v * c for k, v in a.items()}


def _as_const(a):
    if all(k == (1, 0, 0) for k in a):
        return a.get((1, 0, 0), ZERO)
    raise ValueError("expected a constant")


def _vmul(a, b):
    if all(k[0] == 1 for k in a) and all(k[0] == 1 for k in b):
        o = {}
        for (_, i, j), c in a.items():
            for (_, k, l), d in b.items():
                key = (1, i + k, j + l)
                o[key] = o.get(key, ZERO) + c * d
        return {k: v for k, v in o.items() if v}
    if all(k == (1, 0, 0) for k in a):
        return _vscale(b, a.get((1, 0, 0), ZERO))
    if all(k == (1, 0, 0) for k in b):
        return _vscale(a, b.get((1, 0, 0), ZERO))
    raise ValueError("f-terms must carry constant coefficients")


def _as_form(a):
    p = q = r = ZERO
    for k, c in a.items():
        if k[0] != 1 or k[1] + k[2] > 1:
            raise ValueError("f argument must be a linear form")
        if k[1:] == (1, 0): p += c
        elif k[1:] == (0, 1): q += c
        else: r += c
    return (p, q, r)


def parse(s):
    """'f(x+y) = f(x) + f(y) + 2xy' -> canonical identity (lhs - rhs = 0).  Use parse_goal for goals (same thing)."""
    if "=" in s:
        l, r = s.split("=")
        pl, pr = _P(_tokens(l)), _P(_tokens(r))
        v = _vadd(pl.expr(), pr.expr(), -1)
    else:
        v = _P(_tokens(s)).expr()
    return canon(v)


def _fmt_c(c):
    return str(c.numerator) if c.denominator == 1 else f"{c.numerator}/{c.denominator}"


def _fmt_lin(p, q, r):
    parts = []
    for c, n in ((p, "x"), (q, "y"), (r, "")):
        if not c:
            continue
        if n:
            t = n if abs(c) == 1 else f"{_fmt_c(abs(c))}{n}"
        else:
            t = _fmt_c(abs(c))
        parts.append(("-" if c < 0 else "+", t))
    if not parts:
        return "0"
    s = ("-" if parts[0][0] == "-" else "") + parts[0][1]
    for sg, t in parts[1:]:
        s += f" {sg} {t}"
    return s


def fmt_atom(at):
    if at[0] == 0:
        return f"f({_fmt_lin(*at[1:])})"
    _, i, j = at
    if i == j == 0:
        return "1"
    s = ""
    if i: s += "x" + (f"^{i}" if i > 1 else "")
    if j: s += "y" + (f"^{j}" if j > 1 else "")
    return s


def fmt(ident):
    """human-readable 'LHS = RHS' with f-terms on the left and polynomial on the right where possible."""
    if ident is None:
        return "0 = 0"
    L = [(a, c) for a, c in ident if a[0] == 0]
    R = [(a, -c) for a, c in ident if a[0] == 1]
    if not L:
        L, R = [(a, c) for a, c in ident], []

    def side(terms):
        if not terms:
            return "0"
        s = ""
        for n, (a, c) in enumerate(terms):
            body = fmt_atom(a)
            ac = abs(c)
            if a == (1, 0, 0):
                t = _fmt_c(ac)
            else:
                t = body if ac == 1 else f"{_fmt_c(ac)}{body if a[0] == 1 else '*' + body}"
            sg = "-" if c < 0 else "+"
            s += (("-" if sg == "-" else "") + t) if n == 0 else f" {sg} {t}"
        return s
    return f"{side(L)} = {side(R)}"


# ----------------------------------------------------------------------------- misc helpers on identities
def atoms_of(ident):
    return {a for a, _ in ident}


def f_atoms(ident):
    return {a for a, _ in ident if a[0] == 0}


def is_const_sigma(s):
    return s in CONST_SIGMAS


# ----------------------------------------------------------------------------- isomorphism key
def _swap_dict(vec):
    return _rename_y_to_x(vec)


def _scale_f(vec, c):
    return {a: (v * c if a[0] == 0 else v) for a, v in vec.items()}


def _canon_noren(vec):
    vec = {a: c for a, c in vec.items() if c}
    items = sorted(vec.items())
    if not items:
        return ()
    lead = items[0][1]
    return tuple((a, c / lead) for a, c in items)


def _renorm(vec):
    """y-only -> x renaming (identity canonicalisation) on a dict vector"""
    ux, uy = _uses(vec)
    return _rename_y_to_x(vec) if (uy and not ux) else vec


def iso_key(E, T):
    """canonical key of (E,T) under x<->y renaming and joint scaling f -> c f (c != 0 rational). After the swap both E and T are
    re-canonicalised as identities (y-only -> x) before keying. Returns a string."""
    best = None
    for ren in (False, True):
        e, t = dict(E), dict(T)
        if ren:
            e, t = _renorm(_swap_dict(e)), _renorm(_swap_dict(t))
        c = ONE
        for d in (e, t):
            fs = [(a, v) for a, v in sorted(d.items()) if a[0] == 0]
            ms = [(a, v) for a, v in sorted(d.items()) if a[0] == 1]
            if fs and ms:
                c = ms[0][1] / fs[0][1]
                break
        e, t = _scale_f(e, c), _scale_f(t, c)
        key = repr((_canon_noren(e), _canon_noren(t)))
        if best is None or key < best:
            best = key
    return best


# ----------------------------------------------------------------------------- JSON round trip
def ident_to_json(ident):
    out = []
    for a, c in ident:
        if a[0] == 0:
            out.append([0, str(a[1]), str(a[2]), str(a[3]), str(c)])
        else:
            out.append([1, a[1], a[2], str(c)])
    return out


def ident_from_json(js):
    out = []
    for t in js:
        if t[0] == 0:
            out.append(((0, Fr(t[1]), Fr(t[2]), Fr(t[3])), Fr(t[4])))
        else:
            out.append(((1, t[1], t[2]), Fr(t[3])))
    return tuple(out)
