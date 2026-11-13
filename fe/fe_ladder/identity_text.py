"""Identities as text, in the form the question shows, and back. Taken from the earlier run's printer and parser.

The text puts the f(...) terms on the left and the powers of x and y on the right, all scaled to whole numbers
with no common factor and a positive first term. Reading the text and putting it in the fixed form gives back
the identity exactly; the scaling for display never changes the identity.
"""
import re
from fractions import Fraction
from functools import reduce
from math import gcd

from fe_ladder.identities import F_TERM, ONE, POWER, ZERO, fixed_form


def _number(q):
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def _times_variable(size, variable):
    if variable == "":
        return _number(size)
    if size == 1:
        return variable
    if size.denominator == 1:
        return f"{size.numerator}{variable}"
    if size.numerator == 1:
        return f"{variable}/{size.denominator}"
    return f"({_number(size)}){variable}"


def _linear(a, b, c):
    """a x + b y + c written as 'x + y', '-x', '2x - 1', 'x/2', '0'."""
    parts = [(q, v) for q, v in ((a, "x"), (b, "y"), (c, "")) if q != 0]
    if not parts:
        return "0"
    out = ""
    for n, (q, v) in enumerate(parts):
        body = _times_variable(abs(q), v)
        out += (("-" if q < 0 else "") + body) if n == 0 else ((" - " if q < 0 else " + ") + body)
    return out


def _power(i, j):
    return ("" if i == 0 else "x" if i == 1 else f"x^{i}") + ("" if j == 0 else "y" if j == 1 else f"y^{j}")


def _display_order(term):
    # The earlier run's display order: f(...) by decreasing a, b, c; then powers by decreasing degree, then by x.
    if term[0] == F_TERM:
        return (0, -term[1], -term[2], -term[3])
    return (1, -(term[1] + term[2]), -term[1])


def _join(items):
    if not items:
        return "0"
    out = ""
    for n, (negative, body) in enumerate(items):
        out += (("-" if negative else "") + body) if n == 0 else ((" - " if negative else " + ") + body)
    return out


def _factor(c):
    return "" if abs(c) == 1 else _number(abs(c))


def _power_term(term, c):
    """A power with the size of its coefficient: '3x^2', 'xy', or the number alone for the constant 1."""
    power = _power(term[1], term[2])
    if power:
        return f"{_factor(c)}{power}"
    return _number(abs(c))


def write_identity(identity):
    """'LHS = RHS', for example 'f(x + y) - f(x) - f(y) = 2xy'."""
    ordered = sorted(identity, key=lambda pair: _display_order(pair[0]))
    denominator = reduce(lambda p, q: p * q // gcd(p, q), (c.denominator for _, c in ordered), 1)
    whole = [int(c * denominator) for _, c in ordered]
    common = reduce(gcd, (abs(n) for n in whole)) * (-1 if whole[0] < 0 else 1)
    shown = [(term, Fraction(n, common)) for (term, _), n in zip(ordered, whole)]
    left = [(c < 0, f"{_factor(c)}f({_linear(*term[1:])})") for term, c in shown if term[0] == F_TERM]
    # Powers go to the right side, so their sign is turned over there.
    right = [(c > 0, _power_term(term, c)) for term, c in shown if term[0] == POWER]
    if not left:   # no f(...) at all: shown as a polynomial equal to 0
        left = [(c < 0, _power_term(term, c)) for term, c in shown]
        right = []
    return f"{_join(left)} = {_join(right)}"


_TOKEN = re.compile(r"\s*(\d+|[xyf()+\-*/^])")


def _tokens(text):
    out, position = [], 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if not match:
            if text[position:].strip() == "":
                break
            raise ValueError(f"cannot read {text[position:]!r}")
        out.append(match.group(1))
        position = match.end()
    return out


def _add(p, q, sign=1):
    out = dict(p)
    for key, c in q.items():
        out[key] = out.get(key, ZERO) + sign * c
    return {key: c for key, c in out.items() if c}


def _constant(p):
    if any(key != (POWER, 0, 0) for key in p):
        raise ValueError("expected a number")
    return p.get((POWER, 0, 0), ZERO)


def _multiply(p, q):
    if all(key[0] == POWER for key in p) and all(key[0] == POWER for key in q):
        out = {}
        for (_, i, j), c in p.items():
            for (_, k, m), d in q.items():
                out[(POWER, i + k, j + m)] = out.get((POWER, i + k, j + m), ZERO) + c * d
        return {key: c for key, c in out.items() if c}
    if all(key == (POWER, 0, 0) for key in p):
        return {key: c * _constant(p) for key, c in q.items()}
    if all(key == (POWER, 0, 0) for key in q):
        return {key: c * _constant(q) for key, c in p.items()}
    raise ValueError("an f(...) term may only be multiplied by a number")


class _Reader:
    """Reads a sum of terms: numbers, x, y, f(linear), products, powers, brackets, division by numbers."""

    def __init__(self, tokens):
        self.tokens, self.at = tokens, 0

    def peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError(f"expected {expected or 'more'}, found {token}")
        self.at += 1
        return token

    def sum(self):
        value = self.product()
        while self.peek() in ("+", "-"):
            sign = 1 if self.take() == "+" else -1
            value = _add(value, self.product(), sign)
        return value

    def product(self):
        if self.peek() in ("+", "-"):
            sign = -1 if self.take() == "-" else 1
            return {key: sign * c for key, c in self.product().items()}
        value = self.power()
        while self.peek() in ("*", "/", "x", "y", "f", "("):
            if self.peek() == "/":
                self.take()
                divisor = _constant(self.power())
                value = {key: c / divisor for key, c in value.items()}
            else:
                if self.peek() == "*":
                    self.take()
                value = _multiply(value, self.power())
        return value

    def power(self):
        value = self.single()
        if self.peek() == "^":
            self.take()
            result = {(POWER, 0, 0): ONE}
            for _ in range(int(self.take())):
                result = _multiply(result, value)
            return result
        return value

    def single(self):
        token = self.take()
        if token == "(":
            value = self.sum()
            self.take(")")
            return value
        if token in ("x", "y"):
            return {(POWER, 1, 0) if token == "x" else (POWER, 0, 1): ONE}
        if token == "f":
            self.take("(")
            argument = self.sum()
            self.take(")")
            if any(key[0] != POWER or key[1] + key[2] > 1 for key in argument):
                raise ValueError("the argument of f must be linear in x and y")
            a, b, c = (argument.get((POWER, 1, 0), ZERO), argument.get((POWER, 0, 1), ZERO),
                       argument.get((POWER, 0, 0), ZERO))
            return {(F_TERM, a, b, c): ONE}
        if token.isdigit():
            return {(POWER, 0, 0): Fraction(int(token))}
        raise ValueError(f"unexpected {token!r}")


def _side(text):
    reader = _Reader(_tokens(text))
    value = reader.sum()
    if reader.peek() is not None:
        raise ValueError(f"cannot read {text!r}")
    return value


def read_identity(text):
    """'LHS = RHS' (or a sum meaning '= 0') -> the identity in its fixed form, or None for 0 = 0."""
    if text.count("=") > 1:
        raise ValueError(f"more than one '=' in {text!r}")
    left, _, right = text.partition("=")
    return fixed_form(_add(_side(left), _side(right) if right.strip() else {}, -1))
