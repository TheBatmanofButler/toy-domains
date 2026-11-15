"""Reads one TPTP problem file, with the axiom files it includes, and says whether it is usable: made only of
equations, with a goal that is a single denied equation. Also says which status words mean the goal follows.

Only TPTP's plain syntax is read: statements `cnf(...)`, `fof(...)` and `include(...)`. Statements in the
typed languages are read only far enough to say the file is not usable.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from tptp_count.equations import EquationError, read_relation

# The status words that mean the goal follows from the axioms. TPTP gives each problem one status word in its
# header; the words are those of the SZS ontology (G. Sutcliffe, "The SZS Ontologies for Automated Reasoning
# Software", 2008), which the TPTP technical manual names as the source of the header's Status field. Only files
# in denied form are usable (see usable), and for those the one word is:
THEOREM_STATUSES = (
    "Unsatisfiable",        # SZS UNS: the axioms with the denied goal have no model, so the goal follows
)

GIVEN_ROLES = ("axiom", "hypothesis", "definition", "assumption", "lemma", "theorem", "corollary", "plain")
GOAL_ROLES = ("conjecture", "negated_conjecture")

_STATUS = re.compile(r"^%\s*Status\s*:\s*(\S+)", re.M)


class TptpError(ValueError):
    pass


@dataclass
class Statement:
    language: str      # cnf, fof, tff, ...
    name: str
    role: str
    formula: str       # the formula's text as written


@dataclass
class TptpFile:
    path: str          # inside the library, for example Problems/GRP/GRP001-1.p
    area: str          # TPTP's three-letter subject area
    status: str
    statements: list = field(default_factory=list)   # in reading order, includes where they stand


def _skip_space_and_comments(text, i):
    while i < len(text):
        if text[i].isspace():
            i += 1
        elif text[i] == "%":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise TptpError("a comment is not closed")
            i = end + 2
        else:
            break
    return i


def _split_top_level(text):
    """Splits at commas outside brackets and quotes. Square brackets count too, so a list of variables
    `! [X,Y] :` is not cut at its comma, as it was by an earlier reader."""
    parts, depth, quote, start = [], 0, None, 0
    for i, char in enumerate(text):
        if quote:
            if char == quote and text[i - 1] != "\\":
                quote = None
        elif char in "'\"":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return parts


_PIECE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|%[^\n]*|[()]")
_WORD = re.compile(r"[a-z]+\s*\(")


def _closing(text, i):
    """Index of the bracket that closes the one at text[i], skipping quoted text and comments."""
    depth = 0
    for piece in _PIECE.finditer(text, i):
        if piece.group() == "(":
            depth += 1
        elif piece.group() == ")":
            depth -= 1
            if depth == 0:
                return piece.start()
    raise TptpError("a bracket is not closed")


def _without_comments(text):
    """The text with comments inside a statement taken out (quoted text is kept as it is)."""
    return _PIECE.sub(lambda piece: "" if piece.group().startswith("%") else piece.group(), text)


def read_statements(text):
    """Yields (word, fields) for each statement: word is cnf, fof, include, ...; fields the comma-separated
    parts inside its brackets. A generator, so that a caller can stop early in a very long file."""
    i = _skip_space_and_comments(text, 0)
    while i < len(text):
        word = _WORD.match(text, i)
        if not word:
            raise TptpError(f"cannot read the file at {text[i:i + 40]!r}")
        open_at = word.end() - 1
        close_at = _closing(text, open_at)
        after = _skip_space_and_comments(text, close_at + 1)
        if not text.startswith(".", after):
            raise TptpError(f"no full stop after {text[i:i + 40]!r}")
        yield word.group(0)[:-1].strip(), _split_top_level(_without_comments(text[open_at + 1:close_at]))
        i = _skip_space_and_comments(text, after + 1)


# Included axiom files are read once per process; for each, only as far as reading needs to go (see read_file).
# The key is the library, the file and the names selected. The files being read when it was first met (the guard
# against a file that includes itself) need not be part of it: a file in a cycle of includes stops the reading
# with an error before anything is kept here, whichever file the reading started from.
_INCLUDED = {}


def _statements(path, library, wanted, reading):
    """Yields the statements of `path` in order, with included files' statements where the include stands.
    `wanted`: the names an include line selects, or None for all."""
    if path in reading:
        raise TptpError(f"{path} includes itself")
    for word, fields in read_statements((library / path).read_text(errors="replace")):
        if word == "include":
            included = fields[0].strip("'\"")
            if not (library / included).is_file():
                raise TptpError(f"{path}: included file {included} is not in the library")
            names = None
            if len(fields) > 1 and fields[1].startswith("["):
                names = frozenset(name.strip() for name in fields[1][1:-1].split(",") if name.strip())
            yield from _included(included, library, names, reading | {path})
        elif len(fields) < 3:
            raise TptpError(f"{path}: a {word} statement has fewer than three parts")
        elif wanted is None or fields[0] in wanted:
            yield Statement(word, fields[0], fields[1], fields[2])


def _until_ruled_out(statements):
    """The statements up to and including the first that is not a single equation: nothing after it can make
    the file usable, and some axiom files are hundreds of megabytes of other formulas."""
    kept = []
    for statement in statements:
        kept.append(statement)
        if relation(statement) is None:
            break
    return kept


def _included(path, library, wanted, reading):
    if (library, path, wanted) not in _INCLUDED:
        _INCLUDED[(library, path, wanted)] = _until_ruled_out(_statements(path, library, wanted, reading))
    return _INCLUDED[(library, path, wanted)]


def read_file(path, library):
    """The status, the area and the statements of the file at `path` (inside `library`), with included files
    read in where they stand. Reading stops at the first statement that is not a single equation."""
    library = Path(library)
    text = (library / path).read_text(errors="replace")
    status = _STATUS.search(text)
    return TptpFile(path=str(path), area=Path(path).name[:3], status=status.group(1) if status else "",
                    statements=_until_ruled_out(_statements(str(path), library, None, frozenset())))


def _strip_brackets(text):
    text = text.strip()
    while text.startswith("(") and _closing(text, 0) == len(text) - 1:
        text = text[1:-1].strip()
    return text


def relation(statement):
    """A statement's formula as (sign, equation), sign '=' or '!='; None if it is anything else."""
    if statement.language not in ("cnf", "fof"):
        return None
    text = _strip_brackets(statement.formula)
    if statement.language == "fof":
        while (quantifier := re.match(r"!\s*\[[^\]]*\]\s*:", text)):   # "for all" is how variables are read anyway
            text = _strip_brackets(text[quantifier.end():])
    denied = text.startswith("~")
    if denied:
        text = _strip_brackets(text[1:])
    try:
        sign, equation = read_relation(text)
    except EquationError:
        return None
    if denied:
        sign = "!=" if sign == "=" else None
    return (sign, equation) if sign else None


