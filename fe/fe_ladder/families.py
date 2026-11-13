"""The seven families of functions an equation is built for, and exact checks that an identity holds for one.

A family is a fixed polynomial plus any rational combination of some basis polynomials (for example "affine":
every a x + b). An identity holds for the family when it holds for every member at every x and y; this is
checked exactly by expanding f at each argument. Taken from the earlier run's generator, with every random
draw in the same order, so that the same seed and attempt give the same problem.
"""
from fractions import Fraction

from fe_ladder.identities import F_TERM, ONE, POWER, ZERO, fixed_form

NAMES = ["affine", "affine_fixed", "cauchy", "cauchy_p", "quad", "lin_quad", "const"]
WEIGHTS = [3, 2, 2, 2, 2, 2, 1]


def _times(p, q):
    out = {}
    for (i, j), c in p.items():
        for (k, m), d in q.items():
            out[(i + k, j + m)] = out.get((i + k, j + m), ZERO) + c * d
    return {key: c for key, c in out.items() if c}


def at_argument(polynomial, argument):
    """{n: coefficient} in one variable, taken at a x + b y + c -> {(i, j): coefficient} in x and y."""
    a, b, c = argument
    linear = {key: v for key, v in (((1, 0), a), ((0, 1), b), ((0, 0), c)) if v}
    out, power = {}, {(0, 0): ONE}
    for n in range(max(polynomial, default=-1) + 1):
        if n:
            power = _times(power, linear)
        if polynomial.get(n, ZERO):
            for key, v in power.items():
                out[key] = out.get(key, ZERO) + polynomial[n] * v
    return {key: v for key, v in out.items() if v}


class Family:
    def __init__(self, name, fixed, basis, numbers=None):
        self.name, self.fixed, self.basis, self.numbers = name, fixed, basis, numbers or {}

    def random_member(self, rng):
        """One member of the family, as {n: coefficient} in one variable."""
        out = dict(self.fixed)
        for polynomial in self.basis:
            t = Fraction(rng.randint(-5, 5), rng.choice([1, 2, 3]))
            for n, v in polynomial.items():
                out[n] = out.get(n, ZERO) + t * v
        return out


def make_family(name, rng):
    def nonzero():
        return Fraction(rng.choice([1, 2, 3, 1, 2]) * rng.choice([1, -1]), rng.choice([1, 1, 2]))
    if name == "affine":
        return Family(name, {}, [{1: ONE}, {0: ONE}])
    if name == "affine_fixed":
        b0 = nonzero()
        return Family(name, {0: b0}, [{1: ONE}], {"b0": b0})
    if name == "cauchy":
        return Family(name, {}, [{1: ONE}])
    if name == "cauchy_p":
        d0 = nonzero()
        return Family(name, {2: d0}, [{1: ONE}], {"d0": d0})
    if name == "quad":
        return Family(name, {}, [{2: ONE}])
    if name == "lin_quad":
        return Family(name, {}, [{1: ONE}, {2: ONE}])
    if name == "const":
        return Family(name, {}, [{0: ONE}])
    raise KeyError(name)


def _parts(family, term):
    """For an f(...) term: each basis polynomial at its argument, and the fixed polynomial at its argument."""
    argument = term[1:]
    return [at_argument(b, argument) for b in family.basis], at_argument(family.fixed, argument)


def holds(family, identity):
    """Exactly: the identity holds for every member of the family at every x and y."""
    per_basis = [dict() for _ in family.basis]
    rest = {}
    for term, c in identity:
        if term[0] == F_TERM:
            basis_parts, fixed_part = _parts(family, term)
            for t, part in enumerate(basis_parts):
                for key, v in part.items():
                    per_basis[t][key] = per_basis[t].get(key, ZERO) + c * v
            for key, v in fixed_part.items():
                rest[key] = rest.get(key, ZERO) + c * v
        else:
            rest[(term[1], term[2])] = rest.get((term[1], term[2]), ZERO) + c
    return all(not v for part in per_basis for v in part.values()) and all(not v for v in rest.values())


def value(identity, function, x, y):
    """The identity's left side at (x, y), with f given as a Python function."""
    total = ZERO
    for term, c in identity:
        if term[0] == F_TERM:
            total += c * function(term[1] * x + term[2] * y + term[3])
        else:
            total += c * x ** term[1] * y ** term[2]
    return total


