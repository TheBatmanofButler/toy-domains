"""The whole chain on the made-up library: stage 1 (seed 7, 2 test and 3 training problems), stage 2 with the
stand-in prover of test_stage_2.py, stage 3 with a stand-in model scripted try by try, and stage 4. Worked out by
hand:

The test problems are t2_xboole_1 (test-0001, holding back option 11) and t4_xboole_1 (test-0002, option 27),
citing 3 and 2 facts, both of the group of sets: every row of the tables holds the same two problems. At the
experiment's limit (4,000) each held-back option proves its theorem and is in the proof, and the option after it (12,
28) proves it without being in the proof. So both problems have right options, the prover's key is the author's
key, and search puts half its weight on the held-back option and half on the one after: .5 on each.
The model's five tries: test-0001 right, right, right, wrong, unreadable; test-0002 out of thinking (forced, and
right), wrong, wrong, right, right. A wrong answer is the option after the right one. So the model scores .6 on
each (3 of 5), .6 in all with a standard error of 0; one answer in ten is unreadable and one forced. It gets both
problems; search (.5, not more than half) gets neither. Model minus search: .1 on each. Guessing: 1/30.
Same wrong answers for search: its weight on the model's wrong options is .5 on each problem (match .5); uniform
.5 / 29; shuffle 0 (the other problem's pick puts nothing on those numbers); excess .5, standard error 0.
Counted together: no program gets either problem (search's half is not more than half), and the model gets both.
Second table: 2 problems, the held-back option right on both, no other right option, 2 calls that proved the
theorem without the option, the model .6 under all three keys, the bins 0 / 2 / 0 / 0.
Lookup: the training problems hold back t10_basic_0, t11_basic_0 and t13_basic_0, once each; all three are
options of both test problems (3, 20 and 23; 8, 10 and 15), none of them right: a third on each, and a score of 0.
The trained readers, recall and surface_symbols are scored from their saved picks; their figures here are checked
to be those of the picks, not worked by hand.
"""
import json
from statistics import mean

import pytest
from stand_in_replies import chat_reply, forced_reply, tokenize
from stand_in_server import stand_in  # noqa: F401
from test_stage_2 import stage, stage_1_data, stage_2, the_prover

from mizar_ladder.model_run import request_seed
from mizar_ladder.problems import read_jsonl
from mizar_ladder.programs.common import pick_on

ALL = "all problems"
SCRIPT = {"test-0001": ["right", "right", "right", "wrong", "unreadable"],
          "test-0002": ["forced", "wrong", "wrong", "right", "right"]}


def the_model(test):
    held = {p["id"]: p["held_back"] for p in test}
    tries = {request_seed(1, problem_id, t): (problem_id, t) for problem_id in SCRIPT for t in range(1, 6)}

    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        problem_id, t = tries[request["seed"]]
        kind, right = SCRIPT[problem_id][t - 1], held[problem_id]
        if kind == "forced":
            return 200, forced_reply(f"FACT: {right}")
        text = {"right": f"FACT: {right}", "wrong": f"FACT: {right % 30 + 1}", "unreadable": "I cannot tell."}[kind]
        return 200, chat_reply(text)
    return respond


def test_the_whole_chain(tmp_path, stand_in_prover, stand_in):  # noqa: F811
    data, checksums = stage_1_data(tmp_path)
    stage_2(data, checksums, the_prover(stand_in_prover, data))
    test = read_jsonl(data / "test_problems.jsonl")
    assert [(p["theorem"], p["held_back"]) for p in test] == [("t2_xboole_1", 11), ("t4_xboole_1", 27)]
    (tmp_path / "settings.json").write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    server = stand_in(the_model(test))
    stage("3_model_run").main(["--data", str(data), "--base-url", server.base_url, "--model-name", "m",
                               "--model-version", "m@1", "--settings", str(tmp_path / "settings.json"), "--seed", "1",
                               "--check-after", "10", "--price-per-hour", "1", "--wait-seconds", "0"])
    assert json.loads((data / "model_run_check.json").read_text())["passed"]
    stage("4_report").main(["--data", str(data)])

    scores = json.loads((data / "scores.json").read_text())
    assert list(scores) == [ALL, "2 to 3 cited", "sets, relations and functions"]
    assert scores[ALL] == scores["2 to 3 cited"] == scores["sets, relations and functions"]
    row = scores[ALL]
    assert row["problems"] == 2 and row["model"] == pytest.approx(0.6) and row["model_standard_error"] == 0
    assert row["unreadable_share"] == pytest.approx(0.1) and row["forced_share"] == pytest.approx(0.1)
    assert row["programs"]["search"] == 0.5 and row["programs"]["guessing"] == pytest.approx(1 / 30)
    assert row["model_minus_program"]["search"] == {"mean": pytest.approx(0.1), "standard_error": pytest.approx(0)}
    picks = read_jsonl(data / "program_picks.jsonl")
    assert [p["weights"] for p in picks if p["program"] == "lookup"] == [pick_on([3, 20, 23]), pick_on([8, 10, 15])]
    assert row["programs"]["lookup"] == 0
    for name in ("recall", "surface_symbols", "options_only", "surface_trained"):
        assert row["programs"][name] == pytest.approx(mean(p["score"] for p in picks if p["program"] == name))
    four = json.loads((data / "problem_by_problem.json").read_text())["search"][ALL]
    assert (four["both"], four["only_model"], four["only_program"], four["neither"]) == (0, 2, 0, 0)
    wrong = json.loads((data / "wrong_answers.json").read_text())["search"][ALL]
    assert wrong["problems"] == 2 and wrong["wrong_tries"] == 3 and wrong["match_rate"] == pytest.approx(0.5)
    assert wrong["uniform"] == pytest.approx(0.5 / 29) and wrong["shuffle"] == 0
    assert wrong["excess"] == pytest.approx(0.5) and wrong["excess_standard_error"] == 0

    # Counted together: no program puts more than half its weight on a right option (search exactly half), so no
    # program gets either problem; the model gets both (3 of 5 right on each).
    counted = json.loads((data / "counted_together.json").read_text())
    assert list(counted) == [ALL, "2 to 3 cited", "sets, relations and functions"]
    assert counted[ALL] == {"problems": 2, "best_single_program": 0, "best_single_programs": sorted(row["programs"]),
                            "at_least_one_program": 0, "no_program": 2, "model_gets_of_at_least_one_program": 0,
                            "model_gets_of_no_program": 2}
    assert "Counted together" in (data / "report.txt").read_text()

    second = json.loads((data / "second_table.json").read_text())
    assert second["bins"] == {"proved without an option": 0, "has right options": 2, "no option proves it": 0,
                              "stopped for another reason": 0}
    assert second["problems"] == 2 and "search" not in second["programs"]
    assert second["held_back_right_share"] == 1 and second["other_right_mean"] == 0
    assert second["proved_without_use_calls"] == 2
    for key in ("prover", "either", "author"):
        assert second["model"][key] == {"mean": pytest.approx(0.6), "standard_error": pytest.approx(0)}
        assert second["programs"]["guessing"][key]["mean"] == pytest.approx(1 / 30)
    assert "The second table" in (data / "report.txt").read_text() and "lookup" in second["programs"]
    assert "lookup" in (data / "report.txt").read_text() and "lookup" in (data / "bars.svg").read_text()
