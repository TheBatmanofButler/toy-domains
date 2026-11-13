"""Tests of model_run.py and model_server.py, all against a stand-in server that answers by script."""
import json

import pytest
from stand_in_server import THINK_END, StandInServer, chat_reply, scripted, tokenize

from cube_ladder import model_run
from cube_ladder.cube import SOLVED, TURNS, apply_turns
from cube_ladder.model_server import STOP_SENTENCES, ModelServer, continuation_request
from cube_ladder.question import colours

SETTINGS = {"sampling": {"temperature": 0.6, "top_p": 0.95}, "source": "the model's documentation (test value)",
            "stop_sentence": STOP_SENTENCES["qwen"], "thinking_allowance": 8000, "answer_allowance": 200}


def make_states(kinds):
    """One state per kind; each is one turn from solved, so its right turn is known."""
    states, kind_of, turns_of = [], {}, {}
    for n, kind in enumerate(kinds):
        turn = TURNS[n]
        cube = apply_turns(SOLVED, [turn])
        right = turn[0] + {"": "'", "'": "", "2": "2"}[turn[1:]]
        states.append({"id": f"test-02-{n + 1:04d}", "cube": cube, "distance": 2, "right_turns": [right]})
        kind_of[colours(cube)] = kind
        turns_of[colours(cube)] = (right, "B2" if right != "B2" else "U")
    return states, scripted(kind_of, turns_of)


@pytest.fixture
def stand_in():
    servers = []

    def start(respond):
        servers.append(StandInServer(respond))
        return servers[-1]
    yield start
    for server in servers:
        server.close()


def run(states, server, path, **options):
    client = ModelServer(server.base_url, "test-model", wait_seconds=0, **options.pop("client", {}))
    return model_run.run(states, client, path, 5, SETTINGS, "test-model@abc123", run_seed=3, log=lambda *_: None,
                         **options)


def chats(server):
    return [request for path, request in server.requests if path == "/v1/chat/completions"]


