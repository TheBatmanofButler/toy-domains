"""Tests of how model_run.py saves answers: one write at a time, nothing lost when our own code fails while
requests are in flight, and failed records removed without risk to the saved ones."""
import json
import os
import threading
import time

import pytest
from stand_in_server import SETTINGS, make_problems, stand_in  # noqa: F401

from mizar_ladder import model_run
from mizar_ladder.model_server import ModelServer


def run(problems, server, path, workers):
    client = ModelServer(server.base_url, "test-model", wait_seconds=0)
    return model_run.run(problems, [client], path, 5, SETTINGS, "test-model@abc123", run_seed=3, workers=workers,
                         log=lambda *_: None)


def test_one_answer_is_written_at_a_time(stand_in, tmp_path, monkeypatch):
    # Saving an answer ends with fsync; made slow here, two threads saving at once would overlap inside it.
    problems, respond = make_problems(["right", "wrong", "unreadable", "right"])
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
    run(problems, stand_in(respond), tmp_path / "answers.jsonl", workers=6)
    assert most[0] == 1
    assert len(model_run.read_saved(tmp_path / "answers.jsonl")) == 20


def test_an_error_in_our_own_code_keeps_the_file_open_until_started_answers_are_saved(stand_in, tmp_path,
                                                                                         monkeypatch):
    # The first job fails at once in our own code; those started beside it are still waiting on the server.
    # The run stops, but they must be saved before the file is closed.
    problems, respond = make_problems(["right", "wrong", "unreadable", "right"])
    first_problem, first_try = model_run.order_of_asking(problems, 5, 3)[0]
    real_ask, started = model_run.ask, []

    def ask(server, problem, try_number, *rest):
        if (problem["id"], try_number) == (first_problem["id"], first_try):
            raise ZeroDivisionError("an error in our own code")
        started.append((problem["id"], try_number))
        time.sleep(0.2)
        return real_ask(server, problem, try_number, *rest)
    monkeypatch.setattr(model_run, "ask", ask)
    with pytest.raises(ZeroDivisionError):
        run(problems, stand_in(respond), tmp_path / "answers.jsonl", workers=4)
    time.sleep(0.3)        # had the file been closed early, the threads would have finished by now, unsaved
    saved = [(r["problem_id"], r["try"]) for r in model_run.read_saved(tmp_path / "answers.jsonl")]
    assert len(started) >= 3 and sorted(saved) == sorted(started)


def test_removing_failed_records_keeps_the_others_and_a_kill_midway_loses_nothing(tmp_path, monkeypatch):
    path = tmp_path / "answers.jsonl"
    records = [{"problem_id": f"s{n}", "try": 1, "failed": n % 3 == 0} for n in range(9)]
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
    assert [r["problem_id"] for r in kept] == ["s1", "s2", "s4", "s5", "s7", "s8"]
    assert model_run.read_saved(path) == kept
    assert sorted(p.name for p in tmp_path.iterdir()) == ["answers.jsonl"]
