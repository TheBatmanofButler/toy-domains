"""Builds the test set and the training set of cube states, each with its distance and right turns.

Random cubes are drawn and solved by the perfect solver. A cube at one of the far distances (17, 18) can
fill a place there as it is; otherwise it fills a place nearer solved by following its shortest solution
home to that distance. Places are filled in a rotating order, so every distance fills at the same rate.
Each random cube supplies at most one state, in one set. No state appears twice, within a set or across
the two. Any check that fails stops the build.
"""
import json
from dataclasses import dataclass

from cube_ladder.cube import apply_turns, is_valid, random_cube

FOLLOW_HOME_DISTANCES = tuple(range(2, 17))   # distance 1 is not used: only 18 cubes are there
AS_DRAWN_DISTANCES = (17, 18)


class BuildError(Exception):
    pass


def solved_random_cubes(solver, draw_cube, rng, batch_size):
    """An endless stream of (cube, distance, shortest solution). Cubes are drawn one at a time but sent
    to the solver in batches, because each solver run has a fixed start-up cost. The stream's order does
    not depend on the batch size."""
    while True:
        cubes = [draw_cube(rng) for _ in range(batch_size)]
        for cube, (distance, solution) in zip(cubes, solver.distances(cubes)):
            yield cube, distance, solution


@dataclass(frozen=True)
class Rules:
    """Where states come from: distances filled by following cubes home, distances filled by cubes as
    drawn, how many cubes in a row may offer nothing new before a distance closes, and whether a repeated
    draw is allowed (only in tests that draw short scrambles, where repeats are expected)."""
    follow_home: tuple = FOLLOW_HOME_DISTANCES
    as_drawn: tuple = AS_DRAWN_DISTANCES
    give_up_after: int = 2000
    allow_repeated_draws: bool = False

    @property
    def distances(self):
        return tuple(self.follow_home) + tuple(self.as_drawn)


def _state_for(source, source_distance, solution, distance, rules):
    """The state this random cube offers at `distance`, or None: the cube itself at a far distance it is at,
    or the state its shortest solution passes through at a nearer one."""
    if distance in rules.as_drawn:
        return source if source_distance == distance else None
    if distance > source_distance:
        return None
    return apply_turns(source, solution[:source_distance - distance])


class _Places:
    """The open places of one set, and how many cubes in a row have offered nothing new for each distance."""

    def __init__(self, per_distance, rules):
        self.rules = rules
        self.open = {d: per_distance for d in rules.distances}
        self.misses_in_a_row = {d: 0 for d in rules.distances}
        self.pointer = 0   # where the rotation over the follow-home distances starts next time

    def any_open(self):
        return any(self.open.values())

    def offers(self, source, source_distance, solution, taken, repeated):
        """{distance: new state} for every open distance this cube can fill. A distance that gets nothing
        counts a miss, and closes after `give_up_after` misses in a row. A repeated draw offers nothing."""
        offers = {}
        for distance, places in self.open.items():
            if places == 0:
                continue
            state = None if repeated else _state_for(source, source_distance, solution, distance, self.rules)
            if state is None or state in taken:
                self.misses_in_a_row[distance] += 1
                if self.misses_in_a_row[distance] >= self.rules.give_up_after:
                    self.open[distance] = 0   # closed short; the caller reports it
            else:
                self.misses_in_a_row[distance] = 0
                offers[distance] = state
        return offers

    def choose(self, source_distance, offers):
        """Which offered distance the cube fills: its own distance if that is a far one it can fill as
        drawn; otherwise the next follow-home distance in the rotation. None if it can fill nothing."""
        if source_distance in self.rules.as_drawn and source_distance in offers:
            return source_distance
        rotation = list(self.rules.follow_home)
        for step in range(len(rotation)):
            distance = rotation[(self.pointer + step) % len(rotation)]
            if distance in offers:
                self.pointer = (self.pointer + step + 1) % len(rotation)
                return distance
        return None


