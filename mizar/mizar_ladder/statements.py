"""Reads one statement in the provers' notation (TPTP first-order form): its coded symbols, its length, the text the
solver is shown, and whether two statements are the same up to the names of their variables.

In this notation a word starting with a capital letter is a variable and a word starting with a small letter is a
coded symbol (`k3_xboole_0`, `r1_tarski`); `$true` is neither. The text shown replaces each coded symbol by the
name Mizar gives it and changes nothing else, except that a two-place symbol with an operator's name is written
between its arguments: `(A /\\ B)` for a term, `A c= B` for a predicate (coded names starting with `r`). A name is an
operator's when it has a character other than a letter, a digit, `-` or `_`, and has no bracket of any kind and
no `..`: `/\\`, `c=` and `.` are; `in`, `misses`, `-defined`, `[..]`, `{..}`, `[:..:]` and `<....)` are not, and
are written in front of their arguments. The brackets of the shown text always balance: if a statement's would
not, `show` stops. A few Mizar names hold an unpartnered bracket of their own (`[=`, `<....)`, `]....[`); those
characters are part of the name, not of the text's structure.

Two statements are the same when they differ only in the names of their variables or in the order in which a
quantifier lists its variables (`! [B, A]` against `! [A, B]`, or `! [B] : (! [A] :` against `! [A] : (! [B] :`).
Both are taken out the simple way: the variables are renamed V0, V1, ... in the order they first appear outside
the quantifiers' lists, and each quantifier's variables are then sorted (see `canonical`).
"""
import re

_TOKEN = re.compile(r"[A-Za-z0-9_$]+|<=>|=>|<=|<~>|~\||~&|!=|\S")
_SYMBOL = re.compile(r"[a-z][A-Za-z0-9_]*")
_WORD_CHARACTER = re.compile(r"[A-Za-z0-9_$]")
_SYMBOLIC = re.compile(r"[^A-Za-z0-9_-]")
_BRACKETS = {")": "(", "]": "[", "}": "{"}


def tokens(statement):
    return _TOKEN.findall(statement)


def _is_symbol(token):
    return token[0].islower()


def _is_variable(token):
    return token[0].isupper()


def symbols(statement):
    """The different coded symbols in the statement, in order of first appearance."""
    return list(dict.fromkeys(t for t in tokens(statement) if _is_symbol(t)))


def length(statement):
    """The number of symbols and variables in the statement, each occurrence counted (a variable in a
    quantifier's list counts too)."""
    return sum(_is_symbol(t) or _is_variable(t) for t in tokens(statement))


def same_statement(a, b):
    """The same up to the names of variables and the order of each quantifier's list (white space ignored)."""
    return renamed(a) == renamed(b)


_VARIABLE = re.compile(r"(?<![A-Za-z0-9_$])[A-Z][A-Za-z0-9_]*")
_LIST = re.compile(r"([!?]\s*\[)([^\]]*)(\])")


def canonical(statement):
    """The statement with its variables renamed V0, V1, ... in the order they first appear outside the
    quantifiers' lists (then those found only in a list, in list order), and the variables of each quantifier
    sorted. A run of quantifiers of one kind nested directly in one another (`! [A] : (! [B] : ...`, the way the
    library writes Mizar's "for A, B") counts as one quantifier here: its variables are sorted over the run, each
    list keeping its length."""
    outside = _LIST.sub(lambda m: m.group(1) + " " * len(m.group(2)) + m.group(3), statement)
    order = {}
    for found in _VARIABLE.findall(outside) + _VARIABLE.findall(statement):
        order.setdefault(found, f"V{len(order)}")
    plain = _VARIABLE.sub(lambda m: order[m.group(0)], statement)
    lists = list(_LIST.finditer(plain))
    runs, current = [], []
    for match in lists:
        if current and plain[match.start(1)] == plain[current[-1].start(1)] and _NESTED.fullmatch(
                plain, current[-1].end(), match.start()):
            current.append(match)
        else:
            current = [match]
            runs.append(current)
    pieces, at = [], 0
    for run in runs:
        names = sorted((n.strip() for m in run for n in m.group(2).split(",")), key=lambda n: int(n[1:]))
        for match in run:
            size = len(match.group(2).split(","))
            pieces += [plain[at:match.start(2)], ", ".join(names[:size])]
            names, at = names[size:], match.end(2)
    return "".join(pieces) + plain[at:]


