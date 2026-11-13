"""Tests of stage 3's own work around the run: the check made once, failed first answers asked again before
the check, the servers and price the check file records, the token counts, the same address given twice, and
a server that hangs. The thinking budget's part in stage 3 is tested in test_stage_3_budget.py."""
import importlib.util
import json
import threading
from pathlib import Path

import pytest
from stand_in_server import SETTINGS, make_states, stand_in  # noqa: F401

from cube_ladder import model_run
from cube_ladder.model_server import ModelServer
from cube_ladder.states import read_jsonl, write_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"


def stage_3_module():
    spec = importlib.util.spec_from_file_location("stage_3", STAGES / "3_model_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_3(folder, servers, *options):
    module = stage_3_module()
    urls = [part for server in servers for part in ("--base-url", getattr(server, "base_url", server))]
    defaults = {"--price-per-hour": "1", "--check-after": "12"}
    given = dict(zip(options[::2], options[1::2]))
    extra = [part for name, value in defaults.items() if name not in given for part in (name, value)]
    module.main(["--data", str(folder), *urls, "--model-name", "m", "--model-version", "m@1", "--settings",
                 str(folder / "settings.json"), "--seed", "1", "--workers", "2", "--wait-seconds", "0", *extra,
                 *options])


def four_states(folder):
    """Four states the stand-in always answers right (5 tries: 20 answers), and the settings file."""
    states, respond = make_states(["right"] * 4, distances=(2, 3))
    write_jsonl(folder / "test_states.jsonl", states)
    (folder / "settings.json").write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    return respond


def down(path, request):
    return 500, {"error": "down"}


def check_file(folder):
    return json.loads((folder / "model_run_check.json").read_text())


def saved(folder):
    return model_run.read_saved(folder / "model_answers.jsonl")


def test_a_passed_check_is_not_made_again_with_twice_the_servers_and_twice_the_price(tmp_path, stand_in, capsys):
    respond = four_states(tmp_path)
    chats = []

    def fails_after_the_check(path, request):     # answers the first 12 questions, then is down
        if path != "/tokenize":
            chats.append(path)
            if len(chats) > 12:
                return down(path, request)
        return respond(path, request)
    with pytest.raises(SystemExit, match="--retry-failed"):
        stage_3(tmp_path, [stand_in(fails_after_the_check)])
    first = (tmp_path / "model_run_check.json").read_bytes()
    result = json.loads(first)
    assert result["passed"] and result["price_per_hour"] == 1 and not result["carried_on"]
    # At twice the price the same speed would project twice the cost, above this ceiling: the check is not
    # made again, so the run does not stop and the file is not touched.
    ceiling = str(1.5 * result["projected_cost"])
    stage_3(tmp_path, [stand_in(respond), stand_in(respond)], "--price-per-hour", "2", "--cost-ceiling", ceiling,
            "--retry-failed")
    assert (tmp_path / "model_run_check.json").read_bytes() == first
    assert "check made earlier on 12 answers (passed); see model_run_check.json" in capsys.readouterr().out
    assert len(saved(tmp_path)) == 20 and not any(r["failed"] for r in saved(tmp_path))


def test_a_down_server_among_the_first_answers_then_retry_failed_checks_a_full_set(tmp_path, stand_in, capsys):
    respond = four_states(tmp_path)
    broken, alive = stand_in(down), stand_in(respond)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [broken, alive])
    result = check_file(tmp_path)
    assert not result["passed"] and "incomplete records" in result["problems"][0]
    # The token counts came from the server that answers, found once: the down server was tried once for
    # the end-of-thinking tokens and once for the counts (3 attempts each), not once for every count.
    assert result["tokens_per_cube_string"] == 11
    assert [p for p, _ in broken.requests].count("/tokenize") == 6
    assert sum(r["failed"] for r in saved(tmp_path)) == 6
    again = stand_in(respond)
    stage_3(tmp_path, [again], "--retry-failed")
    result = check_file(tmp_path)
    assert result["passed"] and result["answers_checked"] == 12
    assert result["servers"] == sorted([alive.base_url, again.base_url]) and result["servers_given"] == [again.base_url]
    first = saved(tmp_path)[:12]
    assert not any(r["failed"] for r in first) and len({(r["state_id"], r["try"]) for r in first}) == 12
    assert {(s["id"], t) for s, t in model_run.order_of_asking(read_jsonl(tmp_path / "test_states.jsonl"),
                                                               5, 1)[:12]} == {(r["state_id"], r["try"]) for r in first}
    assert "check after 12 answers: the other three checks hold" in capsys.readouterr().out
    assert len(saved(tmp_path)) == 20 and not any(r["failed"] for r in saved(tmp_path))


