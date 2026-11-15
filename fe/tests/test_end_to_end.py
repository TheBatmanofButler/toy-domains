"""The whole chain, stage by stage, through files, on a tiny set: problems of depth 2 and 3 built by stage 1
(searched to 3 moves, and checked by the plain search), and a stand-in model scripted per problem to be always
right, always wrong, unreadable, not available, or out of thinking (the server closes the thinking with the
stop sentence and it answers right, in the same reply).

Hand-worked expectations. Each depth 2 and 3 has 5 test problems; problem k at each depth gets the script
k = 1 right, 2 wrong, 3 unreadable, 4 not available (a move on identity (2), which is not on the page), 5 out of
thinking. So at every depth: model score (1 + 0 + 0 + 0 + 1) / 5 = 0.4; unreadable 1/5; not available 1/5;
forced 1/5, all right; unforced 20, of which 5 right (0.25). Thinking tokens: the stand-in thinks 90 tokens,
then the end-of-thinking token and 10 answer tokens (101 in all), or reaches the budget after 8,000 tokens,
when the server's end-of-thinking text adds 19 thinking tokens and the end-of-thinking token, then 4 answer
tokens (8,024 in all). The thinking figure is the model's own, the 8,000 before the end text for a forced
answer: (4 x 90 + 8000) / 5 = 1672, with no answer lacking a count; tokens used (4 x 101 + 8024) / 5 = 1685.6.
Every answer is asked with the same settings and model version, so the report stage goes ahead.
The model gets problems 1 and 5. Lookahead of depth k scores 1 at depths up to k, so room is 0 at 2 and 3, and
lookahead_3 gets every problem: both 2, only the program 3, only the model 0, neither 0, and no "only the model"
problem expected by chance either way.
The run's check is set to look at all 50 answers: 10 are unreadable (0.2, above 0.15), so it stops; the 10
forced answers (enough to compare: at least 10 of each) are all readable (1.0) against 30 of 40 unforced (0.75:
a move that is not available is readable), so that check holds. The budget behaves as assumed: the 10 forced
answers have the end text after exactly 8,000 thinking tokens, and the 40 others end by themselves after 90.
After the decision to carry on, the run is started again with --carry-on and finishes.
Same wrong moves: at each depth only problem 2 has wrong tries (the not-available moves of problem 4 are left
out), all five on the same wrong move, so every figure rests on 1 problem and 5 wrong tries and none has a
standard error. Guessing puts 1/n on every one of the n options of problem 2, so its match and its uniform
figure are both 1/n. lookahead_3 puts all its weight on right moves, so its match and uniform figures are 0.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from stand_in_replies import chat_reply, forced_reply, tokenize
from stand_in_server import StandInServer, goal_in, move_text, right_move_of, wrong_move_of

from fe_ladder.problems import read_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"
KINDS = {1: "right", 2: "wrong", 3: "unreadable", 4: "not_available", 5: "out_of_thinking"}


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def stand_in_for(test_problems):
    by_goal = {p["goal"]: p for p in test_problems}

    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        problem = by_goal[goal_in(request)]
        kind = KINDS[int(problem["id"].split("-")[2])]
        right = move_text(right_move_of(problem))
        if kind == "out_of_thinking":
            return 200, forced_reply(right)
        return 200, chat_reply({"right": right, "wrong": move_text(wrong_move_of(problem)), "unreadable": "Not sure.",
                                "not_available": "MOVE: (2) y=x"}[kind])
    return StandInServer(respond)


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    stage("1_build_problems")(["--data", str(data), "--seed", "5", "--depths", "2,3", "--most-moves", "3",
                               "--test-per-depth", "5", "--train-per-depth", "5", "--workers", "2"])
    stage("2_run_programs")(["--data", str(data)])
    server = stand_in_for(read_jsonl(data / "test_problems.jsonl"))
    settings = data / "settings.json"
    settings.write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    common = ["--data", str(data), "--base-url", server.base_url, "--model-name", "stand-in", "--model-version",
              "stand-in@1", "--settings", str(settings), "--seed", "9", "--workers", "2", "--wait-seconds", "0",
              "--check-after", "50", "--price-per-hour", "1", "--cost-ceiling", "300"]
    with pytest.raises(SystemExit) as check_stop:
        stage("3_model_run")(common)
    stage("3_model_run")(common + ["--carry-on"])
    stage("4_report")(["--data", str(data)])
    server.close()
    return data, str(check_stop.value)


def test_files_are_written(chain):
    data, _ = chain
    for name in ("test_problems.jsonl", "train_problems.jsonl", "build_summary.json", "program_picks.jsonl",
                 "programs_summary.json", "model_run_check.json", "model_answers.jsonl",
                 "scores_by_depth.json", "problem_by_problem.json", "wrong_moves.json", "report.txt", "curve.svg"):
        assert (data / name).exists(), name
    assert len(read_jsonl(data / "model_answers.jsonl")) == 10 * 5
    assert len(read_jsonl(data / "program_picks.jsonl")) == 10 * 9


def test_the_run_checks_itself_and_stops_on_unreadable_answers(chain):
    data, message = chain
    result = json.loads((data / "model_run_check.json").read_text())
    assert message.startswith("STOP") and not result["passed"] and len(result["problems"]) == 1
    assert "0.20 of answers unreadable" in result["problems"][0]
    assert result["answers_checked"] == 50 and result["unreadable_share"] == 0.2 and result["forced_share"] == 0.2
    assert result["forced_readable_share"] == 1 and result["unforced_readable_share"] == 0.75
    equations = [p["equation"] for p in read_jsonl(data / "test_problems.jsonl")]
    assert result["share_with_thinking"] == 1
    assert result["tokens_per_equation"] == sum(len(e.split()) + 10 for e in equations) / len(equations)
    assert result["forced_comparison"] == "tested"
    assert result["forced_answers_compared"] == 10 and result["unforced_answers_compared"] == 40
    assert result["budget_check"] == "as assumed" and result["end_text_outside_budget_count"] == 10
    assert result["budget_misfit_count"] == 0


def test_the_saved_records_name_the_move_and_its_option(chain):
    data, _ = chain
    problems = {p["id"]: p for p in read_jsonl(data / "test_problems.jsonl")}
    for r in read_jsonl(data / "model_answers.jsonl"):
        kind = KINDS[int(r["problem_id"].split("-")[2])]
        assert (r["move"] is None) == (kind == "unreadable")
        assert (r["option"] is None) == (kind in ("unreadable", "not_available"))
        assert r["right"] == (kind in ("right", "out_of_thinking"))
        if kind == "right":
            assert r["option"] == problems[r["problem_id"]]["right_moves"][0]


def test_final_scores_equal_the_hand_worked_table(chain):
    data, _ = chain
    table = json.loads((data / "scores_by_depth.json").read_text())
    tokens_per_equation = json.loads((data / "model_run_check.json").read_text())["tokens_per_equation"]
    assert sorted(table) == ["2", "3"]
    for depth, row in table.items():
        assert row["problems"] == 5
        assert row["model"] == pytest.approx(0.4)
        assert row["unreadable_share"] == 0.2 and row["not_available_share"] == 0.2
        assert row["forced_share"] == 0.2 and row["failed_share"] == 0
        assert (row["forced_answers"], row["forced_share_right"]) == (5, 1.0)
        assert (row["unforced_answers"], row["unforced_share_right"]) == (20, 0.25)
        assert row["thinking_tokens_mean"] == pytest.approx(1672) and row["tokens_used_mean"] == pytest.approx(1685.6)
        # The stand-in gives token ids with every reply, so no answer lacks a thinking count.
        assert row["answers_without_thinking_count"] == 0
        assert row["most_identities_written"] == pytest.approx(1685.6 / tokens_per_equation)
        for k in (1, 2, 3):
            if int(depth) <= k:
                assert row["programs"][f"lookahead_{k}"] == 1
        assert row["room"] == 0
        # Model problem scores are 1, 0, 0, 0, 1: mean .4, squares about it sum to 1.2, variance .3,
        # standard error sqrt(.3 / 5) = sqrt(.06).
        assert row["model_standard_error"] == pytest.approx(0.06 ** 0.5)


def test_final_problem_by_problem_equals_the_hand_worked_table(chain):
    data, _ = chain
    table = json.loads((data / "problem_by_problem.json").read_text())
    for depth in ("2", "3"):
        assert table["lookahead_3"][depth] == {"both": 2, "only_model": 0, "only_program": 3, "neither": 0,
                                               "only_model_expected_by_chance": 0.0,
                                               "only_model_expected_if_independent": 0.0,
                                               "only_model_if_independent_standard_error": 0.0}


def test_same_wrong_moves_equal_the_hand_worked_line(chain):
    data, _ = chain
    table = json.loads((data / "wrong_moves.json").read_text())
    problems = {p["id"]: p for p in read_jsonl(data / "test_problems.jsonl")}
    controls = ["recall", "surface_strict"]
    for depth in ("2", "3"):
        options = len(problems[f"test-{depth}-0002"]["options"])
        row = table["guessing"][depth]
        assert row["problems"] == 1 and row["wrong_tries"] == 5
        assert row["match_rate"] == pytest.approx(1 / options) and row["uniform"] == pytest.approx(1 / options)
        assert row["excess"] == pytest.approx(row["match_rate"] - row["shuffle"])
        assert row["match_rate_standard_error"] is None and row["excess_standard_error"] is None
        assert sorted(row["excess_over_control"]) == controls
        for control in controls:
            assert row["excess_over_control"][control]["mean"] == pytest.approx(
                row["excess"] - table[control][depth]["excess"])
            assert row["excess_over_control"][control]["standard_error"] is None
        assert table["lookahead_3"][depth]["match_rate"] == 0 and table["lookahead_3"][depth]["uniform"] == 0
    assert "Same wrong moves, over the problems" in (data / "report.txt").read_text()
    text = (data / "report.txt").read_text()
    assert "the most identities the model could have written out in its tokens" in text
    assert "does not rank them on equal terms" in text


def test_the_report_stage_run_twice_gives_identical_files(chain):
    data, _ = chain
    names = ("scores_by_depth.json", "problem_by_problem.json", "wrong_moves.json", "report.txt", "curve.svg")
    before = {name: (data / name).read_bytes() for name in names}
    stage("4_report")(["--data", str(data)])
    assert {name: (data / name).read_bytes() for name in names} == before


def test_rerunning_the_model_stage_asks_nothing_new(chain, capsys):
    data, _ = chain
    before = (data / "model_answers.jsonl").read_bytes()
    server = stand_in_for(read_jsonl(data / "test_problems.jsonl"))
    settings = str(data / "settings.json")
    stage("3_model_run")(["--data", str(data), "--base-url", server.base_url, "--model-name", "stand-in",
                          "--model-version", "stand-in@1", "--settings", settings, "--seed", "9", "--check-after", "50",
                          "--price-per-hour", "1", "--cost-ceiling", "300", "--carry-on"])
    server.close()
    assert [path for path, _ in server.requests if path != "/tokenize"] == []
    assert (data / "model_answers.jsonl").read_bytes() == before
    assert "50 answers already saved, 0 to ask" in capsys.readouterr().out
