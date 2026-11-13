"""Tests of probe/probe.py without a server: which 32 problems it takes and the shape of its request."""
import importlib.util
import random
from pathlib import Path

import pytest
from conftest import record

PROBE = Path(__file__).resolve().parent.parent / "probe" / "probe.py"


def probe():
    spec = importlib.util.spec_from_file_location("probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def training_ids():
    ids = [f"train-{d}-{n:04d}" for d in range(2, 6) for n in range(1, 13)]
    random.Random(3).shuffle(ids)
    return ids


def test_it_takes_the_eight_lowest_numbers_at_each_depth_of_the_training_set():
    train = [{"id": i, "depth": int(i.split("-")[1])} for i in training_ids()]
    chosen = probe().choose_problems(train)
    assert len(chosen) == 32
    assert sorted(p["id"] for p in chosen) == sorted(f"train-{d}-{n:04d}" for d in range(2, 6) for n in range(1, 9))
    # Asked in the order train-2-0001, train-3-0001, train-4-0001, train-5-0001, train-2-0002, ...
    assert [p["id"] for p in chosen[:5]] == ["train-2-0001", "train-3-0001", "train-4-0001", "train-5-0001",
                                             "train-2-0002"]


def test_it_refuses_anything_but_training_problems_and_a_depth_short_of_eight():
    module = probe()
    train = [{"id": i, "depth": int(i.split("-")[1])} for i in training_ids()]
    with pytest.raises(ValueError, match="training"):
        module.choose_problems(train + [{"id": "test-2-0001", "depth": 2}])
    with pytest.raises(ValueError, match="depth 5"):
        module.choose_problems([p for p in train if not p["id"].startswith("train-5-")] +
                               [{"id": "train-5-0001", "depth": 5}])


def test_the_request_has_no_thinking_budget_and_room_for_64000_tokens():
    module = probe()
    problem = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)", "train-3-0001")
    request = module.make_request(problem)
    assert "thinking_token_budget" not in request and request["max_tokens"] == 64000
    assert request["chat_template_kwargs"] == {"enable_thinking": True} and request["return_token_ids"] is True
    assert request["temperature"] == 1.0 and request["top_p"] == 0.95 and request["top_k"] == 20
    assert request["messages"][1]["content"].startswith("Let f be an unknown function")
    assert "Goal: prove the identity f(3x) - 3f(x) = 0" in request["messages"][1]["content"]


def test_rows_are_read_from_saved_replies_without_any_right_or_wrong(tmp_path):
    from stand_in_replies import THINK_END, chat_reply
    module = probe()
    problem = record("f(x + y) = f(x) + f(y)", "f(3x) = 3f(x)", "train-3-0001")
    finished = module.row(problem, {"reply": chat_reply("MOVE: (1) y=x"), "seconds": 3.0}, THINK_END)
    assert finished["status"] == "finished" and finished["thinking_tokens"] == 90 and finished["move_readable"]
    assert "right" not in finished
    assert module.row(problem, {"error": "timeout"}, THINK_END)["status"] == "failed"
    assert module.row(problem, {}, THINK_END)["status"] == "not finished within the time"
    rows = module.write_table([problem], str(tmp_path), THINK_END)
    assert rows[0]["status"] == "not finished within the time" and (tmp_path / "probe_table.csv").exists()
