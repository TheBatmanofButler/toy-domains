"""Reads the model's turn from its answer text. Adapted from the old run's answer reader.

The last line that starts with `MOVE:` counts, so a model that changes its mind is read at its final answer,
and a `MOVE:` inside a later sentence of prose (for example "the format is MOVE: <move>") is not mistaken
for an answer. The turn must be exactly one of the 18 names. Lower-case turn letters are not accepted: in
cube notation `r` is a different move (two layers at once), so reading it as `R` would be a guess. The label
itself may be in any letter case (`MOVE:`, `Move:`, `move:`): it carries no meaning that case could change.
Typographic
primes are read as plain ones, and backticks, asterisks and angle brackets around the turn are ignored.
"""
import re

from cube_ladder.cube import TURNS

_PLAIN = str.maketrans({"’": "'", "‘": "'", "ʹ": "'", "′": "'", "`": " ", "*": " "})
# A line that begins (after spaces) with MOVE in any letter case, a colon, then the turn up to a space or , ; .
_MOVE_LINE = re.compile(r"^\s*MOVE\s*:\s*([^\s,;.]*)", re.IGNORECASE)


def read_turn(answer_text):
    """The turn on the last line that starts with `MOVE:`, or None if there is no such line or its turn is
    not one of the 18."""
    lines = (answer_text or "").translate(_PLAIN).splitlines()
    found = [match.group(1) for match in map(_MOVE_LINE.match, lines) if match]
    if not found:
        return None
    turn = found[-1].strip("<>[]()\"")
    return turn if turn in TURNS else None
