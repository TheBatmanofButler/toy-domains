"""Tests of programs/search.py on hand-made call records, for each of its three cases, and with unsettled calls."""
from mizar_ladder.programs import search
from mizar_ladder.programs.common import pick_on


def calls(problem_id, without, proved=(), unsettled=()):
    """The settled records of one problem; those in `unsettled` (None for the call without an option) are
    unsettled calls whose first run proved the theorem."""
    found = []
    for n in [None] + list(range(1, 31)):
        ending = without if n is None else "proved" if n in proved else "clause limit"
        record = {"problem_id": problem_id, "option": n, "ending": ending, "used": []}
        if n in unsettled:
            record.update(ending="unsettled", endings=["proved", "time cap"])
        found.append(record)
    return found


def test_the_three_cases_and_unsettled_proofs():
    problems = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}]
    records = (calls("a", "clause limit", proved=[3, 7])        # equal weight on the options that proved it
               + calls("b", "nothing left")                     # none proved it: equal weight on all 30
               + calls("c", "proved", proved=[3])               # proved without an option: all 30
               + calls("d", "clause limit", proved=[3, 9], unsettled=[9])          # an unsettled proof is no success
               + calls("e", "proved", proved=[3, 4], unsettled=[None]))            # nor without an option
    assert search.picks(problems, records) == [pick_on([3, 7]), pick_on(range(1, 31)), pick_on(range(1, 31)),
                                               pick_on([3]), pick_on([3, 4])]
