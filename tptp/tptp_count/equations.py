"""Terms and equations: reading and writing them, their size, and when two of them, or two lists of them,
are the same up to renaming.

A variable is a string starting with an upper-case letter; any other term is a tuple (symbol, arg, ...), so a
constant is a one-element tuple. An equation is a pair (left, right); its variables are read as "for all", and
its two sides may be read in either order.
"""
import re

_TOKEN = re.compile(r"\s*('(?:[^'\\]|\\.)*'|[A-Za-z0-9_$]+|!=|=|\(|\)|,)")


class EquationError(ValueError):
    pass


def is_variable(term):
    return isinstance(term, str)


def _tokens(text):
    tokens, position = [], 0
    while position < len(text):
        found = _TOKEN.match(text, position)
        if not found:
            if text[position:].strip():
                raise EquationError(f"cannot read {text!r} at {text[position:]!r}")
            break
        tokens.append(found.group(1))
        position = found.end()
    return tokens


def read_term_tokens(tokens, i):
    """One term from tokens[i:]; returns (term, next index)."""
    if i >= len(tokens) or tokens[i] in ("(", ")", ",", "=", "!="):
        raise EquationError(f"a term was expected at {' '.join(tokens[i:i + 3])!r}")
    name, i = tokens[i], i + 1
    if name[0].isupper():
        return name, i
    if name[0] == "$":   # TPTP's defined symbols ($true, $sum, ...) are not part of an equation between terms
        raise EquationError(f"defined symbol {name}")
    if i < len(tokens) and tokens[i] == "(":
        arguments, i = [], i + 1
        while True:
            argument, i = read_term_tokens(tokens, i)
            arguments.append(argument)
            if i >= len(tokens) or tokens[i] not in (",", ")"):
                raise EquationError(f"',' or ')' expected after an argument of {name}")
            i += 1
            if tokens[i - 1] == ")":
                return (name, *arguments), i
    return (name,), i


def read_relation(text):
    """'l = r' or 'l != r' -> (sign, (l, r)), sign being '=' or '!='."""
    tokens = _tokens(text)
    left, i = read_term_tokens(tokens, 0)
    if i >= len(tokens) or tokens[i] not in ("=", "!="):
        raise EquationError(f"'=' or '!=' expected in {text!r}")
    sign = tokens[i]
    right, i = read_term_tokens(tokens, i + 1)
    if i != len(tokens):
        raise EquationError(f"text left over in {text!r}")
    return sign, (left, right)


def read_equation(text):
    sign, equation = read_relation(text)
    if sign != "=":
        raise EquationError(f"{text!r} is not an equation")
    return equation


def write_term(term):
    if is_variable(term):
        return term
    if len(term) == 1:
        return term[0]
    return term[0] + "(" + ",".join(write_term(a) for a in term[1:]) + ")"


def write_equation(equation):
    return write_term(equation[0]) + "=" + write_term(equation[1])


def _walk(term):
    """Every subterm, depth first, left to right."""
    yield term
    if not is_variable(term):
        for argument in term[1:]:
            yield from _walk(argument)


def size(equation):
    """Number of symbol occurrences on both sides, variables included."""
    return sum(1 for side in equation for _ in _walk(side))


def variables(equation):
    """The variables in order of first occurrence, left side first."""
    found = []
    for side in equation:
        for term in _walk(side):
            if is_variable(term) and term not in found:
                found.append(term)
    return found


def symbols(equation):
    """{symbol: arity} for every function symbol and constant in the equation."""
    return {term[0]: len(term) - 1 for side in equation for term in _walk(side) if not is_variable(term)}


def substitute(term, values):
    if is_variable(term):
        return values.get(term, term)
    return (term[0], *(substitute(a, values) for a in term[1:]))


def rename_symbols(equation, names):
    def rename(term):
        if is_variable(term):
            return term
        return (names.get(term[0], term[0]), *(rename(a) for a in term[1:]))
    return rename(equation[0]), rename(equation[1])


def _match(pattern, term, values):
    """Extends `values` so that pattern with them filled in is term; False if it cannot."""
    if is_variable(pattern):
        if pattern in values:
            return values[pattern] == term
        values[pattern] = term
        return True
    if is_variable(term) or pattern[0] != term[0] or len(pattern) != len(term):
        return False
    return all(_match(p, t, values) for p, t in zip(pattern[1:], term[1:]))


def is_instance(equation, of):
    """Whether `equation` is `of` with its variables filled in (a variable may be filled with a variable),
    reading `of` either way round."""
    for left, right in ((of[0], of[1]), (of[1], of[0])):
        values = {}
        if _match(left, equation[0], values) and _match(right, equation[1], values):
            return True
    return False


def _write_with_labels(term, labels, variable_names):
    if is_variable(term):
        if term not in variable_names:
            variable_names[term] = f"X{len(variable_names)}"
        return variable_names[term]
    name = labels.get(term[0], term[0])
    if len(term) == 1:
        return name
    return name + "(" + ",".join(_write_with_labels(a, labels, variable_names) for a in term[1:]) + ")"


def _labelled(equation, labels):
    """The equation written with symbols replaced by `labels` and variables by X0, X1, ... in order of first
    occurrence, taking whichever of the two side orders writes smaller."""
    ways = []
    for left, right in ((equation[0], equation[1]), (equation[1], equation[0])):
        names = {}
        ways.append(_write_with_labels(left, labels, names) + "=" + _write_with_labels(right, labels, names))
    return min(ways)


def key_up_to_variables(equation):
    """Equal for two equations exactly when one becomes the other by renaming variables (and reading it the
    other way round). Symbols are not renamed: this is the sameness of facts. `key` below, which renames symbols
    too, is the sameness of axiom sets and problems."""
    return _labelled(equation, {})


def universal_form(goal, axioms):
    """The goal as a law: TPTP writes the goal denied, with a fresh constant for each of its variables; the
    constants that appear in no axiom are turned back into variables (named by first occurrence)."""
    known = set()
    for axiom in axioms:
        known.update(symbols(axiom))
    fresh = {}
    for side in goal:
        for term in _walk(side):
            if not is_variable(term) and len(term) == 1 and term[0] not in known and term[0] not in fresh:
                fresh[term[0]] = f"X{len(fresh)}"

    def turn(term):
        if is_variable(term):
            return term
        if len(term) == 1 and term[0] in fresh:
            return fresh[term[0]]
        return (term[0], *(turn(a) for a in term[1:]))
    return turn(goal[0]), turn(goal[1])


def key(equations, goal=None):
    """Equal for two lists of equations (each read as a set) exactly when one becomes the other by renaming
    symbols (each to one of the same arity) and variables. With `goal`, the goal must go to the goal under the
    same renaming: this is what makes two files the same problem. The work is done in renaming.py."""
    from tptp_count.renaming import canonical_labels   # here, because renaming.py builds on this file
    text, _ = canonical_labels(equations, goal)
    return text


def symbol_renaming(source, target):
    """A renaming of symbols that turns the set of equations `source` into `target`, or None if there is none."""
    from tptp_count.renaming import canonical_labels
    source_text, source_labels = canonical_labels(source)
    target_text, target_labels = canonical_labels(target)
    if source_text != target_text:
        return None
    by_label = {label: symbol for symbol, label in target_labels.items()}
    return {symbol: by_label[label] for symbol, label in source_labels.items()}