def _short(name):
    """Some statement names are whole formulas in quotes; a reason needs only their start."""
    return name if len(name) <= 40 else name[:37] + "..."


def usable(file):
    """True, or the reason the file is not usable, in a few words."""
    goals = [s for s in file.statements if s.role in GOAL_ROLES]
    for statement in file.statements:
        if relation(statement) is None:
            what = "goal" if statement.role in GOAL_ROLES else f"statement {_short(statement.name)}"
            return f"{what} is not a single equation"
        if statement.role not in GOAL_ROLES and statement.role not in GIVEN_ROLES:
            return f"statement {_short(statement.name)} has role {_short(statement.role)}"
        if statement.role not in GOAL_ROLES and relation(statement)[0] != "=":
            return f"statement {_short(statement.name)} is an inequality"
    if not goals:
        return "no goal"
    if len(goals) > 1:
        return f"goal is made of {len(goals)} statements"
    # Only a goal in denied form is used, so that it reaches the prover exactly as TPTP wrote it; a file that
    # states its goal as a conjecture is left out.
    if goals[0].role != "negated_conjecture" or relation(goals[0])[0] != "!=":
        return "goal is not a denied equation"
    return True


def axioms_and_goal(file):
    """For a usable file: the axioms in the file's order, and the goal's two sides."""
    axioms = [relation(s)[1] for s in file.statements if s.role not in GOAL_ROLES]
    goal = next(relation(s)[1] for s in file.statements if s.role in GOAL_ROLES)
    return axioms, goal


def is_theorem(status):
    return status in THEOREM_STATUSES