def holds_at_points(family, identity, rng, points=20):
    """The identity holds for a random member of the family at each of `points` random rational points."""
    for _ in range(points):
        member = family.random_member(rng)
        x = Fraction(rng.randint(-9, 9), rng.randint(1, 5))
        y = Fraction(rng.randint(-9, 9), rng.randint(1, 5))
        if value(identity, lambda t, m=member: sum(v * t ** k for k, v in m.items()), x, y) != 0:
            return False
    return True


def _null_space(rows, columns):
    """A basis of the vectors that every row ({column: number}) sends to zero, by exact elimination."""
    pivots, reduced = [], []
    for row in (dict(r) for r in rows if r):
        for pivot, done in zip(pivots, reduced):
            if pivot in row:
                c = row[pivot]
                for k, v in done.items():
                    left = row.get(k, ZERO) - c * v
                    if left:
                        row[k] = left
                    else:
                        row.pop(k, None)
        if not row:
            continue
        pivot = min(row)
        row = {k: v / row[pivot] for k, v in row.items()}
        for done in reduced:
            if pivot in done:
                c = done[pivot]
                for k, v in row.items():
                    left = done.get(k, ZERO) - c * v
                    if left:
                        done[k] = left
                    else:
                        done.pop(k, None)
        pivots.append(pivot)
        reduced.append(row)
    basis = []
    for free in (c for c in range(columns) if c not in pivots):
        vector = {free: ONE}
        for pivot, done in zip(pivots, reduced):
            if free in done:
                vector[pivot] = -done[free]
        basis.append(vector)
    return basis


def valid_identities(family, terms):
    """A basis of the identities over these terms (a list) that hold for the family."""
    rows = {}
    for n, term in enumerate(terms):
        if term[0] == F_TERM:
            basis_parts, fixed_part = _parts(family, term)
            for t, part in enumerate(basis_parts):
                for key, v in part.items():
                    rows.setdefault(("basis", t, key), {})[n] = v
            for key, v in fixed_part.items():
                rows.setdefault(("rest", key), {})[n] = v
        else:
            rows.setdefault(("rest", (term[1], term[2])), {})[n] = ONE
    return _null_space(list(rows.values()), len(terms))


_ARGUMENTS = [(ONE, ZERO, ZERO), (ZERO, ONE, ZERO), (ONE, ONE, ZERO), (ONE, -ONE, ZERO), (-ONE, ZERO, ZERO),
              (Fraction(2), ZERO, ZERO), (ZERO, ZERO, ZERO), (ONE, ZERO, ONE), (ZERO, -ONE, ZERO),
              (Fraction(1, 2), Fraction(1, 2), ZERO), (Fraction(2), ONE, ZERO), (ONE, Fraction(2), ZERO),
              (ZERO, Fraction(2), ZERO)]
_POWERS = [(0, 0), (1, 0), (0, 1), (2, 0), (1, 1), (0, 2)]


def random_valid_identity(family, rng, f_terms=(2, 4), powers=(0, 2)):
    """A random identity that holds for the family, over a random handful of terms; None if they allow none."""
    how_many_f = rng.randint(*f_terms)
    how_many_powers = rng.randint(*powers)
    chosen = [(F_TERM,) + a for a in rng.sample(_ARGUMENTS, how_many_f)]
    chosen += [(POWER,) + p for p in rng.sample(_POWERS, how_many_powers)]
    basis = valid_identities(family, chosen)
    if not basis:
        return None
    vector = {}
    for b in basis:
        t = rng.choice([0, 0, 1, -1, 2, Fraction(1, 2)])
        if t:
            for k, v in b.items():
                vector[k] = vector.get(k, ZERO) + Fraction(t) * v
    return fixed_form({chosen[k]: v for k, v in vector.items()})


def combine(first, second, first_times, second_times):
    """first_times * first + second_times * second, as {term: coefficient} (not yet in the fixed form)."""
    out = {}
    for term, c in first:
        out[term] = out.get(term, ZERO) + first_times * c
    for term, c in second:
        out[term] = out.get(term, ZERO) + second_times * c
    return out
