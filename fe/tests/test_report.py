"""Tests of report.py: the tables show scoring.py's figures, and the picture is a well-formed SVG."""
import json
import xml.etree.ElementTree as ElementTree

from math import sqrt

from test_scoring import CHANCE, made_up
from test_wrong_moves import made_up as made_up_wrong_moves

import pytest

from fe_ladder import report, scoring, wrong_moves

SVG = "{http://www.w3.org/2000/svg}"


def figures():
    problems, picks, answers = made_up()
    by_depth = scoring.scores_by_depth(problems, picks, answers)
    for row in by_depth.values():
        row["most_identities_written"] = scoring.most_identities_written(row["tokens_used_mean"], 40)
    # The stage writes the figures as JSON and reads them back: keys become strings.
    return json.loads(json.dumps(by_depth)), scoring.problem_by_problem(problems, picks, answers)


def test_scores_table_shows_every_figure():
    by_depth, _ = figures()
    lines = report.scores_text(by_depth).splitlines()
    assert lines[0].split() == ["depth", "problems", "guessing", "lookahead_1", "best", "room", "model", "unreadable",
                                "not_available", "forced", "thinking_tokens"]
    assert lines[2].split() == ["1", "5", "0.056", "0.600", "lookahead_1", "0.400", "0.560", "0.120", "0.040", "0.080",
                                "1560.000"]
    assert lines[3].split() == ["2", "5", "0.100", "0.667", "lookahead_1", "0.333", "0.440", "0.200", "0.000", "0.200",
                                "3200.000"]


def test_tied_best_programs_are_all_shown():
    by_depth, _ = figures()
    by_depth["1"]["best_programs"] = ["alpha", "zeta"]
    assert "alpha+zeta" in report.scores_text(by_depth).splitlines()[2].split()


def test_budgets_table():
    by_depth, _ = figures()
    lines = report.budgets_text(by_depth, 8000).splitlines()
    assert lines[0].split() == ["depth", "allowance", "thinking_tokens", "tokens_used", "forced", "cut_off_readable",
                                "lookahead_1_sequences", "most_identities_written"]
    # Depth 1: tokens used 1570, so at most 1570 / 40 = 39.25 identities of the equation's length.
    assert lines[2].split() == ["1", "8000", "1560.000", "1570.000", "0.080", "0.040", "18.000", "39.250"]
    by_depth["2"]["thinking_tokens_mean"] = None
    assert report.budgets_text(by_depth, 8000).splitlines()[3].split()[2] == "n/a"
    # Narrow-and-deep's budget is shown as identities worked out.
    for row in by_depth.values():
        row["identities_worked_out_mean"] = {"narrow_deep": 200.0}
    lines = report.budgets_text(by_depth, 8000).splitlines()
    assert lines[0].split()[6:] == ["lookahead_1_sequences", "narrow_deep_identities", "most_identities_written"]
    assert lines[2].split()[6:] == ["18.000", "200.000", "39.250"]


def test_problem_by_problem_table_with_both_chance_columns():
    _, table = figures()
    block = report.problem_by_problem_text(table).split("\n\n")[1].splitlines()
    assert block[0] == "lookahead_1"
    assert block[1].split() == ["depth", "both", "only_model", "only_program", "neither", "only_model_if_guessing",
                                "only_model_if_independent", "if_independent_se"]
    assert block[3].split() == ["1", "1", "2", "1", "1", f"{3 * CHANCE[1]:.3f}", "1.800", f"{sqrt(0.72):.3f}"]
    assert block[4].split() == ["2", "1", "1", "2", "1", f"{CHANCE[1] + CHANCE[2]:.3f}", "0.800", f"{sqrt(0.48):.3f}"]


