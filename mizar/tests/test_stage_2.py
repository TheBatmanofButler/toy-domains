"""Tests of stage 2 on the made-up library (seed 7: test problems t2_xboole_1 and t4_xboole_1, holding back
t34_basic_0 and t12_basic_0 as options 11 and 27; training problems t3_xboole_0, t5_xboole_0 and t5_xboole_1),
with the stand-in prover at the experiment's limit (4,000): each test problem's held-back option proves its theorem and
is used, the option after it proves it without being used, every other call reaches the clause limit. So both
problems have right options, and search splits its weight between two options. Also: the shell limits refused,
the settings recorded and checked on a restart, the version check, the share of calls on which the two runs
disagreed, and the guessing check, printed first when it fails."""
import importlib.util
import json
from pathlib import Path

import pytest
from conftest import MADE_UP, checksums_of
from made_up_outputs import output
from made_up_prover import table

from mizar_ladder import prover
from mizar_ladder.problems import read_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def key_scenario(test, limit=prover.LIMIT):
    """At `limit`, as above: the held-back option proves the theorem and is used, the option after it proves it
    without being used."""
    found = {}
    for p in test:
        names = [o["name"] for o in p["options"]]
        found[p["theorem"]] = {limit: ("clause limit", {names[p["held_back"] - 1]: ("proved", True),
                                                       names[p["held_back"] % 30]: ("proved", False)})}
    return found


def stage_1_data(tmp_path):
    """Stage 1 on the made-up library, seed 7, 2 test and 3 training problems; returns the data folder and the
    checksums file."""
    checksums = tmp_path / "checksums.json"
    checksums.write_text(json.dumps(checksums_of(MADE_UP)))
    data = tmp_path / "data"
    stage("1_build_problems").main(["--data", str(data), "--library", str(MADE_UP), "--seed", "7", "--test-count",
                                    "2", "--checksums", str(checksums)])
    return data, checksums


def the_prover(stand_in_prover, data):
    test = read_jsonl(data / "test_problems.jsonl")
    return stand_in_prover(table(key_scenario(test)) + [([], output("clause limit"))])


def stage_2(data, checksums, program, seed="7", more=()):
    stage("2_programs_and_prover").main(["--data", str(data), "--library", str(MADE_UP), "--prover", program,
                                         "--seed", seed, "--checksums", str(checksums), "--workers", "2", *more])


def test_stage_2_worked_by_hand(tmp_path, stand_in_prover, capsys):
    data, checksums = stage_1_data(tmp_path)
    program = the_prover(stand_in_prover, data)
    capsys.readouterr()
    stage_2(data, checksums, program)
    assert not (data / "limit_probe.json").exists() and not (data / "raw" / "limit_probe").exists()
    settings = json.loads((data / "settings.json").read_text())
    assert settings["limit"] == 4000 == prover.LIMIT and settings["seed"] == 7 and settings["prover_environment"] == prover.ENVIRONMENT
    assert settings["prover_version"] == prover.VERSION and "address_layout" not in settings
    key = read_jsonl(data / "prover_key.jsonl")
    assert [(k["bin"], k["right"], k["proved_without_use"]) for k in key] == [
        ("has right options", [11], [12]), ("has right options", [27], [28])]
    picks = read_jsonl(data / "program_picks.jsonl")
    assert sorted({p["program"] for p in picks}) == ["guessing", "lookup", "options_only", "recall",
                                                     "search", "surface_symbols", "surface_trained"]
    search = [p for p in picks if p["program"] == "search"]
    assert [p["score"] for p in search] == [0.5, 0.5]
    summary = json.loads((data / "programs_summary.json").read_text())
    assert summary["failed_checks"] == [] and summary["prover_bins"]["has right options"] == 2
    printed = capsys.readouterr().out
    lines = printed.splitlines()
    every = summary["scores"]["all problems"]["programs"]
    for line, name in zip(lines, ("options_only", "recall")):                       # printed first
        assert line == (f"{name} sits {every[name] - every['guessing']:+.3f} above guessing "
                        f"({every[name]:.3f} against {every['guessing']:.3f})")
    assert "limit: 4000 processed clauses (the experiment's)" in printed
    assert all(c["limit"] == 4000 for c in read_jsonl(data / "prover_calls.jsonl"))
    # Counted together: search puts exactly half its weight on the right option, so it gets neither problem, and
    # no other program puts more than half on it.
    assert summary["counted_together"]["all problems"] == {
        "problems": 2, "best_single_program": 0, "best_single_programs": sorted(every), "at_least_one_program": 0,
        "no_program": 2}
    assert printed.index("Counted together") > printed.index("surface_trained")
    assert "problems whose call with the held-back fact ended as nothing left: 0" in printed
    assert summary["held_back_call_nothing_left"] == 0
    assert json.loads((data / "settled.json").read_text())["unsettled"] == 0
    # The runs disagreed on no call of the key.
    assert summary["runs_disagreed"] == {"key": 0, "key_calls": 62,
                                         "key_by_way": {"the endings differed": 0, "the use of the option differed": 0}}
    assert "calls on which the two runs disagreed: 0.000 of the key's 62" in printed


