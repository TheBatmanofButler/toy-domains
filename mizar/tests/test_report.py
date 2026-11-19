"""Tests of report.py: the tables show scoring.py's figures, and the picture is a well-formed SVG."""
import json
import xml.etree.ElementTree as ElementTree
from math import sqrt

import pytest
from test_scoring import CHANCE, made_up
from test_second_table import made_up as made_up_second_table
from test_wrong_answers import made_up as made_up_wrong_answers

from mizar_ladder import report, scoring, second_table, wrong_answers

SVG = "{http://www.w3.org/2000/svg}"


def figures():
    problems, picks, answers = made_up()
    by_row = scoring.scores_by_row(problems, picks, answers)
    # The stage writes the figures as JSON and reads them back.
    return json.loads(json.dumps(by_row)), scoring.problem_by_problem(problems, picks, answers)


def test_scores_table_shows_every_figure():
    by_row, _ = figures()
    lines = report.scores_text(by_row).splitlines()
    assert lines[0].split() == ["row", "problems", "guessing", "recall", "best", "room", "model", "unreadable",
                                "forced", "thinking_tokens"]
    assert lines[2].split() == ["all", "problems", "10", "0.033", "0.633", "recall", "0.367", "0.500", "0.160",
                                "0.140", "2380.000"]
    assert lines[3].split() == ["2", "to", "3", "cited", "5", "0.033", "0.600", "recall", "0.400", "0.560", "0.120",
                                "0.080", "1560.000"]
    assert lines[4].split()[4:] == ["5", "0.033", "0.667", "recall", "0.333", "0.440", "0.200", "0.200", "3200.000"]
    assert [next(name for name in by_row if line.strip().startswith(name)) for line in lines[2:]] == list(by_row)


def test_tied_best_programs_are_all_shown():
    by_row, _ = figures()
    by_row["all problems"]["best_programs"] = ["alpha", "zeta"]
    assert "alpha+zeta" in report.scores_text(by_row).splitlines()[2].split()


def test_budgets_table():
    by_row, _ = figures()
    lines = report.budgets_text(by_row, 8000).splitlines()
    # The column of answers without a thinking count is always there, so the table has one shape.
    assert lines[0].split() == ["row", "allowance", "thinking_tokens", "without_thinking_count", "tokens_used",
                                "forced", "cut_off_readable"]
    assert lines[3].split() == ["2", "to", "3", "cited", "8000", "1560.000", "0", "1570.000", "0.080", "0.040"]
    by_row["4 to 6 cited"]["thinking_tokens_mean"] = None
    by_row["4 to 6 cited"]["answers_without_thinking_count"] = 25
    assert report.budgets_text(by_row, 8000).splitlines()[4].split()[5:7] == ["n/a", "25"]


def test_problem_by_problem_table_with_both_chance_columns():
    _, table = figures()
    block = report.problem_by_problem_text(table).split("\n\n")[1].splitlines()
    assert block[0] == "recall"
    assert block[1].split() == ["row", "both", "only_model", "only_program", "neither", "only_model_if_guessing",
                                "only_model_if_independent", "if_independent_se"]
    assert block[3].split() == ["all", "problems", "2", "3", "3", "2", f"{5 * CHANCE:.3f}", "2.500",
                                f"{sqrt(1.25):.3f}"]
    assert block[4].split()[4:] == ["1", "2", "1", "1", f"{3 * CHANCE:.3f}", "1.800", f"{sqrt(0.72):.3f}"]


def test_same_wrong_answers_table():
    # The figures are those worked out by hand in test_wrong_answers.py; the stage reads them back from JSON.
    table = json.loads(json.dumps(wrong_answers.same_wrong_answers(*made_up_wrong_answers())))
    blocks = report.wrong_answers_text(table).split("\n\n")
    lines = blocks[1].splitlines()
    assert lines[0] == "surface_trained"
    assert lines[1].split() == ["row", "problems", "wrong_tries", "match", "uniform", "shuffle", "excess", "excess_se",
                                "over_recall", "over_recall_se"]
    assert lines[4].split()[4:] == ["2", "3", f"{1 / 6:.3f}", f"{1 / 58:.3f}", "0.250", f"{-1 / 12:.3f}",
                                    f"{1 / 12:.3f}", f"{-1 / 12:.3f}", f"{7 / 12:.3f}"]
    assert lines[5].split()[4:] == ["1", "1", "0.500", f"{1 / 29:.3f}", "1.000", "-0.500", "n/a", "-0.500", "n/a"]
    # A control is not set against itself, so recall's rows have no columns over a control.
    assert blocks[0].splitlines()[0] == "recall" and blocks[0].splitlines()[1].split()[-1] == "excess_se"
    assert blocks[0].splitlines()[4].split()[4:] == ["2", "3", "0.500", f"{1 / 29:.3f}", "0.500", "0.000", "0.500"]


