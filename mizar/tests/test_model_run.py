"""Tests of model_run.py and model_server.py, all against a stand-in server that answers by script."""
import json

import pytest
import urllib.error
import urllib.request

from stand_in_replies import END_TEXT_IDS, THINK_END, chat_reply, tokenize
from stand_in_server import SETTINGS, make_problems, stand_in  # noqa: F401

from mizar_ladder import model_run
from mizar_ladder.model_server import STOP_SENTENCES, ModelServer, end_of_thinking_text, reasoning_config
from mizar_ladder.thinking_end import split_token_count


def run(problems, server, path, **options):
    client = ModelServer(server.base_url, "test-model", wait_seconds=0, **options.pop("client", {}))
    return model_run.run(problems, [client], path, 5, SETTINGS, "test-model@abc123", run_seed=3, log=lambda *_: None,
                         **options)


def chats(server):
    return [request for path, request in server.requests if path == "/v1/chat/completions"]


def test_five_tries_give_five_records(stand_in, tmp_path):
    problems, respond = make_problems(["right"])
    server = stand_in(respond)
    run(problems, server, tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert [r["try"] for r in records] == [1, 2, 3, 4, 5]
    assert all(r["right"] and r["option"] == problems[0]["held_back"] and not r["forced"] for r in records)
    assert all(r["model_version"] == "test-model@abc123" and r["settings"] == SETTINGS for r in records)
    assert all(r["server"] == server.base_url for r in records)
    assert len({r["request_seed"] for r in records}) == 5
    first = chats(server)[0]
    assert records[0]["question"] == first["messages"][1]["content"]
    assert first["thinking_token_budget"] == 8000 and first["max_tokens"] == 8000 + 1000 and first["temperature"] == 0.6
    assert first["chat_template_kwargs"] == {"enable_thinking": True} and first["seed"] == records[0]["request_seed"]
    # Token counts: 90 thinking ids, the end-of-thinking id, then 10 + seed % 7 answer ids.
    assert records[0]["thinking_tokens"] == 90 and records[0]["think_end_token_id"] == THINK_END
    assert records[0]["answer_tokens"] == 10 + records[0]["request_seed"] % 7
    assert records[0]["generated_tokens"] == records[0]["tokens_used"] == 91 + records[0]["answer_tokens"]
    assert records[0]["at_allowance"] is False and not records[0]["cut_off"]
    assert records[0]["stop_sentence_found_in"] == []
    assert records[0]["thinking_tokens_before_end_text"] == 90 and records[0]["end_text_inside_budget"] is None
    assert records[0]["end_text_token_ids"] == END_TEXT_IDS


def test_every_request_carries_the_thinking_budget_and_one_request_gives_one_answer(stand_in, tmp_path):
    kinds = ["right", "wrong", "unreadable", "out_of_thinking", "cut_off_readable", "not_enforced"]
    problems, respond = make_problems(kinds)
    server = stand_in(respond)
    run(problems, server, tmp_path / "answers.jsonl")
    assert len(chats(server)) == len(model_run.read_saved(tmp_path / "answers.jsonl")) == 30
    assert all(r["thinking_token_budget"] == 8000 and r["max_tokens"] == 9000 for r in chats(server))
    assert all(set(r) == set(chats(server)[0]) for r in chats(server))      # the same shape every time


def test_the_stand_in_refuses_a_request_without_the_budget(stand_in, tmp_path, monkeypatch):
    problems, respond = make_problems(["right"])
    server = stand_in(respond)
    request = urllib.request.Request(server.base_url + "/v1/chat/completions", data=b'{"messages": []}',
                                     headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError, match="400"):
        urllib.request.urlopen(request)
    real = model_run.question_request
    monkeypatch.setattr(model_run, "question_request",
                        lambda *a: {k: v for k, v in real(*a).items() if k != "thinking_token_budget"})
    run(problems, server, tmp_path / "answers.jsonl", client={"attempts": 1})
    assert all(r["failed"] and "400" in r["error"] for r in model_run.read_saved(tmp_path / "answers.jsonl"))


def test_the_end_of_thinking_text_and_the_servers_reasoning_config():
    sentence = STOP_SENTENCES["qwen"]
    assert sentence == ("Considering the limited time by the user, I have to give the solution based on the "
                        "thinking directly now.")
    assert end_of_thinking_text(sentence) == "\n\n" + sentence + "\n</think>"
    assert json.loads(reasoning_config(sentence)) == {"reasoning_start_str": "<think>",
                                                      "reasoning_end_str": "\n\n" + sentence + "\n</think>"}


def test_an_unreadable_answer_is_saved_as_wrong(stand_in, tmp_path):
    problems, respond = make_problems(["unreadable", "wrong"])
    run(problems, stand_in(respond), tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    unreadable = [r for r in records if r["problem_id"] == problems[0]["id"]]
    assert all(r["option"] is None and r["right"] is False and not r["forced"] for r in unreadable)
    wrong = [r for r in records if r["problem_id"] == problems[1]["id"]]
    assert all(r["option"] == 3 and r["right"] is False for r in wrong)     # problem 2 holds back option 2


@pytest.mark.parametrize("workers", [1, 3])
def test_stopping_halfway_and_restarting_gives_the_same_file(stand_in, tmp_path, workers):
    problems, respond = make_problems(["right", "wrong", "unreadable", "out_of_thinking"])
    server = stand_in(respond)
    unbroken = tmp_path / "unbroken.jsonl"
    run(problems, server, unbroken, workers=workers)
    lines = unbroken.read_text().splitlines(keepends=True)
    stopped = tmp_path / "stopped.jsonl"
    stopped.write_text("".join(lines[:7]) + lines[7][:30])   # stopped in the middle of writing line 8
    assert len(run(problems, server, stopped, workers=workers)) == 20 - 7

    def without_timing(text_lines):
        return sorted(json.dumps({k: v for k, v in json.loads(line).items() if k not in ("seconds", "finished_at")},
                                 sort_keys=True) for line in text_lines)
    restarted = stopped.read_text().splitlines()
    assert without_timing(restarted) == without_timing(unbroken.read_text().splitlines())
    if workers == 1:
        assert [json.loads(line)["problem_id"] for line in restarted] == [json.loads(line)["problem_id"] for line in lines]


def test_a_limit_asks_only_the_first_answers(stand_in, tmp_path):
    problems, respond = make_problems(["right", "wrong"])
    server = stand_in(respond)
    assert len(run(problems, server, tmp_path / "a.jsonl", limit=7)) == 7
    asked = [(r["problem_id"], r["try"]) for r in model_run.read_saved(tmp_path / "a.jsonl")]
    assert [t for _, t in asked] == [1, 1, 2, 2, 3, 3, 4]          # every problem's try before anyone's next try
    assert asked[-1][0] == asked[0][0] and {asked[0][0], asked[1][0]} == {s["id"] for s in problems}
    assert run(problems, server, tmp_path / "a.jsonl", limit=0) == []


def test_a_server_error_is_retried_then_recorded(stand_in, tmp_path):
    problems, respond = make_problems(["right"])
    server = stand_in(lambda path, request: tokenize(request) if path == "/tokenize" else (500, {"error": "oom"}))
    run(problems, server, tmp_path / "answers.jsonl", client={"attempts": 3})
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert len(records) == 5 and len(chats(server)) == 15
    assert all(r["failed"] and r["option"] is None and r["right"] is False for r in records)
    assert "failed 3 times" in records[0]["error"] and "500" in records[0]["error"]


def test_a_passing_error_is_retried_and_forgotten(stand_in, tmp_path):
    problems, respond = make_problems(["right"])
    calls = []

    def flaky(path, request):
        calls.append(path)
        return (503, {}) if len(calls) % 2 == 1 else respond(path, request)
    run(problems, stand_in(flaky), tmp_path / "answers.jsonl", client={"attempts": 2})
    assert not any(r["failed"] for r in model_run.read_saved(tmp_path / "answers.jsonl"))


def test_failed_answers_can_be_asked_again(stand_in, tmp_path):
    problems, respond = make_problems(["right"])
    path = tmp_path / "answers.jsonl"
    run(problems, stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (500, {})), path, client={"attempts": 1})
    run(problems, stand_in(respond), path)                       # failed records count as saved: nothing asked
    assert all(r["failed"] for r in model_run.read_saved(path))
    run(problems, stand_in(respond), path, retry_failed=True)
    records = model_run.read_saved(path)
    assert len(records) == 5 and not any(r["failed"] for r in records)


def test_a_malformed_reply_is_recorded_as_failed(stand_in, tmp_path):
    problems, _ = make_problems(["right"])
    run(problems[:1], stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (200, {"choices": []})),
        tmp_path / "answers.jsonl")
    assert all(r["failed"] and "BadReply" in r["error"] for r in model_run.read_saved(tmp_path / "answers.jsonl"))


