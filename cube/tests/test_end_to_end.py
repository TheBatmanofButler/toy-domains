"""The whole chain, stage by stage, through files, on a tiny set: cubes scrambled by up to 4 turns, the
brute-force solver, and a stand-in model scripted per state to be always right, always wrong, unreadable,
or out of thinking (the server closes the thinking with the stop sentence and it answers right, in the same
reply).

Hand-worked expectations. Each distance 2 to 4 has 4 test states; state k at each distance gets the
script k = 1 right, 2 wrong, 3 unreadable, 4 out of thinking. So at every distance: model score
(1 + 0 + 0 + 1) / 4 = 0.5; unreadable 1/4; forced 1/4. Thinking tokens: the stand-in thinks 90 tokens,
then the end-of-thinking token and 10 answer tokens (101 in all), or reaches the budget after 8,000 tokens,
when the server's end-of-thinking text adds 19 thinking tokens and the end-of-thinking token, then 4 answer
tokens (8,024 in all). The thinking figure is the model's own, the 8,000 before the end text for a forced
answer: (3 x 90 + 8000) / 4 = 2067.5; tokens used (3 x 101 + 8024) / 4 = 2081.75.
Tokens per cube string: the stand-in counts words + 10 = 11.
The model gets states 1 and 4. Lookahead of depth k scores 1 at distances up to k, so room is 0 at 2 and 3,
and lookahead_3 gets every state there: both 2, only the program 2, only the model 0, neither 0, and no
"only the model" state expected by chance either way. Guessing never gets a state (at most 2 or 3 right turns
of 18 here): only the model 2, neither 2 at every distance, and 4 x 2/4 = 2 expected if independent.
The run's check is set to look at all 60 answers: 15 are unreadable (0.25, above 0.15), so it stops; the 15
forced answers (enough to compare: at least 10 of each) are all readable (1.0) against 30 of 45 unforced
(0.67), so that check holds. The budget behaves as assumed: the 15 forced answers have the end text after
exactly 8,000 thinking tokens (the end text counted outside the budget), and the 45 others end by themselves
after 90. After the decision to carry on, the
run is started again with --carry-on and finishes.
Same wrong turns: at each distance only state 2 has wrong tries, all five on the same wrong turn, so every
figure rests on 1 cube and 5 wrong tries and none has a standard error. Guessing puts 1/18 on every turn of
every cube, so its match, its uniform figure ((18 - r) x 1/18 over 18 - r wrong turns) and its shuffle are all
1/18, and its excess is 0; its excess over a control is then minus the control's excess. lookahead_3 at 2 and
3 puts all its weight on right turns, so its match and uniform figures are 0 there.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from stand_in_replies import chat_reply, forced_reply, tokenize
from stand_in_server import StandInServer, cube_colours_in

from cube_ladder.cube import TURNS
from cube_ladder.question import colours
from cube_ladder.states import read_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"
KINDS = {1: "right", 2: "wrong", 3: "unreadable", 4: "out_of_thinking"}


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def stand_in_for(test_states):
    by_colours = {colours(s["cube"]): s for s in test_states}

    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        state = by_colours[cube_colours_in(request)]
        kind = KINDS[int(state["id"].split("-")[2])]
        right = state["right_turns"][0]
        wrong = next(t for t in TURNS if t not in state["right_turns"])
        if kind == "out_of_thinking":
            return 200, forced_reply(f"MOVE: {right}")
        return 200, chat_reply({"right": f"MOVE: {right}", "wrong": f"MOVE: {wrong}",
                                "unreadable": "Not sure."}[kind])
    return StandInServer(respond)


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    stage("1_build_states")(["--data", str(data), "--seed", "5", "--brute-force-scramble", "4",
                             "--test-per-distance", "4", "--train-per-distance", "30", "--follow-home", "2-3",
                             "--as-drawn", "4", "--batch-size", "20", "--give-up-after", "500"])
    stage("2_run_programs")(["--data", str(data), "--lookup-tolerance", "1"])
    server = stand_in_for(read_jsonl(data / "test_states.jsonl"))
    settings = data / "settings.json"
    settings.write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    common = ["--data", str(data), "--base-url", server.base_url, "--model-name", "stand-in", "--model-version",
              "stand-in@1", "--settings", str(settings), "--seed", "9", "--workers", "2", "--wait-seconds", "0",
              "--check-after", "60", "--price-per-hour", "1"]
    with pytest.raises(SystemExit) as check_stop:
        stage("3_model_run")(common)
    stage("3_model_run")(common + ["--carry-on"])
    stage("4_report")(["--data", str(data)])
    server.close()
    return data, str(check_stop.value)


def test_files_are_written(chain):
    data, _ = chain
    for name in ("test_states.jsonl", "train_states.jsonl", "build_summary.json", "program_picks.jsonl",
                 "programs_summary.json", "model_run_check.json", "model_answers.jsonl",
                 "scores_by_distance.json", "state_by_state.json", "wrong_turns.json", "report.txt", "curve.svg"):
        assert (data / name).exists(), name
    assert len(read_jsonl(data / "model_answers.jsonl")) == 12 * 5
    assert len(read_jsonl(data / "program_picks.jsonl")) == 12 * 9


def test_the_run_checks_itself_and_stops_on_unreadable_answers(chain):
    data, message = chain
    result = json.loads((data / "model_run_check.json").read_text())
    assert message.startswith("STOP") and not result["passed"] and len(result["problems"]) == 1
    assert "0.25 of answers unreadable" in result["problems"][0]
    assert result["answers_checked"] == 60 and result["unreadable_share"] == 0.25 and result["forced_share"] == 0.25
    assert result["forced_readable_share"] == 1 and result["unforced_readable_share"] == pytest.approx(30 / 45)
    assert result["share_with_thinking"] == 1 and result["tokens_per_cube_string"] == 11
    assert result["forced_comparison"] == "tested"
    assert result["forced_answers_compared"] == 15 and result["unforced_answers_compared"] == 45
    assert result["budget_check"] == "as assumed" and result["end_text_outside_budget_count"] == 15
    assert result["budget_misfit_count"] == 0


def test_final_scores_equal_the_hand_worked_table(chain):
    data, _ = chain
    table = json.loads((data / "scores_by_distance.json").read_text())
    assert sorted(table) == ["2", "3", "4"]
    for distance, row in table.items():
        assert row["states"] == 4
        assert row["model"] == 0.5
        assert row["unreadable_share"] == 0.25 and row["forced_share"] == 0.25 and row["failed_share"] == 0
        assert row["thinking_tokens_mean"] == 2067.5 and row["tokens_used_mean"] == 2081.75
        assert row["most_cubes_written"] == pytest.approx(2081.75 / 11)
        for depth in (1, 2, 3):
            if int(distance) <= depth:
                assert row["programs"][f"lookahead_{depth}"] == 1
        if int(distance) <= 3:
            assert row["room"] == 0
        # Model state scores are 1, 0, 0, 1: mean .5, squares about it sum to 1, variance 1/3,
        # standard error sqrt(1/3 / 4) = sqrt(1/12).
        assert row["model_standard_error"] == pytest.approx((1 / 12) ** 0.5)


def test_final_state_by_state_equals_the_hand_worked_table(chain):
    data, _ = chain
    table = json.loads((data / "state_by_state.json").read_text())
    for distance in ("2", "3"):
        assert table["lookahead_3"][distance] == {"both": 2, "only_model": 0, "only_program": 2, "neither": 0,
                                                  "only_model_expected_by_chance": 0.0,
                                                  "only_model_expected_if_independent": 0.0,
                                                  "only_model_if_independent_standard_error": 0.0}
    for distance in ("2", "3", "4"):
        row = table["guessing"][distance]
        assert [row[k] for k in ("both", "only_model", "only_program", "neither")] == [0, 2, 0, 2]
        assert row["only_model_expected_if_independent"] == 2
        assert row["only_model_if_independent_standard_error"] == 1   # sqrt(4 x 0.5 x 0.5)


def test_same_wrong_turns_equal_the_hand_worked_line(chain):
    data, _ = chain
    table = json.loads((data / "wrong_turns.json").read_text())
    controls = ["recall_bottom", "recall_top", "surface_strict"]
    for distance in ("2", "3", "4"):
        row = table["guessing"][distance]
        assert row["cubes"] == 1 and row["wrong_tries"] == 5
        assert row["match_rate"] == pytest.approx(1 / 18) and row["uniform"] == pytest.approx(1 / 18)
        assert row["shuffle"] == pytest.approx(1 / 18) and row["excess"] == pytest.approx(0, abs=1e-12)
        assert row["match_rate_standard_error"] is None and row["excess_standard_error"] is None
        assert sorted(row["excess_over_control"]) == controls
        for control in controls:
            assert row["excess_over_control"][control]["mean"] == pytest.approx(-table[control][distance]["excess"])
            assert row["excess_over_control"][control]["standard_error"] is None
    for distance in ("2", "3"):
        assert table["lookahead_3"][distance]["match_rate"] == 0 and table["lookahead_3"][distance]["uniform"] == 0
    assert "Same wrong turns, over the cubes" in (data / "report.txt").read_text()


def test_the_report_stage_run_twice_gives_identical_files(chain):
    data, _ = chain
    names = ("scores_by_distance.json", "state_by_state.json", "wrong_turns.json", "report.txt", "curve.svg")
    before = {name: (data / name).read_bytes() for name in names}
    stage("4_report")(["--data", str(data)])
    assert {name: (data / name).read_bytes() for name in names} == before


def test_rerunning_the_model_stage_asks_nothing_new(chain, capsys):
    data, _ = chain
    before = (data / "model_answers.jsonl").read_bytes()
    server = stand_in_for(read_jsonl(data / "test_states.jsonl"))
    settings = str(data / "settings.json")
    stage("3_model_run")(["--data", str(data), "--base-url", server.base_url, "--model-name", "stand-in",
                          "--model-version", "stand-in@1", "--settings", settings, "--seed", "9", "--check-after", "60",
                          "--price-per-hour", "1", "--carry-on"])
    server.close()
    assert [path for path, _ in server.requests if path != "/tokenize"] == []
    assert (data / "model_answers.jsonl").read_bytes() == before
    assert "60 answers already saved, 0 to ask" in capsys.readouterr().out
