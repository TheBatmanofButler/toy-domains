"""Tests of how model_run.py saves answers: one write at a time, nothing lost when our own code fails while
requests are in flight, and failed records removed without risk to the saved ones."""
import json
import os
import threading
import time

import pytest
from stand_in_server import SETTINGS, make_states, stand_in  # noqa: F401

from cube_ladder import model_run
from cube_ladder.model_server import ModelServer


def run(states, server, path, workers):
    client = ModelServer(server.base_url, "test-model", wait_seconds=0)
    return model_run.run(states, [client], path, 5, SETTINGS, "test-model@abc123", run_seed=3, workers=workers,
                         log=lambda *_: None)


def test_one_answer_is_written_at_a_time(stand_in, tmp_path, monkeypatch):
    # Saving an answer ends with fsync; made slow here, two threads saving at once would overlap inside it.
    states, respond = make_states(["right", "wrong", "unreadable", "right"], distances=(2, 3))
    lock, inside, most = threading.Lock(), [0], [0]
    real_fsync = os.fsync

    def slow_fsync(fd):
        with lock:
            inside[0] += 1
            most[0] = max(most[0], inside[0])
        time.sleep(0.02)
        real_fsync(fd)
        with lock:
            inside[0] -= 1
    monkeypatch.setattr(model_run.os, "fsync", slow_fsync)
    run(states, stand_in(respond), tmp_path / "answers.jsonl", workers=6)
    assert most[0] == 1
    assert len(model_run.read_saved(tmp_path / "answers.jsonl")) == 20


def test_an_error_in_our_own_code_keeps_the_file_open_until_started_answers_are_saved(stand_in, tmp_path,
                                                                                         monkeypatch):
    # The first job fails at once in our own code; those started beside it are still waiting on the server.
    # The run stops, but they must be saved before the file is closed.
    states, respond = make_states(["right", "wrong", "unreadable", "right"], distances=(2, 3))
    first_state, first_try = model_run.order_of_asking(states, 5, 3)[0]
    real_ask, started = model_run.ask, []

    def ask(server, state, try_number, *rest):
        if (state["id"], try_number) == (first_state["id"], first_try):
            raise ZeroDivisionError("an error in our own code")
        started.append((state["id"], try_number))
        time.sleep(0.2)
        return real_ask(server, state, try_number, *rest)
    monkeypatch.setattr(model_run, "ask", ask)
    with pytest.raises(ZeroDivisionError):
        run(states, stand_in(respond), tmp_path / "answers.jsonl", workers=4)
    time.sleep(0.3)        # had the file been closed early, the threads would have finished by now, unsaved
    saved = [(r["state_id"], r["try"]) for r in model_run.read_saved(tmp_path / "answers.jsonl")]
    assert len(started) >= 3 and sorted(saved) == sorted(started)


def test_removing_failed_records_keeps_the_others_and_a_kill_midway_loses_nothing(tmp_path, monkeypatch):
    path = tmp_path / "answers.jsonl"
    records = [{"state_id": f"s{n}", "try": 1, "failed": n % 3 == 0} for n in range(9)]
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    before = path.read_bytes()
    real_dumps, calls = json.dumps, []

    def dumps_then_killed(record):
        calls.append(record)
        if len(calls) == 3:
            raise KeyboardInterrupt      # as if the run were stopped in the middle of the rewrite
        return real_dumps(record)
    monkeypatch.setattr(model_run.json, "dumps", dumps_then_killed)
    with pytest.raises(KeyboardInterrupt):
        model_run.drop_failed(path)
    monkeypatch.setattr(model_run.json, "dumps", real_dumps)
    assert path.read_bytes() == before
    kept = model_run.drop_failed(path)
    assert [r["state_id"] for r in kept] == ["s1", "s2", "s4", "s5", "s7", "s8"]
    assert model_run.read_saved(path) == kept
    assert sorted(p.name for p in tmp_path.iterdir()) == ["answers.jsonl"]
