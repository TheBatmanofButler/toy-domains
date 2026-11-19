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

from mizar_ladder import report, run_settings, scoring
from mizar_ladder.problems import write_jsonl

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
    (folder / "raw").mkdir()
    write_jsonl(folder / "raw" / "model_answers.jsonl", answers)
    # The prover's key: the held-back option right on the first five problems, no option on the other five.
    write_jsonl(folder / "prover_key.jsonl", [
        {"problem_id": p["id"], "bin": "has right options" if p["held_back"] <= 5 else "no option proves it",
         "right": [p["held_back"]] if p["held_back"] <= 5 else [], "proved_without_use": []} for p in problems])
    (folder / "settled.json").write_text(json.dumps({"calls": 310, "unsettled": 3, "unsettled_share": 3 / 310}))
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
    expected = json.loads(json.dumps(scoring.scores_by_row(problems, picks, answers)))
    assert json.loads((data / "scores.json").read_text()) == expected
    assert json.loads((data / "problem_by_problem.json").read_text()) == json.loads(
        json.dumps(scoring.problem_by_problem(problems, picks, answers)))
    assert set(json.loads((data / "wrong_answers.json").read_text())) == {"guessing", "recall"}
    assert (data / "bars.svg").read_text().startswith("<svg")
    # The second table: on the first five problems both keys agree, so the three scores are the same.
    second = json.loads((data / "second_table.json").read_text())
    assert second["problems"] == 5 and second["bins"]["no option proves it"] == 5
    assert second["model"]["prover"] == second["model"]["author"] == second["model"]["either"]
    assert second["model"]["prover"]["mean"] == pytest.approx(0.56)
    assert second["runs_disagreed_share"] == pytest.approx(3 / 310)
    assert "The second table" in (data / "report.txt").read_text()
    # The budgets table carries the one allowance the answers share.
    assert report.budgets_text(expected, 8000) in (data / "report.txt").read_text()
    assert "STOP" not in capsys.readouterr().out


def test_run_twice_the_stage_writes_the_same_files(tmp_path):
    data = data_folder(tmp_path, with_settings(made_up()[2]))
    stage_4(["--data", str(data)])
    first = {name: (data / name).read_bytes() for name in ("scores.json", "problem_by_problem.json",
                                                            "wrong_answers.json", "second_table.json", "report.txt",
                                                            "bars.svg")}
    stage_4(["--data", str(data)])
    assert {name: (data / name).read_bytes() for name in first} == first


OUTPUTS = ("scores.json", "problem_by_problem.json", "counted_together.json", "wrong_answers.json",
           "second_table.json", "report.txt", "bars.svg")


def named_and_renamed(folder):
    """The named answers (with request seeds), and the same problems and tries asked again renamed: the same
    settings and request seeds, marked renamed, each with the renamed question of its problem, and every answer
    on an odd try made wrong (option 30 is no problem's held-back fact here). Writes the data folder with the
    named answers, and test_problems_renamed.jsonl."""
    from mizar_ladder.question import build_question
    answers = [dict(a, request_seed=1000 + n) for n, a in enumerate(with_settings(made_up()[2]))]
    data = data_folder(folder, answers)
    problems = {p["id"]: dict(p, renamed=True, statement=f"s00001({p['id'].upper()})",
                              given=[{"statement": "s00002(A)"}], options=[{"statement": f"s00003(A{n})"}
                                                                           for n in range(30)])
                for p in made_up()[0]}
    write_jsonl(data / "test_problems_renamed.jsonl", list(problems.values()))
    renamed = [dict(a, settings=dict(a["settings"], renamed=True), question=build_question(problems[a["problem_id"]]),
                    answer_text=a["answer_text"] if a["try"] % 2 == 0 else "FACT: 30") for a in answers]
    return data, answers, renamed


def test_renamed_answers_add_a_section_and_change_nothing_else(tmp_path):
    from mizar_ladder import renaming
    data, answers, renamed = named_and_renamed(tmp_path)
    stage_4(["--data", str(data)])
    before = {name: (data / name).read_bytes() for name in OUTPUTS}
    assert not (data / "renamed.json").exists()
    write_jsonl(data / "raw" / "model_answers_renamed.jsonl", renamed)
    stage_4(["--data", str(data)])
    after = {name: (data / name).read_bytes() for name in OUTPUTS}
    unchanged = [name for name in OUTPUTS if name != "report.txt"]
    assert {k: after[k] for k in unchanged} == {k: before[k] for k in unchanged}
    text = after["report.txt"].decode()
    assert text.startswith(before["report.txt"].decode()[:-1] + "\n\nNamed against renamed:")
    problems, picks, _ = made_up()
    expected = renaming.named_against_renamed(problems, picks, answers, renamed)
    assert json.loads((data / "renamed.json").read_text()) == json.loads(json.dumps(expected))
    assert report.renamed_text(json.loads(json.dumps(expected))) in text
    # Taken away again: the files are those of before, and the renamed.json left from the earlier run is removed.
    (data / "raw" / "model_answers_renamed.jsonl").unlink()
    stage_4(["--data", str(data)])
    assert {name: (data / name).read_bytes() for name in OUTPUTS} == before
    assert not (data / "renamed.json").exists()


def other_seed(renamed):
    return [dict(r, request_seed=7) if n == 4 else r for n, r in enumerate(renamed)]


def other_question(renamed):
    return [dict(r, question=r["question"].replace("meaningless code", "code")) if n == 6 else r
            for n, r in enumerate(renamed)]


