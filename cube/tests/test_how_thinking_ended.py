"""How each scripted way of ending the thinking is recorded by a run against the stand-in server, and how the
budget check judges it, worked by hand. Allowance 8,000, tolerance 8; the Qwen end text is 20 ids, 19 before
the marker, so a forced reply has 19 more thinking tokens than the thinking before its end text."""
import pytest
from stand_in_replies import END_TEXT_IDS, forced_reply, tokenize
from stand_in_server import SETTINGS, make_states, stand_in  # noqa: F401

from cube_ladder import model_run, run_check
from cube_ladder.model_server import ModelServer

R_T = ["reasoning", "token_ids"]
# kind: (stop_sentence_found_in, thinking_tokens, thinking_tokens_before_end_text, at_allowance,
#        end_text_inside_budget, forced, cut_off, what the budget check says)
EXPECTED = {
    "out_of_thinking": (R_T, 8019, 8000, True, False, True, False, None),
    "forced_inside_budget": (R_T, 7999, 7980, True, True, True, False, None),             # 7,972 <= 7,980
    "writes_stop_sentence": (R_T, 3019, 3000, False, None, False, False,
                             "end text after 3000 thinking tokens, allowance 8000"),
    "closed_early": (R_T, 6019, 6000, False, None, False, False, "end text after 6000 thinking tokens, allowance 8000"),
    "sentence_mid_thinking": ([], 3019, 3019, False, None, False, False, None),
    "ends_5_under": ([], 7995, 7995, True, None, False, False, None),                     # healthy, not forced
    "ends_50_under": ([], 7950, 7950, False, None, False, False, None),
    "other_finish_reason": ([], 90, 90, False, None, False, False, None),
    "cut_off_readable": ([], 7000, 7000, False, None, False, True, None),
    "not_enforced": ([], 9000, 9000, False, None, False, True, "no end text, 9000 thinking tokens, allowance 8000"),
}


def run(states, respond, stand_in, path, tries=1, limit=None):
    client = ModelServer(stand_in(respond).base_url, "test-model", wait_seconds=0)
    model_run.run(states, [client], path, tries, SETTINGS, "test-model@abc123", run_seed=3, limit=limit,
                  log=lambda *_: None)
    return model_run.read_saved(path)


@pytest.mark.parametrize("kind", sorted(EXPECTED))
def test_each_way_of_ending_the_thinking(stand_in, tmp_path, kind):
    states, respond = make_states([kind])
    record = run(states, respond, stand_in, tmp_path / "answers.jsonl")[0]
    fields = ("stop_sentence_found_in", "thinking_tokens", "thinking_tokens_before_end_text", "at_allowance",
              "end_text_inside_budget", "forced", "cut_off")
    assert tuple(record[f] for f in fields) + (run_check.budget_misfit(record),) == EXPECTED[kind]
    assert record["right"] == (kind != "not_enforced")              # every other kind answers the right turn
    assert record["end_text_token_ids"] == END_TEXT_IDS


def test_a_finish_reason_other_than_stop_or_length_is_not_cut_off(stand_in, tmp_path):
    states, respond = make_states(["other_finish_reason"])
    record = run(states, respond, stand_in, tmp_path / "answers.jsonl")[0]
    assert record["finish_reason"] == "abort" and not record["cut_off"] and not record["cut_off_but_readable"]


def test_the_end_text_at_the_very_end_of_the_ids_is_found(stand_in, tmp_path):
    # Forced at 8,000 and cut off right after the marker: the end text's ids are the last ids of the reply.
    # The reasoning field here does not keep the sentence, so only the ids can show it.
    states, _ = make_states(["right"])
    reply = forced_reply("", answer_tokens=0, finish_reason="length")
    reply["choices"][0]["message"]["reasoning_content"] = "Hmm"
    assert reply["choices"][0]["token_ids"][-20:] == END_TEXT_IDS
    record = run(states, lambda p, r: tokenize(r) if p == "/tokenize" else (200, reply), stand_in,
                 tmp_path / "answers.jsonl")[0]
    assert record["stop_sentence_found_in"] == ["token_ids"] and record["thinking_tokens_before_end_text"] == 8000
    assert record["forced"] and record["cut_off"] and record["answer_tokens"] == 0


def checked(stand_in, tmp_path, kinds):
    """The run's check on all 5 tries of one state of each kind, at $1 an hour for 20 answers."""
    states, respond = make_states(kinds, distances=(2, 3))
    answers = run(states, respond, stand_in, tmp_path / "answers.jsonl", tries=5)
    return run_check.check(answers, 20, 1.0)


def test_a_healthy_answer_ending_by_itself_at_7950_passes(stand_in, tmp_path):
    result = checked(stand_in, tmp_path, ["right", "right", "right", "ends_50_under"])
    assert result["passed"] and result["budget_check"] == "as assumed" and result["budget_misfit_count"] == 0


def test_a_server_forcing_at_6000_fails(stand_in, tmp_path):
    result = checked(stand_in, tmp_path, ["right", "right", "right", "closed_early"])
    assert not result["passed"] and result["budget_check"] == "not as assumed"
    assert result["budget_misfit_count"] == 5 and result["forced_answers_compared"] == 0
    assert "end text after 6000 thinking tokens, allowance 8000" in result["problems"][0]


def test_forced_answers_record_where_the_end_text_was_counted(stand_in, tmp_path):
    result = checked(stand_in, tmp_path, ["right", "out_of_thinking", "right", "forced_inside_budget"])
    assert result["passed"] and result["forced_answers_compared"] == 10
    assert result["end_text_outside_budget_count"] == 5 and result["end_text_inside_budget_count"] == 5