_NESTED = re.compile(r"\s*:\s*\(\s*")


def renamed(statement):
    """The tokens of `canonical(statement)`."""
    return tokens(canonical(statement))


def shown_key(statement, names):
    """The shown text of `canonical(statement)`, white space taken out: two statements read the same to the
    solver when their keys are equal. The variables are renamed before the statement is shown, not after: in the
    shown text a word with a capital letter may be a Mizar name (`Element`, `TopStruct`), not a variable."""
    return "".join(show(canonical(statement), names).split())


def show(statement, names):
    """The text the solver sees: each coded symbol replaced by its Mizar name in `names` ({symbol: name}), a
    symbol with no name left as it is, two-place symbols with operators' names written between their arguments,
    and everything else as it was. A bracket without its partner in the statement, or in the brackets the shown
    text is made of (each name counted as a plain word), stops it (ValueError)."""
    text = _render(statement, 0, names, "")[0]
    if not structure_balanced(statement, names):
        raise ValueError(f"the shown text has unbalanced brackets: {text!r}")
    return text


def written_in_front(statement, names):
    """The statement with each coded symbol replaced by its entry in `names`, every symbol written in front of its
    arguments as in the statement (no operator is put between its arguments), and nothing else changed. A symbol
    missing from `names` stops it (KeyError)."""
    missing = [s for s in symbols(statement) if s not in names]
    if missing:
        raise KeyError(f"no replacement for {missing}")
    return _render(statement, 0, names, "", between=False)[0]


def structure_balanced(statement, names):
    """True when the shown text's brackets balance, each Mizar name counted as a plain word."""
    return balanced(_render(statement, 0, {symbol: "name" for symbol in names}, "")[0])


def is_operator(name):
    """True for a Mizar name written between two arguments (see above)."""
    return bool(_SYMBOLIC.search(name)) and not any(c in name for c in "()[]{}") and ".." not in name


def balanced(text):
    """True when every bracket of every kind in `text` has its partner, in order."""
    open_ones = []
    for character in text:
        if character in "([{":
            open_ones.append(character)
        elif character in _BRACKETS:
            if not open_ones or open_ones.pop() != _BRACKETS[character]:
                return False
    return not open_ones


def _render(text, i, names, stops, between=True):
    """The shown form of `text` from position `i` up to the first character in `stops` outside brackets (not
    consumed), or the end. Returns (shown text, position reached)."""
    out = []
    while i < len(text) and text[i] not in stops:
        symbol = _SYMBOL.match(text, i)
        if symbol and (i == 0 or not _WORD_CHARACTER.match(text[i - 1])):
            name, i = symbol.group(0), symbol.end()
            if i < len(text) and text[i] == "(":
                arguments, i = _arguments(text, i + 1, names, between)
                out.append(_applied(name, arguments, names, between))
            else:
                out.append(names.get(name, name))
        elif text[i] == "(":
            inside, i = _render(text, i + 1, names, ")", between)
            if i >= len(text):
                raise ValueError(f"unbalanced statement: {text!r}")
            out.append("(" + inside + ")")
            i += 1
        elif text[i] == ")":
            raise ValueError(f"unbalanced statement: {text!r}")
        else:
            out.append(text[i])
            i += 1
    return "".join(out), i


def _arguments(text, i, names, between=True):
    """The arguments of an application whose "(" ends just before `i`, each with its own spacing, and the
    position after the closing ")"."""
    arguments = []
    while True:
        argument, i = _render(text, i, names, ",)", between)
        if i >= len(text):
            raise ValueError(f"unbalanced statement: {text!r}")
        arguments.append(argument)
        i += 1
        if text[i - 1] == ")":
            return arguments, i


def _applied(symbol, arguments, names, between=True):
    name = names.get(symbol, symbol)
    if between and symbol in names and len(arguments) == 2 and is_operator(name):
        left, right = (a.strip() for a in arguments)
        return f"{left} {name} {right}" if symbol.startswith("r") else f"({left} {name} {right})"
    return name + "(" + ",".join(arguments) + ")"
