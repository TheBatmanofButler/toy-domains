"""Distances and right turns, from the perfect solver or, near solved, from trying everything.

`PerfectSolver` runs Rokicki's nxopt (source version f430921a, half-turn metric, 22.8 GB table) as an
outside program; the folder holding the program and its table is passed in. Every solution it returns is
replayed with cube.py and must reach the solved cube in the stated number of turns, or the call fails.
`BruteForceSolver` answers the same questions for cubes within 5 turns of solved. Only tests use it.
"""
import os
import re
import subprocess

from cube_ladder.cube import CORNERS, EDGES, FACES, SOLVED, TURNS, apply_turn, apply_turns, inverse_turns


class SolverError(Exception):
    pass


# nxopt reads one cube per line in Singmaster's notation: 12 edges, then 8 corners, each piece written
# as the letters of its stickers in the order of the faces in its place's name. The places are found
# among cube.py's pieces by the faces their stickers lie on, so no sticker index is typed in twice.
SINGMASTER_NAMES = ("UF", "UR", "UB", "UL", "DF", "DR", "DB", "DL", "FR", "FL", "BR", "BL",
                    "UFR", "URB", "UBL", "ULF", "DRF", "DFL", "DLB", "DBR")


def _singmaster_place(name):
    """The sticker indices of the place called `name`, in the order of the letters of its name."""
    piece = next(p for p in CORNERS + EDGES if {FACES[i // 9] for i in p} == set(name) and len(p) == len(name))
    return tuple(next(i for i in piece if FACES[i // 9] == face) for face in name)


SINGMASTER_PLACES = tuple((name, _singmaster_place(name)) for name in SINGMASTER_NAMES)


def to_singmaster(cube):
    return " ".join("".join(cube[i] for i in stickers) for _, stickers in SINGMASTER_PLACES)


_SOLVED_LINE = re.compile(r"^Solved (\d+) in (\d+) probes \d+ evals \d+ time (\S+)")
_NOT_SOLVED_LINE = re.compile(r"^Did not solve (\d+) in probes \d+ evals \d+ time (\S+)")
_SOLVER_TURN = re.compile(r"^[URFDLB][123]$")


def read_solver_output(text, count):
    """Read nxopt's printout for `count` cubes. Returns, per cube in input order, a dict with `solved`,
    `turns` (as printed) and `seconds`. nxopt numbers its cubes from 1. Lines about search progress
    are skipped. When a cube is solved in L > 0 turns the next line holds the L turns, written as a
    face letter and 1 (clockwise), 2 (half) or 3 (anticlockwise)."""
    results = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        solved, not_solved = _SOLVED_LINE.match(line), _NOT_SOLVED_LINE.match(line)
        if solved:
            number, length = int(solved.group(1)), int(solved.group(2))
            printed = lines[i + 1].split() if length > 0 else []
            if len(printed) != length or not all(_SOLVER_TURN.match(t) for t in printed):
                raise SolverError(f"cube {number}: expected {length} turns after {line!r}, got {lines[i + 1]!r}")
            turns = [t[0] + {"1": "", "2": "2", "3": "'"}[t[1]] for t in printed]
            result = {"solved": True, "turns": turns, "seconds": float(solved.group(3))}
        elif not_solved:
            number = int(not_solved.group(1))
            result = {"solved": False, "turns": None, "seconds": float(not_solved.group(2))}
        else:
            continue
        if number in results:
            raise SolverError(f"cube {number} reported twice")
        results[number] = result
    missing = [n for n in range(1, count + 1) if n not in results]
    if missing or len(results) != count:
        raise SolverError(f"no answer for cubes {missing[:10]} (of {count}); got {len(results)} answers")
    return [results[n] for n in range(1, count + 1)]


def checked_solution(cube, printed_turns, length):
    """nxopt prints a sequence that MAKES the cube from solved; the solution is its inverse. Checks
    that the solution really solves the cube in `length` turns."""
    solution = inverse_turns(printed_turns)
    if len(solution) != length or apply_turns(cube, solution) != SOLVED:
        raise SolverError(f"cube {cube}: solver's turns {' '.join(printed_turns)} do not solve it in {length}")
    return solution


class PerfectSolver:
    def __init__(self, solver_dir, program="nxopt23", threads=1):
        self.program = os.path.join(solver_dir, program)
        self.solver_dir = solver_dir
        self.threads = threads
        self.seconds = 0.0  # total search time nxopt reports, summed over cubes

    def _ask(self, cubes, max_depth):
        """One nxopt run: search each cube up to `max_depth` turns."""
        text = "".join(to_singmaster(cube) + "\n" for cube in cubes)
        command = [self.program, "-t", str(self.threads), "-x", str(max_depth), "-"]
        done = subprocess.run(command, input=text, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              cwd=self.solver_dir, text=True, check=True)
        results = read_solver_output(done.stdout, len(cubes))
        self.seconds += sum(r["seconds"] for r in results)
        return results

    def distances(self, cubes):
        """For each cube, (distance, one shortest solution)."""
        if not cubes:
            return []
        answers = []
        for cube, result in zip(cubes, self._ask(cubes, max_depth=20)):
            if not result["solved"]:
                raise SolverError(f"cube {cube}: not solved within 20 turns")
            length = len(result["turns"])
            answers.append((length, checked_solution(cube, result["turns"], length)))
        return answers

    def right_turns(self, cube, distance):
        return self.right_turns_many([cube], [distance])[0]

    def right_turns_many(self, cubes, distances):
        """For each cube, the turns after which it can be solved in `distance - 1` turns. Cubes are
        grouped by distance so that nxopt (which loads its table each run) runs once per distance."""
        groups = {}
        for n, (cube, distance) in enumerate(zip(cubes, distances)):
            for turn in TURNS:
                groups.setdefault(distance - 1, []).append((n, turn, apply_turn(cube, turn)))
        right = [[] for _ in cubes]
        for depth, asked in sorted(groups.items()):
            for (n, turn, neighbour), result in zip(asked, self._ask([a[2] for a in asked], depth)):
                if not result["solved"]:
                    continue
                if len(result["turns"]) != depth:
                    raise SolverError(f"cube {cubes[n]}: after {turn} it is {len(result['turns'])} from solved, "
                                      f"so its distance is not {depth + 1}")
                checked_solution(neighbour, result["turns"], depth)
                right[n].append(turn)
        return right


class BruteForceSolver:
    """Exact answers for cubes within 5 turns of solved, by trying everything: a table holds a shortest
    solution for every cube within 3 turns, and all sequences of up to 2 turns are tried from the cube."""
    MAX_DISTANCE = 5

    def __init__(self):
        self.seconds = 0.0
        self._near = {SOLVED: []}
        frontier = [SOLVED]
        for _ in range(3):
            next_frontier = []
            for cube in frontier:
                for turn in TURNS:
                    neighbour = apply_turn(cube, turn)
                    if neighbour not in self._near:
                        self._near[neighbour] = inverse_turns([turn]) + self._near[cube]
                        next_frontier.append(neighbour)
            frontier = next_frontier

    def _solution(self, cube):
        """A shortest solution, or None if the cube is more than 5 turns from solved. A cube missing from the
        table is more than 3 turns away; so if nothing reached in s turns is in the table, the cube is more
        than s + 3 away, and the first s at which something is found gives the distance."""
        reached = [(cube, [])]
        for steps in range(3):
            found = [path + self._near[here] for here, path in reached if here in self._near]
            if found:
                return min(found, key=len)
            if steps < 2:
                reached = [(apply_turn(here, turn), path + [turn]) for here, path in reached for turn in TURNS]
        return None

    def distances(self, cubes):
        answers = []
        for cube in cubes:
            solution = self._solution(cube)
            if solution is None:
                raise SolverError(f"cube {cube}: more than {self.MAX_DISTANCE} turns from solved")
            answers.append((len(solution), solution))
        return answers

    def right_turns(self, cube, distance):
        if not 1 <= distance <= self.MAX_DISTANCE:
            raise SolverError(f"cube {cube}: distance {distance} is outside 1 to {self.MAX_DISTANCE}")
        right = []
        for turn in TURNS:
            solution = self._solution(apply_turn(cube, turn))
            if solution is not None and len(solution) < distance - 1:
                raise SolverError(f"cube {cube}: after {turn} it is {len(solution)} from solved, "
                                  f"so its distance is not {distance}")
            if solution is not None and len(solution) == distance - 1:
                right.append(turn)
        return right

    def right_turns_many(self, cubes, distances):
        return [self.right_turns(cube, distance) for cube, distance in zip(cubes, distances)]