def test_the_servers_recorded_are_those_of_the_answers_checked(tmp_path, stand_in):
    respond = four_states(tmp_path)
    states = read_jsonl(tmp_path / "test_states.jsonl")
    one, two, three = stand_in(respond), stand_in(respond), stand_in(respond)
    for server, limit in ((one, 12), (two, 4)):   # 16 answers saved before any check was made
        model_run.run(states, [ModelServer(server.base_url, "m", wait_seconds=0)], tmp_path / "model_answers.jsonl",
                      5, SETTINGS, "m@1", 1, limit=limit, log=lambda *_: None)
    stage_3(tmp_path, [three], "--price-per-hour", "3")
    result = check_file(tmp_path)
    assert result["servers"] == [one.base_url] and result["servers_given"] == [three.base_url]
    assert result["price_per_hour"] == 3 and result["answers_checked"] == 12


def test_a_failed_check_is_made_again_on_the_next_start(tmp_path, stand_in):
    respond = four_states(tmp_path)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12")
    assert not check_file(tmp_path)["passed"] and len(saved(tmp_path)) == 12
    stage_3(tmp_path, [stand_in(respond)])          # the cause put right: a ceiling that fits
    assert check_file(tmp_path)["passed"] and check_file(tmp_path)["cost_ceiling"] == 300
    assert len(saved(tmp_path)) == 20


def test_a_check_carried_on_is_recorded_and_not_made_again(tmp_path, stand_in, capsys):
    respond = four_states(tmp_path)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12", "--tries", "4")
    stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12", "--tries", "4", "--carry-on")
    result = check_file(tmp_path)
    assert not result["passed"] and result["carried_on"] and result["cost_ceiling"] == 1e-12
    assert "check made earlier on 12 answers (failed); carried on with --carry-on" in capsys.readouterr().out
    assert len(saved(tmp_path)) == 16
    before = (tmp_path / "model_run_check.json").read_bytes()
    stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12")     # without --carry-on: not made again
    assert (tmp_path / "model_run_check.json").read_bytes() == before
    assert "check made earlier on 12 answers (failed, carried on)" in capsys.readouterr().out
    assert len(saved(tmp_path)) == 20


def test_carry_on_at_the_first_check_is_recorded(tmp_path, stand_in):
    respond = four_states(tmp_path)
    stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12", "--carry-on")
    assert not check_file(tmp_path)["passed"] and check_file(tmp_path)["carried_on"]
    assert len(saved(tmp_path)) == 20


def test_the_same_address_given_twice_is_refused(tmp_path, stand_in):
    respond = four_states(tmp_path)
    server = stand_in(respond)
    with pytest.raises(SystemExit, match="the same server address is given twice"):
        stage_3(tmp_path, [server, server.base_url + "/"])
    assert server.requests == [] and not (tmp_path / "model_answers.jsonl").exists()


def test_a_server_that_hangs_gives_failed_records_after_the_timeout(tmp_path, stand_in):
    respond = four_states(tmp_path)
    released = threading.Event()

    def hangs(path, request):
        released.wait(timeout=5)
        return respond(path, request)
    hanging, alive = stand_in(hangs), stand_in(respond)
    try:
        with pytest.raises(SystemExit, match="STOP"):
            stage_3(tmp_path, [hanging, alive], "--timeout", "0.2", "--check-after", "4", "--tries", "1")
    finally:
        released.set()
    records = saved(tmp_path)
    assert sorted(r["server"] for r in records) == sorted([hanging.base_url, alive.base_url] * 2)
    assert all(r["failed"] and "timed out" in r["error"] for r in records if r["server"] == hanging.base_url)
    assert not any(r["failed"] for r in records if r["server"] == alive.base_url)