@pytest.mark.parametrize("change, message", [
    (lambda renamed: renamed[:-1], "STOP: the renamed answers: .*missing"),
    (lambda renamed: [dict(r, settings=dict(r["settings"], stop_sentence="Other.")) if n < 3 else r
                      for n, r in enumerate(renamed)], "STOP: the renamed answers: .*stop_sentence"),
    (lambda renamed: [dict(r, settings=dict(r["settings"], source="another")) for r in renamed],
     "STOP: the renamed answers: .*not asked under the same settings"),
    (other_seed, "STOP: the renamed answers: p1 try 5: request seed 7, the named answer's 1004$"),
    (other_question, "STOP: the renamed answers: p2 try 2: its question is not the renamed question of its problem"),
    (lambda renamed: [dict(r, question=r["question"].replace("replaced by a meaningless code, the same code wherever "
                                                             "the symbol appears", "written as its name in the Mizar "
                                                             "Mathematical Library")) for r in renamed],
     "its question is not the renamed question"),
])
def test_renamed_answers_that_do_not_pair_stop_the_stage(tmp_path, change, message):
    data, _, renamed = named_and_renamed(tmp_path)
    write_jsonl(data / "raw" / "model_answers_renamed.jsonl", change(renamed))
    with pytest.raises(SystemExit, match=message):
        stage_4(["--data", str(data)])
    assert not (data / "renamed.json").exists()


def at(renamed, allowance):
    return [dict(r, settings=dict(r["settings"], thinking_allowance=allowance)) for r in renamed]


def test_a_renamed_run_at_another_allowance_without_and_with_the_plain_one(tmp_path):
    from mizar_ladder import renaming
    data, answers, renamed = named_and_renamed(tmp_path)
    stage_4(["--data", str(data)])
    before = {name: (data / name).read_bytes() for name in OUTPUTS}
    problems, picks, _ = made_up()
    # One such file only: its section and renamed_t12000.json; nothing else changes but the report's end.
    other = at([dict(r, answer_text="FACT: 30") if r["try"] == 2 else r for r in renamed], 12000)
    write_jsonl(data / "raw" / "model_answers_renamed_t12000.jsonl", other)
    stage_4(["--data", str(data)])
    expected = json.loads(json.dumps(renaming.named_against_renamed(problems, picks, answers, other, allowance=12000)))
    assert json.loads((data / "renamed_t12000.json").read_text()) == expected
    assert not (data / "renamed.json").exists() and not (data / "renamed_t12000_two_allowances.json").exists()
    text = (data / "report.txt").read_text()
    assert text.startswith(before["report.txt"].decode()[:-1] + "\n\nNamed against renamed at a thinking allowance "
                           "of 12000: the same problems")
    assert report.renamed_text(expected) in text and "Renamed at the two allowances" not in text
    assert all((data / name).read_bytes() == before[name] for name in OUTPUTS if name != "report.txt")
    # With the plain renamed answers too: their section first, then this one and the table at the two allowances.
    write_jsonl(data / "raw" / "model_answers_renamed.jsonl", renamed)
    stage_4(["--data", str(data)])
    both = json.loads(json.dumps(renaming.two_allowances(problems, renamed, other)))
    assert json.loads((data / "renamed_t12000_two_allowances.json").read_text()) == both
    text = (data / "report.txt").read_text()
    assert (text.index("Named against renamed:") < text.index("at a thinking allowance of 12000")
            < text.index("Renamed at the two allowances: the named run's and 12000"))
    assert report.two_allowances_text(both) in text
    # Both taken away: the outputs of before, and every renamed file of the earlier runs removed.
    (data / "raw" / "model_answers_renamed.jsonl").unlink()
    (data / "raw" / "model_answers_renamed_t12000.jsonl").unlink()
    stage_4(["--data", str(data)])
    assert {name: (data / name).read_bytes() for name in OUTPUTS} == before
    assert sorted(p.name for p in data.glob("renamed*.json")) == []


@pytest.mark.parametrize("name, allowance, message", [
    ("model_answers_renamed_t9000.jsonl", 12000, "allowance of 9000: answers in the file for a thinking allowance "
                                                 "of 9000 were asked with \\[12000\\]"),
    ("model_answers_renamed_t8000.jsonl", 8000, "model_answers_renamed_t8000.jsonl: the named run's own thinking "
                                               "allowance"),
    ("model_answers_renamed_tx.jsonl", 12000, "model_answers_renamed_tx.jsonl: not a file of a renamed run"),
])
def test_a_wrong_file_of_another_allowance_stops_the_stage(tmp_path, name, allowance, message):
    data, _, renamed = named_and_renamed(tmp_path)
    write_jsonl(data / "raw" / name, at(renamed, allowance))
    with pytest.raises(SystemExit, match="STOP: .*" + message):
        stage_4(["--data", str(data)])


def test_another_allowance_with_a_wrong_seed_or_question_stops_the_stage(tmp_path):
    data, _, renamed = named_and_renamed(tmp_path)
    write_jsonl(data / "raw" / "model_answers_renamed_t12000.jsonl", at(other_seed(renamed), 12000))
    with pytest.raises(SystemExit, match="allowance of 12000: p1 try 5: request seed 7"):
        stage_4(["--data", str(data)])
    write_jsonl(data / "raw" / "model_answers_renamed_t12000.jsonl", at(other_question(renamed), 12000))
    with pytest.raises(SystemExit, match="allowance of 12000: p2 try 2: its question is not"):
        stage_4(["--data", str(data)])
