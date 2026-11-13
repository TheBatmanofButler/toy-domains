"""The options of a page: every available move, with moves that give the same result counted as one option.

A move applies one substitution to one numbered identity. It is not available if its result is empty (0 = 0),
is already on the page, or equals the identity it was applied to (which is on the page too). Options come in a
fixed order: by the lowest identity number, then the earliest substitution, among the moves that give each.
"""
from dataclasses import dataclass, field

from fe_ladder.identities import SUBSTITUTIONS, apply


@dataclass
class Option:
    result: tuple                               # the new identity, in the fixed form
    moves: list = field(default_factory=list)   # (identity number, substitution) pairs, first one first


def options(page):
    """`page`: the identities in order; the first is number 1."""
    on_page = set(page)
    by_result = {}
    ordered = []
    for number, identity in enumerate(page, 1):
        for substitution in SUBSTITUTIONS:
            result = apply(identity, substitution)
            if result is None or result in on_page:
                continue
            if result in by_result:
                by_result[result].moves.append((number, substitution))
            else:
                option = by_result[result] = Option(result, [(number, substitution)])
                ordered.append(option)
    return ordered

