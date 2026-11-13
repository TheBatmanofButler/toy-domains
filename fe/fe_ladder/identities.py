"""Identities and substitutions. Nothing else in the code knows how a substitution changes an identity.

An identity is a sum of terms with rational coefficients that equals zero for all rational x and y. It is held
in one fixed form: a tuple of (term, coefficient) pairs in term order, zero coefficients dropped, scaled so the
first coefficient is 1, and with y renamed to x if y is the only variable. The text form is in identity_text.py.
"""
from fractions import Fraction
from functools import lru_cache

# A term is a tuple. (F_TERM, a, b, c) is f(a x + b y + c); (POWER, i, j) is x^i y^j, and (POWER, 0, 0) is the
# constant 1. Tuple order is the fixed term order: every f(...) before every power, each kind by its numbers.
# This is the earlier run's order, so the fixed form, and with it the problems the generator makes, agree.
F_TERM, POWER = 0, 1
ONE, ZERO = Fraction(1), Fraction(0)

SUBSTITUTIONS = ("x=0, y=0", "y=0", "x=0", "y=x", "y=-x", "swap x,y", "y=1", "x=x+y, y=-y", "y=x+y", "x=1",
                 "x=-x", "y=-y", "x=x-y, y=x+y")
# What x and what y become, each as (p, q, r) = p x + q y + r. The two parts of a two-part substitution are
# applied at once: both read the old x and y.
_NEW_X_Y = {
    "x=0, y=0": ((0, 0, 0), (0, 0, 0)),
    "y=0": ((1, 0, 0), (0, 0, 0)),
    "x=0": ((0, 0, 0), (0, 1, 0)),
    "y=x": ((1, 0, 0), (1, 0, 0)),
    "y=-x": ((1, 0, 0), (-1, 0, 0)),
    "swap x,y": ((0, 1, 0), (1, 0, 0)),
    "y=1": ((1, 0, 0), (0, 0, 1)),
    "x=x+y, y=-y": ((1, 1, 0), (0, -1, 0)),
    "y=x+y": ((1, 0, 0), (1, 1, 0)),
    "x=1": ((0, 0, 1), (0, 1, 0)),
    "x=-x": ((-1, 0, 0), (0, 1, 0)),
    "y=-y": ((1, 0, 0), (0, -1, 0)),
    "x=x-y, y=x+y": ((1, -1, 0), (1, 1, 0)),
}
NEW_X_Y = {name: tuple(tuple(Fraction(n) for n in part) for part in parts) for name, parts in _NEW_X_Y.items()}
# The substitutions that put a number in place of a variable.
BRING_IN_A_CONSTANT = ("x=0, y=0", "y=0", "x=0", "y=1", "x=1")


def _variables_used(vector):
    uses_x = any(term[1] for term in vector)
    uses_y = any(term[2] for term in vector)
    return uses_x, uses_y


def _swap_term(term):
    return (term[0], term[2], term[1]) + term[3:]


def _swapped(vector):
    return {_swap_term(term): c for term, c in vector.items()}


def _only_y_renamed(vector):
    """Renaming y to x when y is the only variable is sound: both stand for every rational number."""
    uses_x, uses_y = _variables_used(vector)
    return _swapped(vector) if uses_y and not uses_x else vector


def fixed_form(vector):
    """{term: coefficient} -> the identity in its fixed form, or None if every coefficient is zero (0 = 0)."""
    vector = {term: Fraction(c) for term, c in vector.items() if c}
    if not vector:
        return None
    items = sorted(_only_y_renamed(vector).items())
    lead = items[0][1]
    return tuple((term, c / lead) for term, c in items)


def terms(identity):
    return frozenset(term for term, _ in identity)


def _times(p, q):
    """Product of two polynomials held as {(i, j): coefficient}."""
    out = {}
    for (i, j), c in p.items():
        for (k, m), d in q.items():
            out[(i + k, j + m)] = out.get((i + k, j + m), ZERO) + c * d
    return {key: c for key, c in out.items() if c}


def _as_polynomial(form):
    p, q, r = form
    return {key: c for key, c in (((1, 0), p), ((0, 1), q), ((0, 0), r)) if c}


@lru_cache(maxsize=None)
def _power_after(substitution, i, j):
    """x^i y^j after the substitution, as ((i, j), coefficient) pairs."""
    new_x, new_y = NEW_X_Y[substitution]
    result = {(0, 0): ONE}
    for _ in range(i):
        result = _times(result, _as_polynomial(new_x))
    for _ in range(j):
        result = _times(result, _as_polynomial(new_y))
    return tuple(result.items())


@lru_cache(maxsize=2_000_000)
def apply(identity, substitution):
    """The identity after the substitution, in the fixed form, or None if nothing is left (0 = 0)."""
    new_x, new_y = NEW_X_Y[substitution]
    out = {}
    for term, c in identity:
        if term[0] == F_TERM:
            _, a, b, k = term
            argument = (F_TERM, a * new_x[0] + b * new_y[0], a * new_x[1] + b * new_y[1], a * new_x[2] + b * new_y[2] + k)
            out[argument] = out.get(argument, ZERO) + c
        else:
            for (i, j), d in _power_after(substitution, term[1], term[2]):
                out[(POWER, i, j)] = out.get((POWER, i, j), ZERO) + c * d
    return fixed_form(out)


def swap(identity):
    """The identity with x and y exchanged, in the fixed form."""
    return fixed_form(_swapped(dict(identity)))


def scale_f(identity, factor):
    """The identity for f replaced by factor * f, in the fixed form."""
    return fixed_form({term: c * factor if term[0] == F_TERM else c for term, c in identity})


def _scaled_to_one(vector):
    items = sorted(vector.items())
    return tuple((term, c / items[0][1]) for term, c in items)


def problem_key(equation, goal):
    """Equal for two problems exactly when one becomes the other by swapping x and y, or scaling f, or both.

    For each of the two namings, f is scaled so that, in the first of the two identities holding both an f(...)
    and a power, the first f(...) and the first power have the same coefficient; identities with no power do
    not change under scaling f. The key is the smaller of the two results.
    """
    keys = []
    for swapped in (False, True):
        pair = [dict(equation), dict(goal)]
        if swapped:
            pair = [_only_y_renamed(_swapped(vector)) for vector in pair]
        factor = ONE
        for vector in pair:
            f_terms = sorted((t, c) for t, c in vector.items() if t[0] == F_TERM)
            powers = sorted((t, c) for t, c in vector.items() if t[0] == POWER)
            if f_terms and powers:
                factor = powers[0][1] / f_terms[0][1]
                break
        scaled = [{t: c * factor if t[0] == F_TERM else c for t, c in vector.items()} for vector in pair]
        keys.append(tuple(_scaled_to_one(vector) for vector in scaled))
    return min(keys)