def choose_states(stream, per_distance, rules, used_sources, forbidden):
    """Fill `per_distance` places at each distance from the stream, with states all different and none in
    `forbidden` (the test set, when building the training set). Returns (states, unused cubes, distances
    closed before they were full). A uniformly random cube drawn twice means the drawing is broken."""
    places = _Places(per_distance, rules)
    states, unused, taken = [], 0, set(forbidden)
    while places.any_open():
        source, source_distance, solution = next(stream)
        repeated = source in used_sources
        if repeated and not rules.allow_repeated_draws:
            raise BuildError(f"random cube {source} was drawn twice")
        offers = places.offers(source, source_distance, solution, taken, repeated)
        place = places.choose(source_distance, offers)
        if place is None:
            unused += 1
            continue
        used_sources.add(source)
        taken.add(offers[place])
        places.open[place] -= 1
        states.append({"cube": offers[place], "distance": place, "source_cube": source,
                       "source_distance": source_distance})
    counts = count_by_distance(states, rules.distances)
    return states, unused, sorted(d for d in rules.distances if counts[d] < per_distance)


def label_states(states, set_name, solver, seed):
    """Give each state its id, check its distance, and find its right turns."""
    followed = [s for s in states if s["cube"] != s["source_cube"]]
    measured = solver.distances([s["cube"] for s in followed])
    for state, (distance, _) in zip(followed, measured):
        if distance != state["distance"]:
            raise BuildError(f"state {state['cube']} from {state['source_cube']}: measured distance "
                             f"{distance}, intended {state['distance']}")
    right = solver.right_turns_many([s["cube"] for s in states], [s["distance"] for s in states])
    numbers = {}
    labelled = []
    for state, right_turns in zip(states, right):
        number = numbers[state["distance"]] = numbers.get(state["distance"], 0) + 1
        state_id = f"{set_name}-{state['distance']:02d}-{number:04d}"
        if not is_valid(state["cube"]):
            raise BuildError(f"{state_id}: {state['cube']} is not a valid cube")
        if not right_turns:
            raise BuildError(f"{state_id}: no right turn")
        labelled.append({"id": state_id, "cube": state["cube"], "distance": state["distance"],
                         "right_turns": right_turns, "source_cube": state["source_cube"],
                         "source_distance": state["source_distance"], "seed": seed})
    return labelled


def count_by_distance(states, distances):
    return {d: sum(s["distance"] == d for s in states) for d in distances}


def build_states(solver, seed, rng, test_per_distance=100, train_per_distance=1000, rules=Rules(),
                 draw_cube=random_cube, batch_size=500):
    """Returns (test states, training states, summary). The test set is filled first, from the first
    random cubes; the training set from the cubes after. `rng` is a random.Random seeded with `seed`."""
    distances = rules.distances
    stream = solved_random_cubes(solver, draw_cube, rng, batch_size)
    used_sources = set()
    test, test_unused, _ = choose_states(stream, test_per_distance, rules, used_sources, set())
    for distance, count in count_by_distance(test, distances).items():
        if count != test_per_distance:
            raise BuildError(f"test set has {count} states at distance {distance}, not {test_per_distance}")
    test_cubes = {s["cube"] for s in test}
    train, train_unused, train_short = choose_states(stream, train_per_distance, rules, used_sources, test_cubes)
    for distance, count in count_by_distance(train, distances).items():
        if count > train_per_distance:
            raise BuildError(f"training set has {count} states at distance {distance}, more than {train_per_distance}")
    test = label_states(test, "test", solver, seed)
    train = label_states(train, "train", solver, seed)
    for name, chosen in (("test", test), ("training", train)):
        if len({s["cube"] for s in chosen}) != len(chosen):
            raise BuildError(f"the same cube is twice in the {name} set")
    if test_cubes & {s["cube"] for s in train}:
        raise BuildError("a cube is in both the test set and the training set")
    sources = [s["source_cube"] for s in test + train]
    if len(set(sources)) != len(sources):
        raise BuildError("a random cube supplied two states")
    summary = {"seed": seed, "random_cubes_used": len(used_sources),
               "random_cubes_not_used": test_unused + train_unused,
               "training_count_by_distance": count_by_distance(train, distances),
               "training_distances_left_short": train_short,
               "solver_seconds": solver.seconds}
    return test, train, summary


def write_jsonl(path, records):
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]
