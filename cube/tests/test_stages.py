"""Tests of the stage scripts' own work: stage 1's summary, and stage 2's checks, its guard against leaks, the
order of its printout, and its figures for lookup and recall on a set worked out by hand.

The hand-made set for stage 2. Training: ten cubes two turns from solved, each made by two turns X Y that do
not commute, so the only shortest solution is Y' X' and the one right turn is Y':
  U R, F R, D R, B R (right turn R'), R U, F U, L U (U'), R F, U F (F'), R B (B').
So lookup counts R' 4 times, U' 3, F' 2, B' 1, and always picks R'.
Test: four cubes two turns from solved, made by
  L R (right turns R' and L', since R and L commute), U' R (R'), R2 U (U'), F D (D'),
so lookup (all its weight on R') scores 1, 1, 0, 0: (1 + 1 + 0 + 0) / 4 = 0.5 at distance 2;
and the 60 old-run states (distances 12 to 16), whose right turns and whose scripted-method solutions in both
versions were saved by the old run. From that saved file: R' is a right turn only in H4p-0036 (distance 13,
of 18 states there) and H1-0194 (16, of 9); the top version's first turn is right only in H1-0052 (13) and
H1-0187 (16); the bottom version's only in H2-0053 and H3-0048 (13) and H3-0191 (16). Distances 12, 14 and 15
have 10, 12 and 11 states and no hit.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from conftest import read_fixture

from cube_ladder.cube import SOLVED, apply_turns
from cube_ladder.programs import lookahead
from cube_ladder.solver import BruteForceSolver
from cube_ladder.states import write_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"
TRAIN = [("U R", "R'"), ("F R", "R'"), ("D R", "R'"), ("B R", "R'"), ("R U", "U'"), ("F U", "U'"), ("L U", "U'"),
         ("R F", "F'"), ("U F", "F'"), ("R B", "B'")]
TEST = [("L R", ["R'", "L'"]), ("U' R", ["R'"]), ("R2 U", ["U'"]), ("F D", ["D'"])]


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hand_made_files(folder, with_old_states=True):
    train = [{"id": f"train-02-{n + 1:04d}", "cube": apply_turns(SOLVED, turns), "distance": 2, "right_turns": [right]}
             for n, (turns, right) in enumerate(TRAIN)]
    test = [{"id": f"test-02-{n + 1:04d}", "cube": apply_turns(SOLVED, turns), "distance": 2, "right_turns": right}
            for n, (turns, right) in enumerate(TEST)]
    if with_old_states:
        for n, old in enumerate(read_fixture("old_run_states.jsonl")):
            test.append({"id": f"test-{old['distance']:02d}-{n + 1:04d}", "old_id": old["id"], "cube": old["cube"],
                         "distance": old["distance"], "right_turns": old["right_turns"]})
    write_jsonl(folder / "test_states.jsonl", test)
    write_jsonl(folder / "train_states.jsonl", train)
    return test, train


def test_the_hand_made_right_turns_are_right():
    solver = BruteForceSolver()
    for turns, right in TRAIN:
        assert solver.right_turns(apply_turns(SOLVED, turns), 2) == [right]
    for turns, right in TEST:
        assert sorted(solver.right_turns(apply_turns(SOLVED, turns), 2)) == sorted(right)


@pytest.fixture(scope="module")
def stage_2_on_hand_made_set(tmp_path_factory):
    folder = tmp_path_factory.mktemp("hand")
    hand_made_files(folder)
    stage("2_run_programs").main(["--data", str(folder), "--lookup-tolerance", "1"])
    return json.loads((folder / "programs_summary.json").read_text())["scores_by_distance"]


def test_lookup_on_the_hand_made_set(stage_2_on_hand_made_set):
    scores = {int(d): row["programs"]["lookup"] for d, row in stage_2_on_hand_made_set.items()}
    assert scores == pytest.approx({2: 0.5, 12: 0, 13: 1 / 18, 14: 0, 15: 0, 16: 1 / 9})


def test_recall_on_the_old_states(stage_2_on_hand_made_set):
    rows = {int(d): row["programs"] for d, row in stage_2_on_hand_made_set.items()}
    assert {d: rows[d]["recall_top"] for d in range(12, 17)} == pytest.approx({12: 0, 13: 1 / 18, 14: 0, 15: 0, 16: 1 / 9})
    assert {d: rows[d]["recall_bottom"] for d in range(12, 17)} == pytest.approx({12: 0, 13: 2 / 18, 14: 0, 15: 0, 16: 1 / 9})


def test_a_test_cube_planted_in_training_after_loading_is_refused(tmp_path):
    test, train = hand_made_files(tmp_path, with_old_states=False)
    leaked = train + [{**test[0], "id": "train-02-0099"}]   # a test cube, renamed as a training state
    with pytest.raises(ValueError, match="test cube"):
        stage("2_run_programs").run_programs(test, leaked)


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_stage_2_stops_when_lookahead_misses_at_any_depth(tmp_path, monkeypatch, capsys, depth):
    hand_made_files(tmp_path, with_old_states=False)
    honest = lookahead.search

    def broken(cube, searched_depth):
        pick, examined = honest(cube, searched_depth)
        return (pick[::-1] if searched_depth == depth else pick), examined   # wrong turns at one depth only
    monkeypatch.setattr(lookahead, "search", broken)
    module = stage("2_run_programs")
    if depth == 1:   # the hand-made test cubes are 2 turns away; depth 1 is checked at distance 1 only
        rows = {1: {"programs": {"guessing": 1 / 18, "lookup": 1 / 18, "lookahead_1": 0.5, "lookahead_2": 1,
                                 "lookahead_3": 1}, "states": 1}}
        problems = module.failed_checks([{"distance": 1, "right_turns": ["R"]}], rows, 1)
        assert problems == ["distance 1: lookahead_1 scores 0.5, not 1"]
        return
    with pytest.raises(SystemExit, match="checks on the programs failed"):
        module.main(["--data", str(tmp_path), "--lookup-tolerance", "1"])
    printed = capsys.readouterr().out
    assert printed.startswith("STOP: checks on the programs failed")
    assert f"lookahead_{depth} scores" in printed.split("\n\n")[0]   # the failure comes before the table


def test_stage_2_checks_guessing_and_lookup():
    module = stage("2_run_programs")
    rows = {2: {"programs": {"guessing": 0.2, "lookup": 0.4, "lookahead_1": 0.3, "lookahead_2": 1, "lookahead_3": 1},
                "states": 1}}
    problems = module.failed_checks([{"distance": 2, "right_turns": ["R"]}], rows, 0.05)
    assert problems[0] == "distance 2: guessing scores 0.2, average share of right turns is 0.05555555555555555"
    assert problems[1].startswith("distance 2: lookup (options only) scores 0.400, guessing 0.200")


def test_stage_1_summary_of_right_turns():
    states = [{"distance": 2, "right_turns": ["R"]}, {"distance": 2, "right_turns": ["R", "L"]},
              {"distance": 3, "right_turns": ["U"]}]
    assert stage("1_build_states").right_turn_summary(states) == {
        2: {"states": 2, "mean_right_turns": 1.5, "share_with_one": 0.5},
        3: {"states": 1, "mean_right_turns": 1.0, "share_with_one": 1.0}}


def test_stage_1_writes_and_prints_its_summary(tmp_path, capsys):
    stage("1_build_states").main(["--data", str(tmp_path), "--seed", "3", "--brute-force-scramble", "4",
                                  "--test-per-distance", "2", "--train-per-distance", "5", "--follow-home", "2-3",
                                  "--as-drawn", "4", "--batch-size", "10", "--give-up-after", "200"])
    summary = json.loads((tmp_path / "build_summary.json").read_text())
    assert summary["seed"] == 3 and summary["training_count_by_distance"] == {"2": 5, "3": 5, "4": 5}
    assert summary["training_distances_left_short"] == [] and summary["random_cubes_used"] == 6 + 15
    assert {d: row["states"] for d, row in summary["test_right_turns"].items()} == {"2": 2, "3": 2, "4": 2}
    printed = capsys.readouterr().out
    assert "wrote 6 test states and 15 training states" in printed
    assert "training states per distance: {2: 5, 3: 5, 4: 5}" in printed
    assert "distance  2: 2 test states" in printed


def test_stage_1_refuses_without_solver_or_old_states(tmp_path):
    module = stage("1_build_states")
    with pytest.raises(SystemExit, match="--solver-dir"):
        module.main(["--data", str(tmp_path), "--seed", "1"])
    with pytest.raises(SystemExit, match="--old-states"):
        module.main(["--data", str(tmp_path), "--seed", "1", "--solver-dir", str(tmp_path)])
    assert module.distance_list("2-4") == (2, 3, 4) and module.distance_list("17,18") == (17, 18)
