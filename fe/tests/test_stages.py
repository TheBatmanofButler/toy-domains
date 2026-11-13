"""Tests of the stage scripts' own work: stage 1's checks, summary and printout on a tiny trial; stage 2's
checks, its guard against leaks, the order of its printout, and its figures for lookup and recall on a set
worked out by hand; stage 3 with two model servers and too few forced answers to compare.

The hand-made set for stage 2 (right moves found by the search, and easy to see by hand). Training:
  f(x + y) = f(x) + f(y) with goal f(2x) = 2f(x): y=x;   with goal f(0) = 0: x=0, y=0 and y=0 and x=0 (one option);
  the same with + 2xy and goal f(2x) = 2f(x) + 2x^2: y=x;   with + 3 and goal f(2x) = 2f(x) + 3: y=x;
  with - 2 and goal f(0) = 2: x=0, y=0 and y=0 and x=0.
So lookup counts y=x 3 times and x=0, y=0, y=0 and x=0 twice each, and picks y=x wherever it is available.
Test, on f(x + y) = f(x) + f(y): goal f(3x) = 3f(x) (depth 3, right moves y=x and y=x+y, options 1 and 5 of 9)
and goal f(x + 1) = f(x) + f(1) (depth 1, right move y=1 = x=1, option 3 of 9). Lookup scores 1 and 0; recall
(always the first option, f(0) = 0) scores 0 and 0; guessing 2/9 and 1/9.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from conftest import read_fixture, record
from stand_in_replies import chat_reply, tokenize
from stand_in_server import make_problems, move_text, right_move_of, stand_in  # noqa: F401

from fe_ladder.problems import read_jsonl, write_jsonl
from fe_ladder.programs import lookahead

STAGES = Path(__file__).resolve().parent.parent / "stages"
CAUCHY = "f(x + y) = f(x) + f(y)"
TRAIN = [(CAUCHY, "f(2x) = 2f(x)"), (CAUCHY, "f(0) = 0"), ("f(x + y) = f(x) + f(y) + 2xy", "f(2x) = 2f(x) + 2x^2"),
         ("f(x + y) = f(x) + f(y) + 3", "f(2x) = 2f(x) + 3"), ("f(x + y) = f(x) + f(y) - 2", "f(0) = 2")]
TEST = [(CAUCHY, "f(3x) = 3f(x)"), (CAUCHY, "f(x + 1) = f(x) + f(1)")]


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hand_made_files(folder):
    train = [dict(record(e, g, f"train-1-{n + 1:04d}"), seed=1) for n, (e, g) in enumerate(TRAIN)]
    test = [dict(record(e, g), seed=1) for e, g in TEST]
    for n, p in enumerate(test):
        p["id"] = f"test-{p['depth']}-{n + 1:04d}"
    write_jsonl(folder / "test_problems.jsonl", test)
    write_jsonl(folder / "train_problems.jsonl", train)
    return test, train


def test_the_hand_made_right_moves_are_right(tmp_path):
    test, train = hand_made_files(tmp_path)
    assert [(p["depth"], p["right_moves"]) for p in train] == [(1, [1]), (1, [0]), (1, [1]), (1, [1]), (1, [0])]
    assert [(p["depth"], p["right_moves"], len(p["options"])) for p in test] == [(3, [1, 5], 9), (1, [3], 9)]


@pytest.fixture(scope="module")
def stage_2_on_hand_made_set(tmp_path_factory):
    folder = tmp_path_factory.mktemp("hand")
    hand_made_files(folder)
    stage("2_run_programs").main(["--data", str(folder)])
    return (json.loads((folder / "programs_summary.json").read_text())["scores_by_depth"],
            read_jsonl(folder / "program_picks.jsonl"))


def test_lookup_recall_and_guessing_on_the_hand_made_set(stage_2_on_hand_made_set):
    rows, _ = stage_2_on_hand_made_set
    scores = {int(d): row["programs"] for d, row in rows.items()}
    assert {d: s["lookup"] for d, s in scores.items()} == {1: 0, 3: 1}
    assert {d: s["recall"] for d, s in scores.items()} == {1: 0, 3: 0}
    assert {d: s["guessing"] for d, s in scores.items()} == pytest.approx({1: 1 / 9, 3: 2 / 9})
    assert all(s[f"lookahead_{k}"] == 1 for d, s in scores.items() for k in (1, 2, 3) if d <= k)


def test_stage_2_records_each_search_program_s_budget(stage_2_on_hand_made_set):
    rows, picks = stage_2_on_hand_made_set
    searchers = {p["program"] for p in picks if "sequences_examined" in p}
    assert searchers == {"lookahead_1", "lookahead_2", "lookahead_3"}
    assert set(rows["3"]["sequences_examined_mean"]) == searchers
    # Narrow-and-deep's budget is the identities it worked out, under that name.
    assert {p["program"] for p in picks if "identities_worked_out" in p} == {"narrow_deep"}
    assert set(rows["3"]["identities_worked_out_mean"]) == {"narrow_deep"}
    # f(3x) = 3f(x): lookahead_3 examines 9 + 119 + 2117 sequences (see test_lookahead.py).
    assert next(p for p in picks if p["program"] == "lookahead_3" and p["problem_id"] == "test-3-0001")[
        "sequences_examined"] == 9 + 119 + 2117


def test_a_test_problem_planted_in_training_after_loading_is_refused(tmp_path):
    test, train = hand_made_files(tmp_path)
    leaked = train + [{**test[0], "id": "train-3-0099"}]   # a test problem, renamed as a training problem
    with pytest.raises(ValueError, match="same problem as a test problem"):
        stage("2_run_programs").run_programs(test, leaked, 1)


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_stage_2_stops_when_lookahead_misses_at_any_depth(tmp_path, monkeypatch, capsys, depth):
    hand_made_files(tmp_path)
    honest = lookahead.search

    def broken(problem, searched_depth):
        pick, examined = honest(problem, searched_depth)
        return (pick[::-1] if searched_depth == depth else pick), examined   # wrong moves at one depth only
    monkeypatch.setattr(lookahead, "search", broken)
    with pytest.raises(SystemExit, match="checks on the programs failed"):
        stage("2_run_programs").main(["--data", str(tmp_path)])
    printed = capsys.readouterr().out
    assert printed.startswith("STOP: checks on the programs failed")
    assert f"lookahead_{depth} scores" in printed.split("\n\n")[0]   # the failure comes before the table


def test_stage_2_checks_guessing():
    rows = {2: {"programs": {"guessing": 0.2, "lookahead_1": 0.3, "lookahead_2": 1, "lookahead_3": 1}}}
    problems = stage("2_run_programs").failed_checks([{"depth": 2, "right_moves": [0], "options": [{}] * 4}], rows)
    assert problems == ["depth 2: guessing scores 0.2, average share of right moves is 0.25"]


def test_stage_2_refuses_problems_from_two_builds(tmp_path):
    test, train = hand_made_files(tmp_path)
    write_jsonl(tmp_path / "train_problems.jsonl", [dict(p, seed=2) for p in train])
    with pytest.raises(SystemExit, match="more than one build seed"):
        stage("2_run_programs").main(["--data", str(tmp_path)])


def test_stage_1_summary_by_depth():
    planted = {"first_chain": ["y=x", "y=0"], "second_chain": ["x=1"]}
    problems = [{"depth": 2, "right_moves": [0], "options": [{}] * 10, "planted": planted},
                {"depth": 2, "right_moves": [0, 3], "options": [{}] * 5, "planted": planted},
                {"depth": 3, "right_moves": [1], "options": [{}] * 4, "planted": planted}]
    assert stage("1_build_problems").depth_summary(problems) == {
        2: {"problems": 2, "mean_right_moves": 1.5, "mean_options": 7.5, "mean_share_right": (0.1 + 0.4) / 2,
            "share_shorter_than_planted": 1.0},
        3: {"problems": 1, "mean_right_moves": 1.0, "mean_options": 4.0, "mean_share_right": 0.25,
            "share_shorter_than_planted": 0.0}}


def test_stage_1_writes_and_prints_its_summary(tmp_path, capsys):
    stage("1_build_problems").main(["--data", str(tmp_path), "--seed", "3", "--depths", "2,3", "--most-moves", "3",
                                    "--test-per-depth", "2", "--train-per-depth", "3", "--workers", "2"])
    summary = json.loads((tmp_path / "build_summary.json").read_text())
    assert summary["seed"] == 3 and summary["training_count_by_depth"] == {"2": 3, "3": 3}
    assert summary["test_count_by_depth"] == {"2": 2, "3": 2} and summary["training_depths_left_short"] == []
    assert sum(summary["count_by_kind"].values()) == summary["attempts"]
    assert {d: row["problems"] for d, row in summary["test_by_depth"].items()} == {"2": 2, "3": 2}
    printed = capsys.readouterr().out
    assert "the plain search agrees on 4 test problems of depth 2 and 3" in printed
    assert "wrote 4 test problems and 6 training problems" in printed
    assert "training problems per depth: {2: 3, 3: 3}" in printed
    assert "depth 2: 2 test problems" in printed
    assert len(read_jsonl(tmp_path / "test_problems.jsonl")) == 4


def test_stage_1_stops_on_a_failed_build(tmp_path):
    with pytest.raises(SystemExit, match="STOP: the test set has"):
        stage("1_build_problems").main(["--data", str(tmp_path), "--seed", "3", "--depths", "2,3", "--most-moves",
                                        "3", "--test-per-depth", "2", "--most-attempts", "3"])


def test_stage_1_refuses_the_real_build_without_the_earlier_problems(tmp_path):
    module = stage("1_build_problems")
    with pytest.raises(SystemExit, match="--earlier-problems"):
        module.main(["--data", str(tmp_path), "--seed", "1"])
    assert module.depth_list("2,3") == (2, 3)


def test_stage_1_checks_the_earlier_problems_and_the_plain_search(tmp_path, capsys):
    module = stage("1_build_problems")
    earlier = [p for p in read_fixture("earlier_problems.jsonl") if p["depth"] == 3][:3]
    write_jsonl(tmp_path / "earlier.jsonl", earlier)
    assert module.check_earlier_problems(tmp_path / "earlier.jsonl") is None
    assert "reproduces the earlier run on all 3 earlier problems" in capsys.readouterr().out
    write_jsonl(tmp_path / "earlier.jsonl", [dict(earlier[0], proofs=earlier[0]["proofs"] + 1)])
    assert module.check_earlier_problems(tmp_path / "earlier.jsonl").startswith(f"earlier problem {earlier[0]['id']}")
    with pytest.raises(SystemExit, match="STOP: earlier problem"):
        module.main(["--data", str(tmp_path), "--seed", "1", "--earlier-problems", str(tmp_path / "earlier.jsonl")])
    small = [dict(record(CAUCHY, "f(2x) = 2f(x) + f(0)"), id="test-2-0001")]
    assert small[0]["depth"] == 2 and module.check_plain_search(small, 5) is None
    assert module.check_plain_search([dict(small[0], right_moves=[0])], 5).startswith("test-2-0001")


def test_stage_3_with_two_servers_and_too_few_forced_answers(tmp_path, stand_in, capsys):
    problems, _ = make_problems(["right"] * 4)
    write_jsonl(tmp_path / "test_problems.jsonl", problems)
    (tmp_path / "settings.json").write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))

    def respond(path, request):
        return tokenize(request) if path == "/tokenize" else (200, chat_reply(move_text(right_move_of(problems[0]))))
    servers = [stand_in(respond), stand_in(respond)]
    stage("3_model_run").main(["--data", str(tmp_path), "--base-url", servers[0].base_url, "--base-url",
                               servers[1].base_url, "--model-name", "m", "--model-version", "m@1", "--settings",
                               str(tmp_path / "settings.json"), "--seed", "1", "--workers", "2", "--check-after", "12",
                               "--price-per-hour", "1", "--cost-ceiling", "300", "--wait-seconds", "0"])
    result = json.loads((tmp_path / "model_run_check.json").read_text())
    assert result["passed"] and result["forced_comparison"] == "not tested" and result["answers_checked"] == 12
    assert result["forced_answers_compared"] == 0 and result["unforced_answers_compared"] == 12
    assert result["servers"] == sorted(s.base_url for s in servers)
    printed = capsys.readouterr().out
    assert "check after 12 answers: the other three checks hold; forced against unforced not tested" in printed
    assert "forced against unforced: not tested (0 forced, 12 unforced answers compared" in printed
    assert ("server's thinking budget: as assumed (0 forced: 0 with the end text after the allowance, 0 with it "
            "inside; 0 that do not fit)") in printed
    assert "20 answers saved of 20" in printed     # the run carried on to the end
    records = [json.loads(line) for line in (tmp_path / "model_answers.jsonl").read_text().splitlines()]
    assert sorted(r["server"] for r in records) == sorted([s.base_url for s in servers] * 10)