def test_another_limit_makes_the_key_at_that_limit_and_a_restart_with_another_is_refused(tmp_path, stand_in_prover,
                                                                                       capsys):
    # The stand-in answers the key's table only at 500: with --limit 500 both problems have right options, as at
    # the default limit above; every call carries 500, and so does settings.json.
    data, checksums = stage_1_data(tmp_path)
    test = read_jsonl(data / "test_problems.jsonl")
    program = stand_in_prover(table(key_scenario(test, 500)) + [([], output("clause limit"))])
    stage_2(data, checksums, program, more=["--limit", "500"])
    assert json.loads((data / "settings.json").read_text())["limit"] == 500
    assert {c["limit"] for c in read_jsonl(data / "prover_calls.jsonl")} == {500}
    assert [k["bin"] for k in read_jsonl(data / "prover_key.jsonl")] == ["has right options"] * 2
    assert json.loads((data / "programs_summary.json").read_text())["limit"] == 500
    assert "limit: 500 processed clauses (not the experiment's 4000)" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="other settings: limit"):
        stage_2(data, checksums, program)                                   # the default, 4,000
    assert stage("2_programs_and_prover").settings(7, program, None)["limit"] == prover.LIMIT


def test_shell_limits_are_refused(tmp_path, monkeypatch):
    module = stage("2_programs_and_prover")
    monkeypatch.setattr(module, "shell_limits", lambda: {"computing time": 3600, "address space": "unlimited",
                                                         "data": "unlimited"})
    with pytest.raises(SystemExit, match="REFUSED: the shell limits computing time to 3600"):
        module.main(["--data", str(tmp_path), "--library", str(MADE_UP), "--prover", "p", "--seed", "7"])
    assert all(v == "unlimited" or isinstance(v, int) for v in module.shell_limits().values())


def test_a_wrong_version_and_other_settings_stop_the_stage(tmp_path, stand_in_prover):
    data, checksums = stage_1_data(tmp_path)
    with pytest.raises(SystemExit, match="STOP: the prover reports 'E 2.5'"):
        stage_2(data, checksums, stand_in_prover([], version="E 2.5"))
    program = the_prover(stand_in_prover, data)
    stage_2(data, checksums, program)
    with pytest.raises(SystemExit, match="other settings: seed"):
        stage_2(data, checksums, program, seed="8")


def test_an_unsettled_call_and_nothing_left_with_the_held_back_fact(tmp_path, stand_in_prover):
    # At the limit: test-0001 (t2_xboole_1, holding back option 11) does not prove the theorem without an option
    # (nothing left), proves it with the held-back fact, and its option 20 reaches the clause limit in the first
    # run and the time cap in the second (unsettled: 1 of the key's 62 calls). test-0002 (t4_xboole_1, option 27):
    # nothing left without an option and with the held-back fact; every other option reaches the clause limit.
    # So one held-back call ended as nothing left (two calls without an option did), and test-0002 has no option
    # that proves it.
    data, checksums = stage_1_data(tmp_path)
    test = read_jsonl(data / "test_problems.jsonl")
    one, two = ([o["name"] for o in p["options"]] for p in test)
    key = {test[0]["theorem"]: {prover.LIMIT: ("nothing left", {one[10]: ("proved", True),
                                                                one[19]: (("first time", "clause limit", "time cap"),
                                                                          False)})},
           test[1]["theorem"]: {prover.LIMIT: ("nothing left", {two[26]: ("nothing left", False)})}}
    program = stand_in_prover(table(key) + [([], output("clause limit"))])
    stage_2(data, checksums, program)
    summary = json.loads((data / "programs_summary.json").read_text())
    assert summary["failed_checks"] == [] and summary["held_back_call_nothing_left"] == 1
    assert summary["prover_bins"] == {"proved without an option": 0, "has right options": 1, "no option proves it": 1,
                                      "stopped for another reason": 0}
    settled = json.loads((data / "settled.json").read_text())
    assert settled["unsettled_calls"] == [{"problem_id": "test-0001", "option": 20, "option_name": one[19],
                                           "why": "the endings differed",
                                           "endings": ["clause limit", "time cap"]}]
    assert summary["runs_disagreed"]["key"] == pytest.approx(1 / 62)
    calls = read_jsonl(data / "prover_calls.jsonl")
    assert calls[20]["option"] == 20 and calls[20]["ending"] == "unsettled"


def test_the_guessing_check_is_exact(tmp_path, stand_in_prover, monkeypatch, capsys):
    data, checksums = stage_1_data(tmp_path)
    program = the_prover(stand_in_prover, data)
    module = stage("2_programs_and_prover")
    test = read_jsonl(data / "test_problems.jsonl")

    def nearly(problems):
        # A thousandth more on the held-back option than on the others.
        picks = []
        for p in problems:
            weights = [(1 - 0.031) / 29] * 30
            weights[p["held_back"] - 1] = 0.031
            picks.append(weights)
        return picks
    monkeypatch.setattr(module.guessing, "picks", nearly)
    capsys.readouterr()
    with pytest.raises(SystemExit, match="checks on the programs or the prover failed"):
        module.main(["--data", str(data), "--library", str(MADE_UP), "--prover", program, "--seed", "7",
                     "--checksums", str(checksums)])
    assert capsys.readouterr().out.startswith("FAILED CHECK: guessing scores 0.031")
    assert len(test) == 2
