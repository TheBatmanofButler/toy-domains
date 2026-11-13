"""Tests of states.py: a tiny build with the brute-force solver and cubes scrambled by 5 turns."""
import random

import pytest
from conftest import plain_distance

from cube_ladder.cube import SOLVED, TURNS, apply_turn, apply_turns
from cube_ladder.solver import BruteForceSolver
from cube_ladder.states import BuildError, Rules, build_states, read_jsonl, write_jsonl

COUNTS = dict(test_per_distance=4, train_per_distance=12)
RULES = dict(follow_home=(2, 3), as_drawn=(4, 5), give_up_after=300, allow_repeated_draws=True)


def scrambled_5(rng):
    return apply_turns(SOLVED, [rng.choice(TURNS) for _ in range(5)])


@pytest.fixture(scope="module")
def solver():
    return BruteForceSolver()


def build(solver, seed=7, batch_size=16, draw_cube=scrambled_5, **changes):
    """A tiny build; `changes` may alter the counts or the rules."""
    counts = {k: changes.get(k, v) for k, v in COUNTS.items()}
    rules = Rules(**{k: changes.get(k, v) for k, v in RULES.items()})
    return build_states(solver, seed, random.Random(seed), rules=rules, draw_cube=draw_cube, batch_size=batch_size,
                        **counts)


@pytest.fixture(scope="module")
def tiny(solver):
    return build(solver)


def test_counts_are_exact(tiny):
    test, train, summary = tiny
    for distance in (2, 3, 4, 5):
        assert sum(s["distance"] == distance for s in test) == 4
        assert sum(s["distance"] == distance for s in train) == 12
    assert summary["training_distances_left_short"] == []
    assert summary["training_count_by_distance"] == {2: 12, 3: 12, 4: 12, 5: 12}
    assert summary["random_cubes_used"] == 16 + 48


def test_every_right_turn_leads_one_closer_and_no_other_does(tiny, distance_table):
    test, train, _ = tiny
    for state in test + train:
        assert plain_distance(state["cube"], distance_table) == state["distance"]
        for turn in TURNS:
            closer = plain_distance(apply_turn(state["cube"], turn), distance_table) == state["distance"] - 1
            assert closer == (turn in state["right_turns"])


def test_no_state_repeats_within_or_across_sets_and_no_cube_used_twice(tiny):
    test, train, _ = tiny
    assert len({s["cube"] for s in test}) == len(test) and len({s["cube"] for s in train}) == len(train)
    assert not {s["cube"] for s in test} & {s["cube"] for s in train}
    sources = [s["source_cube"] for s in test + train]
    assert len(sources) == len(set(sources))


def test_states_lie_on_their_cube_s_way_home(tiny, solver):
    test, train, _ = tiny
    for state in test + train:
        assert state["source_distance"] >= state["distance"]
        (distance, _), = solver.distances([state["source_cube"]])
        assert distance == state["source_distance"]
        if state["distance"] in (4, 5) and state["source_distance"] == state["distance"]:
            assert state["cube"] == state["source_cube"]


def test_ids_and_seed_are_recorded(tiny):
    test, train, _ = tiny
    assert test[0]["id"].startswith("test-") and train[0]["id"].startswith("train-")
    assert {s["id"] for s in test} >= {"test-02-0001", "test-05-0004"}
    assert len({s["id"] for s in test + train}) == len(test + train)
    assert {s["seed"] for s in test + train} == {7}


def test_same_seed_gives_the_same_files(tiny, solver, tmp_path):
    again = build(solver, batch_size=5)   # a different batch size must not matter
    for name, first, second in (("test", tiny[0], again[0]), ("train", tiny[1], again[1])):
        write_jsonl(tmp_path / f"{name}_1.jsonl", first)
        write_jsonl(tmp_path / f"{name}_2.jsonl", second)
        assert (tmp_path / f"{name}_1.jsonl").read_bytes() == (tmp_path / f"{name}_2.jsonl").read_bytes()
        assert read_jsonl(tmp_path / f"{name}_1.jsonl") == first
    assert build(solver, seed=8)[0] != tiny[0]


def test_distances_rotate_as_they_fill(solver):
    test, _, _ = build(solver, test_per_distance=3, train_per_distance=1)
    followed = [s["distance"] for s in test if s["distance"] in (2, 3)]
    assert followed[:4] == [2, 3, 2, 3]