def test_five_tries_give_five_records(stand_in, tmp_path):
    states, respond = make_states(["right"])
    server = stand_in(respond)
    run(states, server, tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert [r["try"] for r in records] == [1, 2, 3, 4, 5]
    assert all(r["right"] and r["turn"] == states[0]["right_turns"][0] and not r["forced"] for r in records)
    assert all(r["model_version"] == "test-model@abc123" and r["settings"] == SETTINGS for r in records)
    assert len({r["request_seed"] for r in records}) == 5
    first = chats(server)[0]
    assert records[0]["question"] == first["messages"][1]["content"]
    assert first["max_tokens"] == 8000 + 200 and first["temperature"] == 0.6
    assert first["chat_template_kwargs"] == {"enable_thinking": True} and first["seed"] == records[0]["request_seed"]
    # Token counts: 90 thinking ids, the end-of-thinking id, then 10 + seed % 7 answer ids.
    assert records[0]["thinking_tokens"] == 90 and records[0]["think_end_token_id"] == THINK_END
    assert records[0]["answer_tokens"] == 10 + records[0]["request_seed"] % 7
    assert records[0]["generated_tokens"] == records[0]["tokens_used"] == 91 + records[0]["answer_tokens"]
    assert records[0]["forced_answer_tokens"] == 0


def test_running_out_continues_the_same_turn_after_the_stop_sentence(stand_in, tmp_path):
    states, respond = make_states(["out_of_thinking"])
    server = stand_in(respond)
    run(states, server, tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert all(r["forced"] and r["right"] and not r["cut_off_but_readable"] for r in records)
    assert len(chats(server)) == 10
    first, continuation = chats(server)[0], chats(server)[1]
    assert continuation["messages"][:2] == first["messages"]                    # no new user message
    assert [m["role"] for m in continuation["messages"]] == ["system", "user", "assistant"]
    text = continuation["messages"][2]["content"]
    assert text == "<think>\n" + ("Hmm " * 50).strip() + "\n\n" + STOP_SENTENCES["qwen"] + "\n</think>\n\n"
    assert continuation["continue_final_message"] is True and continuation["add_generation_prompt"] is False
    assert continuation["max_tokens"] == 200
    record = records[0]
    assert record["thinking"] == "Hmm " * 50 and record["first_answer_text"] == "" and record["continuation_text"] == text
    assert record["thinking_tokens"] == 8200 and record["answer_tokens"] == 0     # thinking never ended
    assert record["forced_answer_tokens"] == 4 and record["tokens_used"] == 8204
    assert record["continuation_answer_field"] == "content"


def test_an_answer_cut_off_but_already_readable_is_not_forced(stand_in, tmp_path):
    states, respond = make_states(["cut_off_readable"])
    server = stand_in(respond)
    run(states, server, tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert all(r["cut_off_but_readable"] and not r["forced"] and r["right"] for r in records)
    assert len(chats(server)) == 5


def test_continued_answer_may_come_back_as_thinking(stand_in, tmp_path):
    states, _ = make_states(["right"])

    def respond(path, request):
        if path == "/tokenize":
            return tokenize(request)
        if request.get("continue_final_message"):
            return 200, chat_reply("", reasoning="MOVE: R'", thinking_tokens=0, answer_tokens=3, closed=False)
        return 200, chat_reply("", reasoning="Hmm", finish_reason="length", closed=False)
    run(states[:1], stand_in(respond), tmp_path / "answers.jsonl")
    record = model_run.read_saved(tmp_path / "answers.jsonl")[0]
    assert record["forced"] and record["answer_text"] == "MOVE: R'" and record["continuation_answer_field"] == "reasoning"


def test_continuation_request_shape():
    request, text = continuation_request("m", [{"role": "user", "content": "q"}], "  thought \n", "Stop now.", 200,
                                         {"temperature": 0.6}, 7)
    assert text == "<think>\nthought\n\nStop now.\n</think>\n\n"
    assert request == {"model": "m", "messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": text}],
                       "add_generation_prompt": False, "continue_final_message": True, "max_tokens": 200, "seed": 7,
                       "chat_template_kwargs": {"enable_thinking": True}, "return_token_ids": True, "temperature": 0.6}


def test_an_unreadable_answer_is_saved_as_wrong(stand_in, tmp_path):
    states, respond = make_states(["unreadable", "wrong"])
    run(states, stand_in(respond), tmp_path / "answers.jsonl")
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    unreadable = [r for r in records if r["state_id"] == states[0]["id"]]
    assert all(r["turn"] is None and r["right"] is False and not r["forced"] for r in unreadable)
    wrong = [r for r in records if r["state_id"] == states[1]["id"]]
    assert all(r["turn"] == "B2" and r["right"] is False for r in wrong)


@pytest.mark.parametrize("workers", [1, 3])
def test_stopping_halfway_and_restarting_gives_the_same_file(stand_in, tmp_path, workers):
    states, respond = make_states(["right", "wrong", "unreadable", "out_of_thinking"])
    server = stand_in(respond)
    unbroken = tmp_path / "unbroken.jsonl"
    run(states, server, unbroken, workers=workers)
    lines = unbroken.read_text().splitlines(keepends=True)
    stopped = tmp_path / "stopped.jsonl"
    stopped.write_text("".join(lines[:7]) + lines[7][:30])   # stopped in the middle of writing line 8
    assert len(run(states, server, stopped, workers=workers)) == 20 - 7

    def without_timing(text_lines):
        return sorted(json.dumps({k: v for k, v in json.loads(line).items() if k not in ("seconds", "finished_at")},
                                 sort_keys=True) for line in text_lines)
    restarted = stopped.read_text().splitlines()
    assert without_timing(restarted) == without_timing(unbroken.read_text().splitlines())
    if workers == 1:
        assert [json.loads(line)["state_id"] for line in restarted] == [json.loads(line)["state_id"] for line in lines]


def test_a_limit_asks_only_the_first_answers(stand_in, tmp_path):
    states, respond = make_states(["right", "wrong"])
    server = stand_in(respond)
    assert len(run(states, server, tmp_path / "a.jsonl", limit=7)) == 7
    assert [(r["state_id"], r["try"]) for r in model_run.read_saved(tmp_path / "a.jsonl")][-1] == (states[1]["id"], 2)
    assert run(states, server, tmp_path / "a.jsonl", limit=0) == []


def test_a_server_error_is_retried_then_recorded(stand_in, tmp_path):
    states, respond = make_states(["right"])
    server = stand_in(lambda path, request: tokenize(request) if path == "/tokenize" else (500, {"error": "oom"}))
    run(states, server, tmp_path / "answers.jsonl", client={"attempts": 3})
    records = model_run.read_saved(tmp_path / "answers.jsonl")
    assert len(records) == 5 and len(chats(server)) == 15
    assert all(r["failed"] and r["turn"] is None and r["right"] is False for r in records)
    assert "failed 3 times" in records[0]["error"] and "500" in records[0]["error"]


def test_a_passing_error_is_retried_and_forgotten(stand_in, tmp_path):
    states, respond = make_states(["right"])
    calls = []

    def flaky(path, request):
        calls.append(path)
        return (503, {}) if len(calls) % 2 == 1 else respond(path, request)
    run(states, stand_in(flaky), tmp_path / "answers.jsonl", client={"attempts": 2})
    assert not any(r["failed"] for r in model_run.read_saved(tmp_path / "answers.jsonl"))


def test_failed_answers_can_be_asked_again(stand_in, tmp_path):
    states, respond = make_states(["right"])
    path = tmp_path / "answers.jsonl"
    run(states, stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (500, {})), path, client={"attempts": 1})
    run(states, stand_in(respond), path)                       # failed records count as saved: nothing asked
    assert all(r["failed"] for r in model_run.read_saved(path))
    run(states, stand_in(respond), path, retry_failed=True)
    records = model_run.read_saved(path)
    assert len(records) == 5 and not any(r["failed"] for r in records)