def test_standard_error_tables():
    by_row, _ = figures()
    lines = report.standard_errors_text(by_row).splitlines()
    assert lines[0].split() == ["row", "guessing", "recall", "room", "room_of", "model"]
    assert lines[3].split()[4:] == ["0.000", f"{sqrt(0.035):.3f}", f"{sqrt(0.035):.3f}", "recall",
                                    f"{sqrt(0.0296):.3f}"]
    by_row["4 to 6 cited"]["model_standard_error"] = None
    assert report.standard_errors_text(by_row).splitlines()[4].split()[-1] == "n/a"
    lines = report.model_minus_program_text(by_row).splitlines()
    assert lines[0].split() == ["row", "guessing", "guessing_se", "recall", "recall_se"]
    assert lines[4].split()[-2:] == [f"{-3.4 / 15:.3f}", f"{sqrt(90.8 / 1125):.3f}"]


def test_bars_are_an_svg_with_one_bar_per_program_and_the_model_marked():
    by_row, _ = figures()
    picture = ElementTree.fromstring(report.bars_svg(by_row))
    bars = [r for r in picture.findall(f"{SVG}rect") if r.get("class") == "bar"]
    assert len(bars) == 3   # guessing, recall, model
    assert bars[-1].get("fill") == "#000000" and bars[0].get("fill") != "#000000"
    labels = [t.text for t in picture.findall(f"{SVG}text")]
    assert {"guessing", "recall", "MODEL", "all problems"} <= set(labels)
    # The model's bar: score .5, so from the axis (y = 20 + 1 x 310 = 330) up to y = 20 + .5 x 310 = 175.
    assert float(bars[-1].get("y")) == pytest.approx(175) and float(bars[-1].get("height")) == pytest.approx(155)
    # One line of one standard error per bar, the guessing one of zero length. The model's: .5 +- sqrt(1.22/90).
    lines = [line for line in picture.findall(f"{SVG}line") if line.get("class") == "error-bar"]
    assert len(lines) == 3
    assert float(lines[-1].get("y1")) == pytest.approx(20 + (1 - (0.5 - sqrt(1.22 / 90))) * 310, abs=0.06)
    assert float(lines[-1].get("y2")) == pytest.approx(20 + (1 - (0.5 + sqrt(1.22 / 90))) * 310, abs=0.06)
    by_row["all problems"]["model_standard_error"] = None
    no_line = ElementTree.fromstring(report.bars_svg(by_row))
    assert len([b for b in no_line.findall(f"{SVG}line") if b.get("class") == "error-bar"]) == 2
    without_model = {r: {k: v for k, v in row.items() if k != "model"} for r, row in by_row.items()}
    assert len([r for r in ElementTree.fromstring(report.bars_svg(without_model, row="topology")).findall(f"{SVG}rect")
                if r.get("class") == "bar"]) == 2


def test_the_second_table():
    # The figures are those worked out by hand in test_second_table.py.
    table = json.loads(json.dumps(second_table.second_table(*made_up_second_table(), runs_disagreed=0.025)))
    parts = report.second_table_text(table).split("\n\n")
    assert parts[0] == ("Prover bins: proved without an option 1, has right options 6, no option proves it 1, "
                        "stopped for another reason 2; the prover's two runs disagreed on 0.025 of the calls. "
                        "The table is over the 6 problems with right options.")
    scores = parts[1].splitlines()
    assert scores[1].split() == ["prover", "prover_se", "either", "either_se", "author", "author_se"]
    assert scores[3].split()[:2] == ["recall", f"{3.5 / 6:.3f}"] and scores[4].split()[:2] == ["model", "0.467"]
    assert parts[2].splitlines()[3].split()[:2] == ["recall", f"{-0.7 / 6:.3f}"]
    assert parts[3] == ("Held-back option right under the prover's key: 0.500; other options right under it, per "
                        "problem: 0.833; option calls that proved the theorem without the option in the proof: 3")
