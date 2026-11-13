"""A stand-in for the nxopt program, for tests: it reads cubes in Singmaster notation and prints what nxopt
prints, using the brute-force solver (so only cubes within 5 turns of solved). Like nxopt it prints, for a
solved cube, the turns that MAKE the cube from solved, and it mixes in lines about search progress.
FAKE_NXOPT_MODE=wrong prints wrong turns; =missing leaves out the last cube; =short prints one turn too few."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cube_ladder.cube import SOLVED, inverse_turns  # noqa: E402
from cube_ladder.solver import SINGMASTER_PLACES, BruteForceSolver  # noqa: E402


def from_singmaster(line):
    stickers = list(SOLVED)   # centres never move
    for token, (_, indices) in zip(line.split(), SINGMASTER_PLACES):
        for letter, i in zip(token, indices):
            stickers[i] = letter
    return "".join(stickers)


def main():
    max_depth = int(sys.argv[sys.argv.index("-x") + 1])
    mode = os.environ.get("FAKE_NXOPT_MODE", "")
    lines = [line for line in sys.stdin.read().split("\n") if line.strip()]
    if mode == "missing":
        lines = lines[:-1]
    solver = BruteForceSolver()
    print("This is nxopt23 metric HALF\nLoad nxopth23b.dat ....100 read in 0.1")
    for number, line in enumerate(lines, 1):
        print(f"Finished searching depth 1 pos {number} in 1 probes 1 evals.")
        solution = solver._solution(from_singmaster(line))
        if solution is None or len(solution) > max_depth:
            print(f"Did not solve {number} in probes 6 evals 1 time 1e-06")
            continue
        print(f"Saving solution {number}")
        makes = [t[0] + {"": "1", "2": "2", "'": "3"}[t[1:]] for t in inverse_turns(solution)]
        if mode == "wrong" and makes:   # change the first turn's amount, so the turns make another cube
            makes[0] = makes[0][0] + {"1": "2", "2": "3", "3": "1"}[makes[0][1]]
        length = len(makes)
        if mode == "short" and makes:
            makes = makes[1:]
        print(f"Solved {number} in {length} probes 10 evals 3 time 0.001")
        if length:
            print(" " + " ".join(makes))


if __name__ == "__main__":
    main()
