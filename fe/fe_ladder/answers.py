"""Reads the model's move from its answer text, and finds the option it belongs to.

The last line that starts with `MOVE:` counts, so a model that changes its mind is read at its final answer,
and a `MOVE:` inside a later sentence of prose is not mistaken for an answer. The label may be in any letter
case. The rest of the line must be `(<identity number>) <substitution>`, with the substitution exactly one of
the 13 as listed, spaces aside (`x=x+y,y=-y` is read as `x=x+y, y=-y`, `y = x + y` as `y=x+y`). As in the
cube's reader, backticks and asterisks are ignored. The longest listed substitution that fits is taken, and
what follows it must be the end of the line (spaces aside); or a full stop, comma or semicolon, then anything;
or one or more spaces and then a letter or an opening bracket (a reason in words or in brackets). Anything else
after spaces, such as an operator or a digit (`y=x - y`, `y=x 2`), makes the answer unreadable rather than a
guess. So `y=x+y` is never read as `y=x`, and `y=x+` is not read at all. A substitution given by its number,
or written another way, is unreadable.
"""
import re

from fe_ladder.identities import SUBSTITUTIONS

_PLAIN = str.maketrans({"`": " ", "*": " "})
_MOVE_LINE = re.compile(r"^\s*MOVE\s*:(.*)$", re.IGNORECASE)
_NUMBERED = re.compile(r"^\s*\(\s*(\d+)\s*\)\s*(.*)$")


def _spelled(substitution):
    """The substitution's characters with any spaces allowed between them, then what may follow it."""
    letters = [re.escape(ch) for ch in substitution if not ch.isspace()]
    return re.compile(r"\s*".join(letters) + r"(?=\s*$|[.,;]|\s+[A-Za-z(])")


# Longest first, so that a substitution that begins another (y=x and y=x+y, x=0 and x=0, y=0) is tried last.
_LONGEST_FIRST = [(s, _spelled(s)) for s in sorted(SUBSTITUTIONS, key=lambda s: -len(s.replace(" ", "")))]


def read_move(answer_text):
    """(identity number, substitution) from the last line that starts with `MOVE:`, or None."""
    lines = (answer_text or "").translate(_PLAIN).splitlines()
    found = [match.group(1) for match in map(_MOVE_LINE.match, lines) if match]
    if not found:
        return None
    numbered = _NUMBERED.match(found[-1])
    if not numbered:
        return None
    for substitution, spelled in _LONGEST_FIRST:
        if spelled.match(numbered.group(2)):
            return int(numbered.group(1)), substitution
    return None


def option_of(problem, move):
    """The position of the option of `problem` (a problem record) that `move` belongs to, or None if the move
    is not available (its result is empty or already on the page, or the identity number is not on the page)."""
    number, substitution = move
    for position, option in enumerate(problem["options"]):
        if [number, substitution] in option["moves"]:
            return position
    return None
