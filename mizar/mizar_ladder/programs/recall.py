"""Recall: the option cited most often in the rest of the library.

The count leaves out the 300 test theorems and the problem's own theorem (programs/common.py).
"""
from mizar_ladder.programs.common import option_names, pick_best


def picks(problems, counts):
    return [pick_best([counts.citations(name, own=p["theorem"]) for name in option_names(p)]) for p in problems]
