"""Tests of the settings every answer was asked under (run_settings.py), and of stage 4 reading them: answers
asked with two thinking allowances, or by two model versions, stop the stage with a message naming what
differs and how many answers have each value; with one value the stage writes the same figures as before.

The stage runs on scoring's ten made-up problems (test_scoring.py), whose 50 answers are given one set of
settings here; the made-up figures are those of test_scoring.py and test_report.py.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from test_scoring import made_up

from fe_ladder import report, run_settings, scoring
from fe_ladder.problems import write_jsonl

STAGES = Path(__file__).resolve().parent.parent / "stages"
SETTINGS = {"thinking_allowance": 8000, "answer_allowance": 1000, "stop_sentence": "Time to answer.",
            "sampling": {"temperature": 0.6, "top_p": 0.95}, "source": "test value"}


def stage_4(argv):
    spec = importlib.util.spec_from_file_location("4_report", STAGES / "4_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(argv)


def with_settings(answers, settings=SETTINGS, model_version="m@1"):
    return [dict(a, settings=dict(settings), model_version=model_version) for a in answers]


def data_folder(folder, answers):
    problems, picks, _ = made_up()
    write_jsonl(folder / "test_problems.jsonl", problems)
    write_jsonl(folder / "program_picks.jsonl", picks)
    write_jsonl(folder / "model_answers.jsonl", answers)
    (folder / "model_run_check.json").write_text(json.dumps({"tokens_per_equation": 40}))
    return folder


def test_one_set_of_settings_is_returned():
    shared = run_settings.shared_settings(with_settings(made_up()[2]))
    assert shared == {"thinking_allowance": 8000, "answer_allowance": 1000, "stop_sentence": "Time to answer.",
                      "sampling": {"temperature": 0.6, "top_p": 0.95}, "model_version": "m@1"}
    # The same sampling values written in another order are the same values.
    answers = with_settings(made_up()[2])
    answers[0]["settings"]["sampling"] = {"top_p": 0.95, "temperature": 0.6}
    assert run_settings.shared_settings(answers)["sampling"] == SETTINGS["sampling"]


def test_every_difference_is_named_with_its_counts():
    answers = with_settings(made_up()[2])
    for a in answers[:5]:
        a["settings"]["thinking_allowance"] = 6000
        a["settings"]["sampling"] = {"temperature": 1.0}
    answers[7]["model_version"] = "m@2"
    with pytest.raises(run_settings.SettingsDiffer) as differ:
        run_settings.shared_settings(answers)
    assert str(differ.value) == (
        "the answers were not all asked under the same settings; thinking_allowance: 6000 (5 answers), "
        '8000 (45 answers); sampling: {"temperature": 0.6, "top_p": 0.95} (45 answers), {"temperature": 1.0} '
        '(5 answers); model_version: "m@1" (49 answers), "m@2" (1 answer)')
    with pytest.raises(run_settings.SettingsDiffer, match="no answers"):
        run_settings.shared_settings([])


def test_two_thinking_allowances_stop_the_stage(tmp_path):
    answers = with_settings(made_up()[2])
    for a in answers[:3]:
        a["settings"]["thinking_allowance"] = 6000
    data = data_folder(tmp_path, answers)
    with pytest.raises(SystemExit, match=r"STOP: .*thinking_allowance: 6000 \(3 answers\), 8000 \(47 answers\)$"):
        stage_4(["--data", str(data)])
    assert not (data / "report.txt").exists()


def test_two_model_versions_stop_the_stage(tmp_path):
    answers = with_settings(made_up()[2])
    answers[-1]["model_version"] = "m@2"
    data = data_folder(tmp_path, answers)
    with pytest.raises(SystemExit, match=r'STOP: .*model_version: "m@1" \(49 answers\), "m@2" \(1 answer\)$'):
        stage_4(["--data", str(data)])
    assert not (data / "report.txt").exists()


def test_with_one_set_of_settings_the_stage_writes_the_same_figures(tmp_path, capsys):
    problems, picks, answers = made_up()
    data = data_folder(tmp_path, with_settings(answers))
    stage_4(["--data", str(data)])
    # The figures are scoring's on the answers as they were, before any settings were added.
    expected = scoring.scores_by_depth(problems, picks, answers)
    for row in expected.values():
        row["most_identities_written"] = scoring.most_identities_written(row["tokens_used_mean"], 40)
    expected = json.loads(json.dumps(expected))
    assert json.loads((data / "scores_by_depth.json").read_text()) == expected
    # The budgets table carries the one allowance the answers share.
    assert report.budgets_text(expected, 8000) in (data / "report.txt").read_text()
    assert "STOP" not in capsys.readouterr().out
