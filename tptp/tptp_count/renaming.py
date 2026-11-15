"""The canonical form of a set of equations (and, if given, a goal) under renaming of symbols and variables.

Two sets get the same canonical form exactly when one becomes the other by such a renaming. The method is the
usual one for this kind of question: give every symbol a colour that any renaming must keep (its arity, where it
occurs), refine the colours until they stop splitting, and where symbols are still tied, try each in turn as
the first and keep the smallest result. A tie between two symbols that can be swapped without changing the set
needs only one of them tried. equations.key and equations.symbol_renaming are built on this.

Why the result does not depend on the names of the symbols. Nothing in the colours or in the writing at a leaf
looks at a name: colours are built from arities, counts and equations written with every symbol shown by its
colour, and a leaf writes each symbol by its colour alone. So if a renaming turns one set into another, it turns
each branch of the search on the first into a branch on the second with the same writing, and the smallest over
all branches is the same. That is why every symbol of the tied cell must be tried, not only the first by name:
two symbols can share a colour without one being able to stand in for the other, and which comes first by name
is not kept by a renaming.

Why the pruning is sound. Let `other` have been tried and `symbol` be in the same cell, and let swapping the two
leave every part the same set: the swap is then a renaming of the structure onto itself. It also leaves the
current colours as they are, since both symbols have the same colour and nothing else moves. By the paragraph
above it turns the branch that tries `other` into the branch that tries `symbol`, writing for writing, so the
smallest writing found under the two is the same and the second branch need not be searched. The test is made
only against symbols already tried, so each skipped branch has a searched twin.
"""
from tptp_count.equations import _labelled, key_up_to_variables, rename_symbols, symbols


class RenamingError(ValueError):
    pass


def _ranks(colours):
    """Replaces each colour by its place among the distinct colours, so colours stay small and comparable."""
    order = {colour: rank for rank, colour in enumerate(sorted(set(colours.values())))}
    return {symbol: order[colour] for symbol, colour in colours.items()}


def _refine(parts, ranks):
    """Splits colours by how each symbol occurs: for every equation it is in, the equation written with this
    symbol marked and every other symbol shown only by its colour. Repeats until nothing splits."""
    while True:
        labels = {symbol: f"c{rank}" for symbol, rank in ranks.items()}
        seen = {symbol: [] for symbol in ranks}
        for tag, equations in parts:
            for equation in equations:
                for symbol in symbols(equation):
                    marked = dict(labels)
                    marked[symbol] = "*"
                    seen[symbol].append((tag, _labelled(equation, marked)))
        refined = _ranks({symbol: (ranks[symbol], tuple(sorted(seen[symbol]))) for symbol in ranks})
        if len(set(refined.values())) == len(set(ranks.values())):
            return refined
        ranks = refined


def _swap_keeps(parts, first, second):
    """Whether swapping two symbols leaves every part of the structure the same set."""
    swap = {first: second, second: first}
    return all({key_up_to_variables(rename_symbols(e, swap)) for e in equations}
               == {key_up_to_variables(e) for e in equations} for _, equations in parts)


def _smallest(parts, ranks):
    """(text, {symbol: label}) of the smallest writing over every way of breaking the remaining ties."""
    cells = {}
    for symbol, rank in ranks.items():
        cells.setdefault(rank, []).append(symbol)
    tied = [rank for rank, cell in cells.items() if len(cell) > 1]
    if not tied:
        labels = {symbol: f"f{rank}" for symbol, rank in ranks.items()}
        text = " | ".join(f"{tag}: " + " ; ".join(sorted(_labelled(e, labels) for e in equations))
                          for tag, equations in parts)
        return text, labels
    best, tried = None, []
    for symbol in sorted(cells[min(tied)]):
        if any(_swap_keeps(parts, symbol, other) for other in tried):
            continue   # its branch gives the same smallest writing as one already tried (see the module's note)
        tried.append(symbol)
        split = _ranks({s: (rank, s != symbol) for s, rank in ranks.items()})
        found = _smallest(parts, _refine(parts, split))
        if best is None or found[0] < best[0]:
            best = found
    return best


def canonical_labels(equations, goal=None):
    """-> (canonical text, {symbol: label}). The equations are read as a set; renamings of one equation's
    variables count as the same equation."""
    unique = {}
    for equation in equations:
        unique.setdefault(key_up_to_variables(equation), equation)
    parts = [("axioms", list(unique.values()))]
    if goal is not None:
        parts.append(("goal", [goal]))
    arities = {}
    for _, part in parts:
        for equation in part:
            for symbol, arity in symbols(equation).items():
                if arities.setdefault(symbol, arity) != arity:
                    raise RenamingError(f"symbol {symbol} is used with arities {arities[symbol]} and {arity}")
    counts = {symbol: [0, 0] for symbol in arities}
    for index, (_, part) in enumerate(parts):
        for equation in part:
            for symbol in symbols(equation):
                counts[symbol][index] += 1
    ranks = _ranks({symbol: (arities[symbol], *counts[symbol]) for symbol in arities})
    return _smallest(parts, _refine(parts, ranks))
