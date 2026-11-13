"""Tests of report.py: the tables show scoring.py's figures, and the picture is a well-formed SVG."""
import json
import xml.etree.ElementTree as ElementTree

from math import sqrt

from test_scoring import CHANCE, made_up

import pytest

from cube_ladder import report, scoring

SVG = "{http://www.w3.org/2000/svg}"


def figures():
    states, picks, answers = made_up()
    by_distance = scoring.scores_by_distance(states, picks, answers)
    for row in by_distance.values():
        row["most_cubes_written"] = scoring.most_cubes_written(row["tokens_used_mean"], 40)
    # The stage writes the figures as JSON and reads them back: keys become strings.
    return json.loads(json.dumps(by_distance)), scoring.state_by_state(states, picks, answers)


def test_scores_table_shows_every_figure():
    by_distance, _ = figures()
    lines = report.scores_text(by_distance).splitlines()
    assert lines[0].split() == ["distance", "states", "guessing", "lookahead_1", "best", "room", "model", "unreadable",
                                "forced", "thinking_tokens"]
    assert lines[2].split() == ["1", "5", "0.056", "0.600", "lookahead_1", "0.400", "0.560", "0.120", "0.080", "1560.000"]
    assert lines[3].split() == ["2", "5", "0.100", "0.667", "lookahead_1", "0.333", "0.440", "0.200", "0.200", "3200.000"]


def test_tied_best_programs_are_all_shown():
    by_distance, _ = figures()
    by_distance["1"]["best_programs"] = ["alpha", "zeta"]
    assert "alpha+zeta" in report.scores_text(by_distance).splitlines()[2].split()


def test_budgets_table():
    by_distance, _ = figures()
    lines = report.budgets_text(by_distance, 8000).splitlines()
    assert lines[0].split() == ["distance", "allowance", "thinking_tokens", "tokens_used", "forced", "cut_off_readable",
                                "lookahead_1_positions", "most_cubes_written"]
    # Distance 1: tokens used 1570, so at most 1570 / 40 = 39.25 cubes.
    assert lines[2].split() == ["1", "8000", "1560.000", "1570.000", "0.080", "0.040", "18.000", "39.250"]
    by_distance["2"]["thinking_tokens_mean"] = None
    assert report.budgets_text(by_distance, 8000).splitlines()[3].split()[2] == "n/a"


def test_state_by_state_table_with_both_chance_columns():
    _, table = figures()
    block = report.state_by_state_text(table).split("\n\n")[1].splitlines()
    assert block[0] == "lookahead_1"
    assert block[1].split() == ["distance", "both", "only_model", "only_program", "neither", "only_model_if_guessing",
                                "only_model_if_independent", "if_independent_se"]
    assert block[3].split() == ["1", "1", "2", "1", "1", f"{3 * CHANCE[1]:.3f}", "1.800", f"{sqrt(0.72):.3f}"]
    assert block[4].split() == ["2", "1", "1", "2", "1", f"{CHANCE[1] + CHANCE[2]:.3f}", "0.800", f"{sqrt(0.48):.3f}"]


def test_standard_error_tables():
    by_distance, _ = figures()
    lines = report.standard_errors_text(by_distance).splitlines()
    assert lines[0].split() == ["distance", "guessing", "lookahead_1", "room", "room_of", "model"]
    assert lines[2].split() == ["1", "0.000", f"{sqrt(0.035):.3f}", f"{sqrt(0.035):.3f}", "lookahead_1",
                                f"{sqrt(0.0296):.3f}"]
    by_distance["2"]["model_standard_error"] = None
    assert report.standard_errors_text(by_distance).splitlines()[3].split()[-1] == "n/a"
    lines = report.model_minus_program_text(by_distance).splitlines()
    assert lines[0].split() == ["distance", "guessing", "guessing_se", "lookahead_1", "lookahead_1_se"]
    assert lines[3].split()[3:] == [f"{-3.4 / 15:.3f}", f"{sqrt(90.8 / 1125):.3f}"]


def test_curve_is_an_svg_with_one_line_per_series_and_the_model_marked():
    by_distance, _ = figures()
    picture = ElementTree.fromstring(report.curve_svg(by_distance))
    lines = picture.findall(f"{SVG}polyline")
    assert len(lines) == 3   # guessing, lookahead_1, model
    model_line = lines[-1]
    assert model_line.get("stroke") == "#000000" and model_line.get("stroke-width") == "4"
    assert model_line.get("stroke-dasharray") and not lines[0].get("stroke-dasharray")
    labels = [t.text for t in picture.findall(f"{SVG}text")]
    assert {"guessing", "lookahead_1", "MODEL"} <= set(labels)
    # One bar per point: 2 distances x 3 series, the guessing bar at distance 1 being of zero length.
    bars = [line for line in picture.findall(f"{SVG}line") if line.get("class") == "error-bar"]
    assert len(bars) == 6
    # The model's bar at distance 2: score .44, standard error sqrt(.0296) = .172, so from .268 to .612.
    # In the drawing, y = 20 + (1 - score) x 350.
    model_bars = [b for b in bars if b.get("stroke") == "#000000"]
    assert float(model_bars[1].get("y1")) == pytest.approx(20 + (1 - (0.44 - sqrt(0.0296))) * 350, abs=0.06)
    assert float(model_bars[1].get("y2")) == pytest.approx(20 + (1 - (0.44 + sqrt(0.0296))) * 350, abs=0.06)
    by_distance["2"]["model_standard_error"] = None
    no_bar = ElementTree.fromstring(report.curve_svg(by_distance))
    assert len([b for b in no_bar.findall(f"{SVG}line") if b.get("class") == "error-bar"]) == 5
    without_model = {d: {k: v for k, v in row.items() if k != "model"} for d, row in by_distance.items()}
    assert len(ElementTree.fromstring(report.curve_svg(without_model)).findall(f"{SVG}polyline")) == 2
