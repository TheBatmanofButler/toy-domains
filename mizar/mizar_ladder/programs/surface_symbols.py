"""Surface, symbols: the option sharing the most symbols with the theorem, rare symbols counting more.

For each option, the sum over the symbols it shares with the theorem of log(facts in the library / facts
containing the symbol), counted as in programs/common.py. The pick is the option with the highest sum, ties
sharing the weight. Nothing is trained.
"""
from mizar_ladder.programs.common import option_names, pick_best


def picks(problems, counts):
    return [pick_best([counts.shared_sum(name, [p["theorem"]], own=p["theorem"]) for name in option_names(p)])
            for p in problems]
