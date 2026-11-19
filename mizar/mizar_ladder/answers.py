"""Reads the model's option from its answer text.

The last line that starts with `FACT:` counts (the label in any letter case), so a model that changes its mind is
read at its final answer, and a `FACT:` inside a later sentence of prose is not taken for an answer. The rest of
that line must be a whole number from 1 to 30; backticks, asterisks and a closing full stop are ignored. Anything
else on the line (a word for a number, a reason after the number) makes the answer unreadable.
"""
import re

from mizar_ladder.problems import OPTIONS

_FACT_LINE = re.compile(r"^\s*FACT\s*:(.*)$", re.IGNORECASE)


def read_option(answer_text):
    """The option number on the last line that starts with `FACT:`, or None."""
    lines = (answer_text or "").replace("`", " ").replace("*", " ").splitlines()
    found = [match.group(1) for match in map(_FACT_LINE.match, lines) if match]
    if not found:
        return None
    rest = found[-1].strip()
    rest = rest[:-1].strip() if rest.endswith(".") else rest
    if not re.fullmatch(r"[0-9]+", rest):
        return None
    number = int(rest)
    return number if 1 <= number <= OPTIONS else None
