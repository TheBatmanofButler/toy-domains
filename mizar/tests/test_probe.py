"""Tests of probe/probe.py without a server: which 32 problems it takes and the shape of its request."""
import importlib.util
import json
import random
from pathlib import Path

import pytest
from conftest import FIXTURES

PROBE = Path(__file__).resolve().parent.parent / "probe" / "probe.py"


def probe():
    spec = importlib.util.spec_from_file_location("probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def training_ids():
    ids = [f"train-{n:04d}" for n in range(1, 41)]
    random.Random(3).shuffle(ids)
    return ids


def record(problem_id):
    """The fixed real problem, under a training id."""
    return dict(json.loads((FIXTURES / "fixed_problem.json").read_text()), id=problem_id)


def test_it_draws_32_training_problems_with_the_seed():
    train = [{"id": i} for i in training_ids()]
    chosen = [p["id"] for p in probe().choose_problems(train)]
    drawn = random.Random("20261112:thinking probe").sample(sorted(training_ids()), 32)
    assert chosen == sorted(drawn) and len(set(chosen)) == 32
    assert chosen != [f"train-{n:04d}" for n in range(1, 33)]          # not the lowest numbers
    assert [p["id"] for p in probe().choose_problems(train[::-1])] == chosen     # nor the order of the file
    assert [p["id"] for p in probe().choose_problems(train, seed=5)] != chosen


def test_it_refuses_anything_but_training_problems_and_fewer_than_32():
    module = probe()
    train = [{"id": i} for i in training_ids()]
    with pytest.raises(ValueError, match="training"):
        module.choose_problems(train + [{"id": "test-0001"}])
    with pytest.raises(ValueError, match="only 31 training problems"):
        module.choose_problems(train[:31])


def test_the_request_has_no_thinking_budget_and_room_for_64000_tokens():
    module = probe()
    request = module.make_request(record("train-0003"))
    assert "thinking_token_budget" not in request and request["max_tokens"] == 64000
    assert request["chat_template_kwargs"] == {"enable_thinking": True} and request["return_token_ids"] is True
    assert request["temperature"] == 1.0 and request["top_p"] == 0.95 and request["top_k"] == 20
    assert request["messages"][1]["content"].startswith("Statements are written in first-order logic")
    assert request["messages"][1]["content"].endswith("Answer with `FACT: <number>`.")


def test_rows_are_read_from_saved_replies_without_any_right_or_wrong(tmp_path):
    from stand_in_replies import THINK_END, chat_reply
    module = probe()
    problem = record("train-0003")
    finished = module.row(problem, {"reply": chat_reply("FACT: 24"), "seconds": 3.0}, THINK_END)
    assert finished["status"] == "finished" and finished["thinking_tokens"] == 90 and finished["option_readable"]
    assert finished["fact_lines"] == 1 and "right" not in finished
    assert module.row(problem, {"error": "timeout"}, THINK_END)["status"] == "failed"
    assert module.row(problem, {}, THINK_END)["status"] == "not finished within the time"
    rows = module.write_table([problem], str(tmp_path), THINK_END)
    assert rows[0]["status"] == "not finished within the time" and (tmp_path / "probe_table.csv").exists()
