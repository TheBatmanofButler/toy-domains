"""Tests of the thinking budget's part in stage 3: the server's reasoning config printed alone, the end text of
the chosen stop sentence recorded and looked up, the budget check's line, and the check judging the answers by
the allowance they were asked with, not this start's."""
import json

import pytest
from stand_in_replies import NEUTRAL_END_TEXT_IDS, NEUTRAL_SENTENCE, forced_reply
from stand_in_server import SETTINGS, make_problems, stand_in  # noqa: F401
from test_stage_3 import check_file, saved, stage_3, stage_3_module

from fe_ladder import model_run
from fe_ladder.model_server import STOP_SENTENCES, ModelServer, end_of_thinking_text
from fe_ladder.problems import read_jsonl, write_jsonl


def problems_and_settings(folder, kinds):
    problems, respond = make_problems(kinds, depths=(2, 3))
    write_jsonl(folder / "test_problems.jsonl", problems)
    (folder / "settings.json").write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    return respond


def forcing(respond, **reply_options):
    """`respond`, with every answer forced as `forced_reply` makes it (its answer text kept)."""
    def answer(path, request):
        status, reply = respond(path, request)
        if path == "/tokenize":
            return status, reply
        return 200, forced_reply(reply["choices"][0]["message"]["content"], **reply_options)
    return answer


def test_the_reasoning_config_is_printed_with_no_other_argument(capsys, monkeypatch):
    module = stage_3_module()
    module.main(["--print-reasoning-config"])
    assert json.loads(capsys.readouterr().out) == {"reasoning_start_str": "<think>",
                                                   "reasoning_end_str": "\n\n" + STOP_SENTENCES["qwen"] + "\n</think>"}
    module.main(["--print-reasoning-config", "--stop-sentence", "neutral"])
    assert json.loads(capsys.readouterr().out)["reasoning_end_str"] == end_of_thinking_text(STOP_SENTENCES["neutral"])
    monkeypatch.setattr(module.sys, "argv", ["3_model_run.py", "--stop-sentence", "Time is up.", "--print-reasoning-config"])
    module.main()
    assert json.loads(capsys.readouterr().out)["reasoning_end_str"] == "\n\nTime is up.\n</think>"


def test_the_run_records_the_end_of_thinking_text_and_the_budget_line_is_printed(tmp_path, stand_in, capsys):
    respond = problems_and_settings(tmp_path, ["right", "not_enforced", "right", "out_of_thinking"])
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [stand_in(respond)], "--check-after", "8")
    record = saved(tmp_path)[0]
    assert record["settings"]["end_of_thinking_text"] == "\n\n" + STOP_SENTENCES["qwen"] + "\n</think>"
    assert record["settings"]["answer_allowance"] == 1000
    result = check_file(tmp_path)
    # 8 answers: 2 tries of each problem. The 2 not enforced think 9,000 with no end text; the 2 forced fit.
    assert result["budget_check"] == "not as assumed" and result["budget_misfit_count"] == 2
    assert result["end_text_outside_budget_count"] == 2 and result["thinking_allowances"] == [8000]
    printed = capsys.readouterr().out
    assert ("  server's thinking budget: not as assumed (2 forced: 2 with the end text after the allowance, 0 with "
            "it inside; 2 that do not fit)") in printed
    assert "no end text, 9000 thinking tokens, allowance 8000" in printed


def test_the_end_text_is_looked_up_for_the_chosen_sentence(tmp_path, stand_in):
    # A server started with the neutral sentence: its end text (22 ids) is what the run looks for, so the
    # forced answers are seen in the token ids and fit; the Qwen end text's ids would not be found.
    respond = problems_and_settings(tmp_path, ["right", "right", "wrong", "wrong"])
    stage_3(tmp_path, [stand_in(forcing(respond, sentence=NEUTRAL_SENTENCE))], "--stop-sentence", "neutral",
            "--check-after", "8")
    records = saved(tmp_path)
    assert len(records) == 20 and all(r["end_text_token_ids"] == NEUTRAL_END_TEXT_IDS for r in records)
    assert all(r["forced"] and r["stop_sentence_found_in"] == ["reasoning", "token_ids"] for r in records)
    assert all(r["thinking_tokens"] == 8021 and r["thinking_tokens_before_end_text"] == 8000 for r in records)
    assert check_file(tmp_path)["passed"] and check_file(tmp_path)["budget_check"] == "as assumed"


def test_the_check_uses_the_allowance_the_answers_were_asked_with(tmp_path, stand_in):
    # 12 answers asked earlier with an allowance of 6,000, from a server that forces at 6,000: they fit. This
    # start's allowance is the default 8,000, by which they would not.
    respond = problems_and_settings(tmp_path, ["right"] * 4)
    server = stand_in(forcing(respond, before=6000))
    model_run.run(read_jsonl(tmp_path / "test_problems.jsonl"), [ModelServer(server.base_url, "m", wait_seconds=0)],
                  tmp_path / "model_answers.jsonl", 5, dict(SETTINGS, thinking_allowance=6000), "m@1", 1, limit=12,
                  log=lambda *_: None)
    assert all(r["forced"] for r in saved(tmp_path))
    stage_3(tmp_path, [server])
    result = check_file(tmp_path)
    assert result["passed"] and result["budget_check"] == "as assumed" and result["thinking_allowances"] == [6000]