def test_a_distance_with_too_few_cubes_ends_with_a_smaller_training_set(solver):
    # Only 243 cubes are 2 turns from solved, and 10 of them are test states: 300 training places there
    # cannot be filled, so distance 2 closes after 150 cubes in a row offer nothing new, and says so.
    test, train, summary = build(solver, test_per_distance=10, train_per_distance=300, give_up_after=150)
    at_2 = [s["cube"] for s in train if s["distance"] == 2]
    assert summary["training_distances_left_short"] == [2]
    assert summary["training_count_by_distance"][2] == len(at_2) <= 243 - 10
    assert len(set(at_2)) == len(at_2)
    assert all(summary["training_count_by_distance"][d] == 300 for d in (3, 4, 5))


def test_unfillable_test_set_stops_the_build(solver):
    with pytest.raises(BuildError, match="test set has 0 states at distance 6"):
        build(solver, as_drawn=(6,), give_up_after=50)


def test_repeated_random_cube_stops_a_real_build(solver):
    two_cubes = [apply_turns(SOLVED, "R U F L D"), apply_turns(SOLVED, "F R U B L")]
    with pytest.raises(BuildError, match="drawn twice"):
        build(solver, draw_cube=lambda rng: rng.choice(two_cubes), allow_repeated_draws=False)


class LyingSolver(BruteForceSolver):
    def __init__(self, lie):
        super().__init__()
        self.lie = lie

    def distances(self, cubes):
        found = super().distances(cubes)
        if self.lie == "distance" and len(cubes) != 16:   # drawing asks in batches of 16; measuring otherwise
            return [(d + 1, s) for d, s in found]
        return found

    def right_turns_many(self, cubes, distances):
        found = super().right_turns_many(cubes, distances)
        return [[]] + found[1:] if self.lie == "no right turn" else found


@pytest.mark.parametrize("lie, message", [("distance", "measured distance"), ("no right turn", "no right turn")])
def test_a_wrong_label_stops_the_build(lie, message):
    with pytest.raises(BuildError, match=message):
        build(LyingSolver(lie))


def test_an_invalid_state_stops_the_build():
    class AnySolver:
        seconds = 0.0

        def distances(self, cubes):
            return [(4, ["R"] * 4) for _ in cubes]

        def right_turns_many(self, cubes, distances):
            return [["R"] for _ in cubes]

    broken = "R" + SOLVED[1:9] + "U" + SOLVED[10:]   # two stickers swapped: not a real cube
    with pytest.raises(BuildError, match="not a valid cube"):
        build_states(AnySolver(), 1, random.Random(1), 1, 1,
                     Rules(follow_home=(), as_drawn=(4,), give_up_after=5, allow_repeated_draws=True),
                     draw_cube=lambda rng: broken, batch_size=1)


@pytest.mark.parametrize("copied, message", [(("cube", "distance"), "both the test set and the training set"),
                                             (("source_cube",), "supplied two states")])
def test_last_checks_catch_a_state_or_cube_used_twice(solver, monkeypatch, copied, message):
    # choose_states never lets this happen; the last checks are there in case it is ever changed. Here the
    # first training state is made to copy fields of the first test state.
    from cube_ladder import states as module
    original = module.choose_states
    chosen_sets = []

    def copying_choose_states(*args):
        chosen, unused, unfilled = original(*args)
        if chosen_sets:   # the second call chooses the training set
            chosen[0] = {**chosen[0], **{field: chosen_sets[0][0][field] for field in copied}}
        chosen_sets.append(chosen)
        return chosen, unused, unfilled
    monkeypatch.setattr(module, "choose_states", copying_choose_states)
    with pytest.raises(BuildError, match=message):
        build(solver)


@pytest.mark.parametrize("change, message", [("too many", "more than 12"), ("twice", "twice in the training set")])
def test_last_checks_catch_too_many_or_repeated_training_states(solver, monkeypatch, change, message):
    # Again guards that choose_states never trips: an extra training state, or one that repeats another.
    from cube_ladder import states as module
    original = module.choose_states
    calls = []

    def changed_choose_states(*args):
        chosen, unused, short = original(*args)
        calls.append(1)
        if len(calls) == 2:
            first = chosen[0]
            same = [s for s in chosen if s["distance"] == first["distance"]]
            extra = {**first, "source_cube": "extra"} if change == "too many" else {**same[1], "cube": first["cube"],
                                                                                     "distance": first["distance"]}
            chosen = chosen + [extra] if change == "too many" else [extra if s is same[1] else s for s in chosen]
        return chosen, unused, short
    monkeypatch.setattr(module, "choose_states", changed_choose_states)
    with pytest.raises(BuildError, match=message):
        build(solver)
