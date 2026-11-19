"""Tests of stage 3's own work around the run: the check made once, failed first answers asked again before
the check, the servers and price the check file records, the token lookups, the same address given twice, a
server that hangs, and answers saved without how long they took. The thinking budget's part in stage 3 is
tested in test_stage_3_budget.py."""
import importlib.util
import json
import threading
from pathlib import Path

import pytest
from stand_in_replies import chat_reply
from stand_in_server import SETTINGS, make_problems, stand_in  # noqa: F401

from mizar_ladder import model_run
from mizar_ladder.model_server import ModelServer
from mizar_ladder.problems import read_jsonl, write_jsonl

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


def four_problems(folder):
    """Four problems the stand-in always answers right (5 tries: 20 answers), and the settings file."""
    problems, respond = make_problems(["right"] * 4)
    write_jsonl(folder / "test_problems.jsonl", problems)
    (folder / "raw").mkdir(exist_ok=True)
    (folder / "settings.json").write_text(json.dumps({"sampling": {"temperature": 0.6}, "source": "test value"}))
    return respond


def down(path, request):
    return 500, {"error": "down"}


def check_file(folder):
    return json.loads((folder / "model_run_check.json").read_text())


def saved(folder):
    return model_run.read_saved(folder / "raw" / "model_answers.jsonl")


def test_a_passed_check_is_not_made_again_with_twice_the_servers_and_twice_the_price(tmp_path, stand_in, capsys):
    respond = four_problems(tmp_path)
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
    respond = four_problems(tmp_path)
    broken, alive = stand_in(down), stand_in(respond)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [broken, alive])
    result = check_file(tmp_path)
    assert not result["passed"] and "incomplete records" in result["problems"][0]
    # The end-of-thinking tokens came from the server that answers: the down server was tried once for them
    # (3 attempts).
    assert [p for p, _ in broken.requests].count("/tokenize") == 3
    assert sum(r["failed"] for r in saved(tmp_path)) == 6
    again = stand_in(respond)
    stage_3(tmp_path, [again], "--retry-failed")
    result = check_file(tmp_path)
    assert result["passed"] and result["answers_checked"] == 12
    assert result["servers"] == sorted([alive.base_url, again.base_url]) and result["servers_given"] == [again.base_url]
    first = saved(tmp_path)[:12]
    assert not any(r["failed"] for r in first) and len({(r["problem_id"], r["try"]) for r in first}) == 12
    assert {(s["id"], t) for s, t in model_run.order_of_asking(read_jsonl(tmp_path / "test_problems.jsonl"),
                                                               5, 1)[:12]} == {(r["problem_id"], r["try"]) for r in first}
    assert "check after 12 answers: the other three checks hold" in capsys.readouterr().out
    assert len(saved(tmp_path)) == 20 and not any(r["failed"] for r in saved(tmp_path))


