"""Every program gives the same picks when what a solver must not see is taken out of the test problems: the
planted proof, the depth, the right moves, the counts of proofs and sequences, the family and the attempt."""
import pytest
from conftest import record
from small_problems import small_problems

from fe_ladder.identity_text import write_identity
from fe_ladder.programs import guessing, lookahead, lookup, narrow_deep, recall, surface_relaxed, surface_strict

HIDDEN = ("planted", "depth", "right_moves", "proofs", "sequences", "family", "attempt")


@pytest.fixture(scope="module")
def sets():
    made = []
    for n, (equation, goal) in enumerate(small_problems(80, seed=21)):
        r = record(write_identity(equation), write_identity(goal), most_moves=3)
        if r["depth"]:
            made.append(dict(r, planted={"first_chain": ["y=x"], "second_chain": []}, attempt=n, family="cauchy"))
    train = [dict(r, id=f"train-{r['depth']}-{n:04d}") for n, r in enumerate(made[:30])]
    test = [dict(r, id=f"test-{r['depth']}-{n:04d}") for n, r in enumerate(made[30:40])]
    return train, test


def without_hidden(problems):
    return [{k: v for k, v in p.items() if k not in HIDDEN} for p in problems]


def test_every_program_gives_the_same_picks_without_what_it_must_not_see(sets):
    train, test = sets
    bare = without_hidden(test)
    counts = lookup.train(train, test)
    strict = surface_strict.train(train, test)
    relaxed = surface_relaxed.train(train, test)
    for full, stripped in ((guessing.picks(test), guessing.picks(bare)),
                           (recall.picks(test), recall.picks(bare)),
                           (lookup.picks(test, counts), lookup.picks(bare, counts)),
                           (surface_strict.picks(test, strict), surface_strict.picks(bare, strict)),
                           (surface_relaxed.picks(test, relaxed), surface_relaxed.picks(bare, relaxed)),
                           (lookahead.picks(test, 2), lookahead.picks(bare, 2)),
                           (narrow_deep.picks(test, 4), narrow_deep.picks(bare, 4))):
        assert full == stripped