def test_a_malformed_reply_is_recorded_as_failed(stand_in, tmp_path):
    states, _ = make_states(["right"])
    run(states[:1], stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (200, {"choices": []})),
        tmp_path / "answers.jsonl")
    assert all(r["failed"] and "BadReply" in r["error"] for r in model_run.read_saved(tmp_path / "answers.jsonl"))


def test_an_error_in_our_own_code_is_not_retried(stand_in, tmp_path, monkeypatch):
    states, respond = make_states(["right"])
    server = stand_in(respond)
    monkeypatch.setattr(model_run, "build_question", lambda cube: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        run(states, server, tmp_path / "answers.jsonl")
    assert chats(server) == []


def test_reasoning_may_come_under_either_name(stand_in, tmp_path):
    states, _ = make_states(["right"])
    reply = chat_reply("MOVE: R'", reasoning=None)
    reply["choices"][0]["message"]["reasoning"] = "thought under the other name"
    run(states, stand_in(lambda p, r: tokenize(r) if p == "/tokenize" else (200, reply)), tmp_path / "answers.jsonl")
    assert model_run.read_saved(tmp_path / "answers.jsonl")[0]["thinking"] == "thought under the other name"


def test_token_counts_without_ids_are_left_empty(stand_in, tmp_path):
    states, respond = make_states(["right"])

    def no_ids(path, request):
        status, reply = respond(path, request)
        if path == "/tokenize":
            return 200, {"count": 3, "tokens": [5, 6, 7]}            # '</think>' is not one token here
        return status, reply
    run(states, stand_in(no_ids), tmp_path / "answers.jsonl")
    record = model_run.read_saved(tmp_path / "answers.jsonl")[0]
    assert record["thinking_tokens"] is None and record["answer_tokens"] is None and record["generated_tokens"] > 0
    assert model_run.split_token_count(None, 9) == (None, None)


def test_count_tokens_and_the_key_is_sent(stand_in):
    states, respond = make_states(["right"])
    server = stand_in(respond)
    client = ModelServer(server.base_url + "/", "m", api_key="secret-for-test")
    assert client.count_tokens("a b c") == 13
    assert server.requests[0] == ("/tokenize", {"model": "m", "prompt": "a b c", "add_special_tokens": False})
    assert server.headers[0]["Authorization"] == "Bearer secret-for-test"


def test_request_seeds_are_fixed_by_state_and_try():
    assert model_run.request_seed(1, "test-02-0001", 1) == model_run.request_seed(1, "test-02-0001", 1)
    assert model_run.request_seed(1, "test-02-0001", 1) != model_run.request_seed(1, "test-02-0001", 2)
    assert model_run.request_seed(1, "test-02-0001", 1) != model_run.request_seed(2, "test-02-0001", 1)
