"""The one function that decides which bin of the plan's table a file ends in, from what was found about it.

The order of the rules matters and is the specification's: a file is left out before any call is looked at;
then the unaided call decides alone if it proved the goal or did not decide; then a file whose axiom set has no
usable list of facts stops; only then are the options looked at.
"""
from tptp_count.prover import DECIDING, NOTHING_LEFT, PROVED
from tptp_count.tptp_file import is_theorem

NOT_USABLE = "left out: not usable"
STATUS = "left out: status"
DUPLICATE = "left out: duplicate"
TOO_FEW = "left out: too few facts"
PROVED_UNAIDED = "proved unaided"
NO_FACT_HELPS = "no single fact helps"
A_PROBLEM = "a problem"
STOPPED = "stopped for another reason"
BINS = (NOT_USABLE, STATUS, DUPLICATE, TOO_FEW, PROVED_UNAIDED, NO_FACT_HELPS, A_PROBLEM, STOPPED)
MAIN = (PROVED_UNAIDED, NO_FACT_HELPS, A_PROBLEM)

NOT_FOLLOWING = "the prover says the goal does not follow, TPTP says it does"
NO_FACTS = "no usable list of facts: a deriving run of its axiom set did not finish"
UNSETTLED = "its axioms' facts were not the same in two counts"


class BinError(ValueError):
    pass


def bin_of(usable, status, duplicate_of=None, unaided=None, options=None, option_endings=(), no_facts=None,
           unsettled=False):
    """-> (bin, why). `usable`: True or the reason the file is not usable; `duplicate_of`: the path of an
    earlier file that is the same problem, or None; `unaided`: how the unaided call ended; `options`: the drawn
    options, or None if there were too few facts; `option_endings`: how each option's call ended, in order;
    `no_facts`: None, or why the axiom set has no usable list of facts (a deriving run that did not finish);
    `unsettled`: whether one of the two counts derived a usable list of facts for the axiom set and the other
    none (settle.py), so that nothing derived from it is used. `why` is None for the three main bins."""
    if usable is not True:
        return NOT_USABLE, usable
    if not is_theorem(status):
        return STATUS, f"status {status or 'missing'}"
    if duplicate_of is not None:
        return DUPLICATE, f"same problem as {duplicate_of}"
    if unaided is None:
        raise BinError("a usable theorem file that is not a duplicate needs its unaided call")
    if unaided == PROVED:
        return PROVED_UNAIDED, None
    if unaided not in DECIDING:
        return STOPPED, f"unaided call: {unaided}"
    if unsettled:
        return STOPPED, UNSETTLED
    if no_facts is not None:
        # The reason does not say which deriving run was cut off: a run that sits at the time cap is cut off in one
        # run of the count and finishes in the next, and files.jsonl must be the same. derived_facts.jsonl says.
        return STOPPED, NO_FACTS
    if unaided == NOTHING_LEFT:
        return STOPPED, NOT_FOLLOWING
    # Every other ending has been dealt with above: from here on the unaided call ended on the clause limit.
    if options is None:
        return TOO_FEW, "fewer than 30 derived facts"
    if len(option_endings) != len(options):
        raise BinError(f"{len(options)} options but {len(option_endings)} option calls")
    if PROVED in option_endings:
        return A_PROBLEM, None
    not_deciding = [(number, ending) for number, ending in enumerate(option_endings) if ending not in DECIDING]
    if not not_deciding:
        return NO_FACT_HELPS, None
    number, ending = not_deciding[0]
    return STOPPED, f"option call {number}: {ending}" + (f" and {len(not_deciding) - 1} more" if len(not_deciding) > 1 else "")