def test_an_error_in_our_own_code_is_not_retried(stand_in, tmp_path, monkeypatch):
    problems, respond = make_problems(["right"])
    server = stand_in(respond)
    monkeypatch.setattr(model_run, "build_question", lambda problem: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        run(problems, server, tmp_path / "answers.jsonl")
    assert chats(server) == []


def test_reasoning_may_come_under_either_name(stand_in, tmp_path):
    problems, _ = make_problems(["right"])
    reply = chat_reply("FACT: 1", reasoning=None)
    reply["choices"][0]["message"]["reasoning"] = "thought under the other name"
    run(problems, stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (200, reply)), tmp_path / "answers.jsonl")
    assert model_run.read_saved(tmp_path / "answers.jsonl")[0]["thinking"] == "thought under the other name"


def test_token_counts_without_ids_are_left_empty(stand_in, tmp_path):
    problems, respond = make_problems(["right"])

    def no_ids(path, request):
        status, reply = respond(path, request)
        if path == "/tokenize":
            return 200, {"count": 3, "tokens": [5, 6, 7]}            # '</think>' is not one token here
        return status, reply
    run(problems, stand_in(no_ids), tmp_path / "answers.jsonl")
    record = model_run.read_saved(tmp_path / "answers.jsonl")[0]
    assert record["thinking_tokens"] is None and record["answer_tokens"] is None and record["generated_tokens"] > 0
    assert split_token_count(None, 9) == (None, None)


def test_count_tokens_and_the_key_is_sent(stand_in):
    problems, respond = make_problems(["right"])
    server = stand_in(respond)
    client = ModelServer(server.base_url + "/", "m", api_key="secret-for-test")
    assert client.count_tokens("a b c") == 13
    assert server.requests[0] == ("/tokenize", {"model": "m", "prompt": "a b c", "add_special_tokens": False})
    assert server.headers[0]["Authorization"] == "Bearer secret-for-test"


def test_request_seeds_are_fixed_by_problem_and_try():
    assert model_run.request_seed(1, "test-0001", 1) == model_run.request_seed(1, "test-0001", 1)
    assert model_run.request_seed(1, "test-0001", 1) != model_run.request_seed(1, "test-0001", 2)
    assert model_run.request_seed(1, "test-0001", 1) != model_run.request_seed(2, "test-0001", 1)