def test_same_wrong_moves_table():
    # The figures are those worked out by hand in test_wrong_moves.py; the stage reads them back from JSON.
    table = json.loads(json.dumps(wrong_moves.same_wrong_moves(*made_up_wrong_moves())))
    blocks = report.wrong_moves_text(table).split("\n\n")
    lines = blocks[0].splitlines()
    assert lines[0] == "lookahead_1"
    assert lines[1].split() == ["depth", "problems", "wrong_tries", "left_out_not_available", "match", "uniform",
                                "shuffle", "excess", "excess_se", "over_recall", "over_recall_se"]
    assert lines[3].split() == ["1", "2", "3", "0", f"{1 / 6:.3f}", f"{1 / 34:.3f}", "0.250", f"{-1 / 12:.3f}",
                                f"{1 / 12:.3f}", f"{-1 / 12:.3f}", f"{7 / 12:.3f}"]
    assert lines[4].split() == ["2", "1", "1", "0", "0.500", "0.062", "1.000", "-0.500", "n/a", "-0.500", "n/a"]
    # A control is not set against itself, so recall's rows have no columns over a control.
    assert blocks[1].splitlines()[1].split()[-1] == "excess_se"
    assert blocks[1].splitlines()[3].split() == ["1", "2", "3", "0", "0.500", f"{1 / 17:.3f}", "0.500", "0.000", "0.500"]


def test_standard_error_tables():
    by_depth, _ = figures()
    lines = report.standard_errors_text(by_depth).splitlines()
    assert lines[0].split() == ["depth", "guessing", "lookahead_1", "room", "room_of", "model"]
    assert lines[2].split() == ["1", "0.000", f"{sqrt(0.035):.3f}", f"{sqrt(0.035):.3f}", "lookahead_1",
                                f"{sqrt(0.0296):.3f}"]
    by_depth["2"]["model_standard_error"] = None
    assert report.standard_errors_text(by_depth).splitlines()[3].split()[-1] == "n/a"
    lines = report.model_minus_program_text(by_depth).splitlines()
    assert lines[0].split() == ["depth", "guessing", "guessing_se", "lookahead_1", "lookahead_1_se"]
    assert lines[3].split()[3:] == [f"{-3.4 / 15:.3f}", f"{sqrt(90.8 / 1125):.3f}"]


def test_forced_and_unforced_table():
    # From test_scoring.py: depth 1, 2 forced (both right) and 23 unforced (12 right); depth 2, 5 forced (1 right)
    # and 20 unforced (10 right).
    by_depth, _ = figures()
    lines = report.forced_and_unforced_text(by_depth).splitlines()
    assert lines[0].split() == ["depth", "forced", "forced_right", "unforced", "unforced_right"]
    assert lines[2].split() == ["1", "2", "1.000", "23", f"{12 / 23:.3f}"]
    assert lines[3].split() == ["2", "5", "0.200", "20", "0.500"]
    by_depth["2"]["forced_share_right"] = None
    assert report.forced_and_unforced_text(by_depth).splitlines()[3].split()[2] == "n/a"


def test_curve_is_an_svg_with_one_line_per_series_and_the_model_marked():
    by_depth, _ = figures()
    picture = ElementTree.fromstring(report.curve_svg(by_depth))
    lines = picture.findall(f"{SVG}polyline")
    assert len(lines) == 3   # guessing, lookahead_1, model
    model_line = lines[-1]
    assert model_line.get("stroke") == "#000000" and model_line.get("stroke-width") == "4"
    assert model_line.get("stroke-dasharray") and not lines[0].get("stroke-dasharray")
    labels = [t.text for t in picture.findall(f"{SVG}text")]
    assert {"guessing", "lookahead_1", "MODEL"} <= set(labels)
    # One bar per point: 2 depths x 3 series, the guessing bar at depth 1 being of zero length.
    bars = [line for line in picture.findall(f"{SVG}line") if line.get("class") == "error-bar"]
    assert len(bars) == 6
    # The model's bar at depth 2: score .44, standard error sqrt(.0296) = .172, so from .268 to .612.
    # In the drawing, y = 20 + (1 - score) x 350.
    model_bars = [b for b in bars if b.get("stroke") == "#000000"]
    assert float(model_bars[1].get("y1")) == pytest.approx(20 + (1 - (0.44 - sqrt(0.0296))) * 350, abs=0.06)
    assert float(model_bars[1].get("y2")) == pytest.approx(20 + (1 - (0.44 + sqrt(0.0296))) * 350, abs=0.06)
    by_depth["2"]["model_standard_error"] = None
    no_bar = ElementTree.fromstring(report.curve_svg(by_depth))
    assert len([b for b in no_bar.findall(f"{SVG}line") if b.get("class") == "error-bar"]) == 5
    without_model = {d: {k: v for k, v in row.items() if k != "model"} for d, row in by_depth.items()}
    assert len(ElementTree.fromstring(report.curve_svg(without_model)).findall(f"{SVG}polyline")) == 2