def test_the_servers_recorded_are_those_of_the_answers_checked(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    problems = read_jsonl(tmp_path / "test_problems.jsonl")
    one, two, three = stand_in(respond), stand_in(respond), stand_in(respond)
    for server, limit in ((one, 12), (two, 4)):   # 16 answers saved before any check was made
        model_run.run(problems, [ModelServer(server.base_url, "m", wait_seconds=0)], tmp_path / "raw" / "model_answers.jsonl",
                      5, SETTINGS, "m@1", 1, limit=limit, log=lambda *_: None)
    stage_3(tmp_path, [three], "--price-per-hour", "3")
    result = check_file(tmp_path)
    assert result["servers"] == [one.base_url] and result["servers_given"] == [three.base_url]
    assert result["price_per_hour"] == 3 and result["answers_checked"] == 12


def test_a_failed_check_is_made_again_on_the_next_start(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12")
    assert not check_file(tmp_path)["passed"] and len(saved(tmp_path)) == 12
    stage_3(tmp_path, [stand_in(respond)])          # the cause put right: a ceiling that fits
    assert check_file(tmp_path)["passed"] and check_file(tmp_path)["cost_ceiling"] == 300
    assert len(saved(tmp_path)) == 20


def test_a_check_carried_on_is_recorded_and_not_made_again(tmp_path, stand_in, capsys):
    respond = four_problems(tmp_path)
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
    respond = four_problems(tmp_path)
    stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12", "--carry-on")
    assert not check_file(tmp_path)["passed"] and check_file(tmp_path)["carried_on"]
    assert len(saved(tmp_path)) == 20


def test_the_same_address_given_twice_is_refused(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    server = stand_in(respond)
    with pytest.raises(SystemExit, match="the same server address is given twice"):
        stage_3(tmp_path, [server, server.base_url + "/"])
    assert server.requests == [] and not (tmp_path / "raw" / "model_answers.jsonl").exists()


def test_a_server_that_hangs_gives_failed_records_after_the_timeout(tmp_path, stand_in):
    respond = four_problems(tmp_path)
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


def test_answers_saved_without_seconds_stop_the_check_with_a_plain_message(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    with pytest.raises(SystemExit, match="STOP"):
        stage_3(tmp_path, [stand_in(respond)], "--cost-ceiling", "1e-12")
    # As an older file would have them: no `seconds`, so the speed cannot be measured from the first start.
    old = [{k: v for k, v in r.items() if k != "seconds"} for r in saved(tmp_path)]
    write_jsonl(tmp_path / "raw" / "model_answers.jsonl", old)
    with pytest.raises(SystemExit, match="cannot be made: speed cannot be measured: 12 answers were saved without"):
        stage_3(tmp_path, [stand_in(respond)])


def test_stage_3_with_two_servers_and_too_few_forced_answers(tmp_path, stand_in, capsys):
    # From the cube's tests of the stage scripts: four problems, every answer the same readable option.
    respond = four_problems(tmp_path)

    def same_answer(path, request):
        return respond(path, request) if path == "/tokenize" else (200, chat_reply("FACT: 1"))
    servers = [stand_in(same_answer), stand_in(same_answer)]
    stage_3(tmp_path, servers)
    result = check_file(tmp_path)
    assert result["passed"] and result["forced_comparison"] == "not tested" and result["answers_checked"] == 12
    assert result["forced_answers_compared"] == 0 and result["unforced_answers_compared"] == 12
    assert result["servers"] == sorted(s.base_url for s in servers)
    printed = capsys.readouterr().out
    assert "check after 12 answers: the other three checks hold; forced against unforced not tested" in printed
    assert "forced against unforced: not tested (0 forced, 12 unforced answers compared" in printed
    assert ("server's thinking budget: as assumed (0 forced: 0 with the end text after the allowance, 0 with it "
            "inside; 0 that do not fit)") in printed
    assert "20 answers saved of 20" in printed     # the run carried on to the end
    assert sorted(r["server"] for r in saved(tmp_path)) == sorted([s.base_url for s in servers] * 10)


def renamed_copy(folder):
    """test_problems_renamed.jsonl beside test_problems.jsonl: the same records, marked renamed (the stand-in
    knows a problem by its theorem's text, which is left as it is here)."""
    problems = read_jsonl(folder / "test_problems.jsonl")
    write_jsonl(folder / "test_problems_renamed.jsonl", [dict(p, renamed=True) for p in problems])


def named_then_renamed_files(folder, server):
    """The named run (seed 1, 5 tries), then what stage 1b would write for it: named_run.json and the renamed
    problems."""
    from mizar_ladder import renaming
    stage_3(folder, [server])
    named = renaming.named_run(saved(folder), read_jsonl(folder / "test_problems.jsonl"), 1)
    (folder / "named_run.json").write_text(json.dumps(named))
    renamed_copy(folder)
    return named


def test_renamed_writes_only_the_renamed_files_with_the_named_runs_seeds(tmp_path, stand_in):
    from mizar_ladder.question import NOTATION_RENAMED
    respond = four_problems(tmp_path)
    named_files = {}
    named_then_renamed_files(tmp_path, stand_in(respond))
    for name in ("raw/model_answers.jsonl", "model_run_check.json"):
        named_files[name] = (tmp_path / name).read_bytes()
    stage_3(tmp_path, [stand_in(respond)], "--renamed")
    assert {name: (tmp_path / name).read_bytes() for name in named_files} == named_files     # left as they were
    assert json.loads((tmp_path / "model_run_check_renamed.json").read_text())["passed"]
    records = model_run.read_saved(tmp_path / "raw" / "model_answers_renamed.jsonl")
    assert len(records) == 20 and all(r["settings"]["renamed"] is True and r["right"] for r in records)
    assert all(r["question"].startswith(NOTATION_RENAMED + "\n\n") for r in records)
    named = {(r["problem_id"], r["try"]): r for r in saved(tmp_path)}
    assert all(r["request_seed"] == named[(r["problem_id"], r["try"])]["request_seed"] for r in records)
    assert all("renamed" not in r["settings"] for r in named.values())
    assert all({k: v for k, v in r["settings"].items() if k != "renamed"} == named[(r["problem_id"], r["try"])]["settings"]
               for r in records)


@pytest.mark.parametrize("options, message", [
    (("--thinking-allowance", "6000"), "settings differ: thinking_allowance"),
    (("--stop-sentence", "neutral"), "settings differ: end_of_thinking_text, stop_sentence"),
    (("--model-version", "m@2"), "model version 'm@2', the named run's 'm@1'"),
    (("--tries", "4"), "4 tries, the named run's 5"),
    (("--seed", "2"), "request seeds differ \\(run seed 2, the named run's 1\\): the first at test-0001 try 1"),
])
def test_a_renamed_run_unlike_the_named_one_stops_before_its_first_request(tmp_path, stand_in, options, message):
    respond = four_problems(tmp_path)
    named_then_renamed_files(tmp_path, stand_in(respond))
    asked = []

    def counting(path, request):
        asked.append(path)
        return respond(path, request)
    with pytest.raises(SystemExit, match="STOP: the renamed run would not be asked as the named run was: " + message):
        stage_3(tmp_path, [stand_in(counting)], "--renamed", *options)
    assert asked == [] and not (tmp_path / "raw" / "model_answers_renamed.jsonl").exists()


def test_a_renamed_run_needs_named_run_json_and_the_named_runs_problems(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    named_then_renamed_files(tmp_path, stand_in(respond))
    named = json.loads((tmp_path / "named_run.json").read_text())
    (tmp_path / "named_run.json").unlink()
    with pytest.raises(SystemExit, match="named_run.json does not exist"):
        stage_3(tmp_path, [stand_in(respond)], "--renamed")
    named["request_seeds"].pop("test-0004")
    (tmp_path / "named_run.json").write_text(json.dumps(named))
    with pytest.raises(SystemExit, match="the problems are not the named run's"):
        stage_3(tmp_path, [stand_in(respond)], "--renamed")


def test_the_two_kinds_are_never_mixed(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    server = stand_in(respond)
    named_then_renamed_files(tmp_path, server)
    one_named = saved(tmp_path)[0]
    (tmp_path / "raw" / "model_answers_renamed.jsonl").write_text(json.dumps(one_named) + "\n")
    with pytest.raises(SystemExit, match="model_answers_renamed.jsonl holds named answers"):
        stage_3(tmp_path, [server], "--renamed")
    (tmp_path / "raw" / "model_answers.jsonl").write_text(
        json.dumps(dict(one_named, settings=dict(one_named["settings"], renamed=True))) + "\n")
    with pytest.raises(SystemExit, match="model_answers.jsonl holds renamed answers"):
        stage_3(tmp_path, [server])
    write_jsonl(tmp_path / "test_problems_renamed.jsonl", read_jsonl(tmp_path / "test_problems.jsonl"))
    with pytest.raises(SystemExit, match="test_problems_renamed.jsonl holds named problems"):
        stage_3(tmp_path, [server], "--renamed")
    renamed_copy(tmp_path)
    write_jsonl(tmp_path / "test_problems.jsonl", read_jsonl(tmp_path / "test_problems_renamed.jsonl"))
    with pytest.raises(SystemExit, match="test_problems.jsonl holds renamed problems"):
        stage_3(tmp_path, [server])


def test_a_renamed_run_at_another_allowance_writes_its_own_files(tmp_path, stand_in):
    respond = four_problems(tmp_path)
    named_then_renamed_files(tmp_path, stand_in(respond))
    stage_3(tmp_path, [stand_in(respond)], "--renamed")
    plain = {name: (tmp_path / name).read_bytes()
             for name in ("raw/model_answers_renamed.jsonl", "model_run_check_renamed.json")}
    stage_3(tmp_path, [stand_in(respond)], "--renamed", "--other-allowance", "--thinking-allowance", "12000")
    assert {name: (tmp_path / name).read_bytes() for name in plain} == plain          # left as they were
    records = model_run.read_saved(tmp_path / "raw" / "model_answers_renamed_t12000.jsonl")
    assert len(records) == 20 and all(r["settings"]["thinking_allowance"] == 12000 and r["settings"]["renamed"]
                                      for r in records)
    assert json.loads((tmp_path / "model_run_check_renamed_t12000.json").read_text())["passed"]
    named = {(r["problem_id"], r["try"]): r for r in saved(tmp_path)}
    assert all(r["request_seed"] == named[(r["problem_id"], r["try"])]["request_seed"] for r in records)
    assert sorted(p.name for p in (tmp_path / "raw").iterdir()) == [
        "model_answers.jsonl", "model_answers_renamed.jsonl", "model_answers_renamed_t12000.jsonl"]


@pytest.mark.parametrize("options, message", [
    (("--other-allowance", "--thinking-allowance", "12000"), "--other-allowance is for a renamed run only"),
    (("--renamed", "--other-allowance"), "--other-allowance with the named run's own thinking allowance \\(8000\\)"),
    (("--renamed", "--other-allowance", "--thinking-allowance", "12000", "--stop-sentence", "neutral"),
     "settings differ: end_of_thinking_text, stop_sentence"),
    (("--renamed", "--other-allowance", "--thinking-allowance", "12000", "--tries", "4"), "4 tries, the named run's 5"),
    (("--renamed", "--other-allowance", "--thinking-allowance", "12000", "--seed", "2"), "request seeds differ"),
    (("--renamed", "--thinking-allowance", "12000"), "settings differ: thinking_allowance"),   # without the option
])
def test_the_other_allowance_refusals(tmp_path, stand_in, options, message):
    respond = four_problems(tmp_path)
    named_then_renamed_files(tmp_path, stand_in(respond))
    asked = []

    def counting(path, request):
        asked.append(path)
        return respond(path, request)
    with pytest.raises(SystemExit, match=message):
        stage_3(tmp_path, [stand_in(counting)], *options)
    assert asked == [] and sorted(p.name for p in (tmp_path / "raw").iterdir()) == ["model_answers.jsonl"]
