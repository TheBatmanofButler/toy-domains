"""Drawing the 30 options of a problem from its axiom set's derived facts: at random, from the seed and the
problem's id, without looking at the goal except to take the goal itself out of the list.
"""
import hashlib
import random

from tptp_count.equations import key_up_to_variables

COUNT = 30


def generator(seed, problem_id):
    """A random generator made from the run's seed and the problem's id, the same on every machine."""
    digest = hashlib.sha256(f"{seed}|{problem_id}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def draw(derived_facts, goal, seed, problem_id):
    """The 30 options in the order drawn, or None ("too few facts") if fewer than 30 facts are left once any
    fact that is the goal up to renaming of variables is removed. `goal` is the goal as a law (variables in
    place of its fresh constants), so that it can be compared with the facts."""
    goal_key = key_up_to_variables(goal)
    left = [fact for fact in derived_facts if key_up_to_variables(fact) != goal_key]
    if len(left) < COUNT:
        return None
    return generator(seed, problem_id).sample(left, COUNT)
