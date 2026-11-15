"""Tests for report.py: the made-up library's tables equal those worked out by hand; the bins add up to the
number of files read; and the figures on small hand-made files."""
import json

import pytest

import made_up
from tptp_count.count import count
from tptp_count.settle import settle
from tptp_count.report import (ReportError, bin_counts, clauses_needed, main_bins_by_area, main_shares, report,
                               right_facts, set_aside, tables)


@pytest.fixture
def summary(tmp_path, stand_in):
    count(made_up.LIBRARY, tmp_path / "first", stand_in(made_up.table()), 20261112)
    settle(tmp_path / "first", tmp_path / "first", tmp_path)      # one count settled with itself: nothing changes
    return report(tmp_path), tmp_path


def test_the_made_up_librarys_figures_equal_the_hand_worked_ones(summary):
    found, data = summary
    assert found["files"] == 12
    assert found["bins"] == made_up.COUNTS
    assert found["main_shares"] == made_up.SHARES
    assert found["right_facts"]["per_problem"] == made_up.RIGHT_FACTS
    assert found["right_facts"]["problems_with_this_many"] == {"1": 1, "2": 1}
    assert found["right_facts"]["problems_with_undecided_options"] == made_up.UNDECIDED
    assert found["main_bins_by_area"] == made_up.BY_AREA
    needed = found["clauses_needed_proved_unaided"]
    assert needed["values"] == [made_up.proved_clauses()] and needed["count"] == 1
    assert json.loads((data / "bins.json").read_text()) == json.loads(json.dumps(found))


def test_the_bins_add_up_to_the_number_of_files(summary):
    found, _ = summary
    assert sum(found["bins"].values()) == found["files"] == len(made_up.BINS)


def test_bin_counts_stop_on_an_unknown_bin():
    with pytest.raises(ReportError):
        bin_counts([{"path": "x", "bin": "proved"}])


def test_shares_with_no_main_bin_are_none():
    assert main_shares({"proved unaided": 0, "no single fact helps": 0, "a problem": 0}) == \
        {"proved unaided": None, "no single fact helps": None, "a problem": None}
    assert main_shares({"proved unaided": 1, "no single fact helps": 2, "a problem": 1})["no single fact helps"] == 0.5


def test_clauses_needed_in_bands():
    files = [{"bin": "proved unaided", "problem_id": n} for n in "abcd"] + [{"bin": "a problem", "problem_id": "e"}]
    problems = [{"id": n, "unaided": {"processed": v}} for n, v in zip("abcde", (20, 21, 160, 7, 99))]
    found = clauses_needed(files, problems)
    assert found["values"] == [7, 20, 21, 160] and found["median"] == 20.5 and found["max"] == 160
    assert found["bands"]["0-20"] == 2 and found["bands"]["21-40"] == 1 and found["bands"]["141-160"] == 1
    assert sum(found["bands"].values()) == 4 and len(found["bands"]) == 8
    assert clauses_needed([], [])["median"] is None


def test_a_proof_with_no_clause_processed_falls_in_a_band():
    files = [{"bin": "proved unaided", "problem_id": n} for n in "ab"]
    problems = [{"id": "a", "unaided": {"processed": 0}}, {"id": "b", "unaided": {"processed": 1}}]
    found = clauses_needed(files, problems)
    assert found["bands"]["0-20"] == 2 and sum(found["bands"].values()) == found["count"] == 2


def test_right_facts_and_areas_on_hand_made_files():
    files = [{"bin": "a problem", "problem_id": "p", "area": "GRP"}, {"bin": "a problem", "problem_id": "q", "area": "LAT"},
             {"bin": "no single fact helps", "problem_id": "r", "area": "GRP"},
             {"bin": "left out: status", "problem_id": None, "area": "RNG"}]
    problems = [{"id": "p", "right": [0, 4, 9], "undecided_options": []},
                {"id": "q", "right": [2], "undecided_options": [5, 7]},
                {"id": "r", "right": [], "undecided_options": [1]}]    # not counted: not in "a problem"
    assert right_facts(files, problems) == {"per_problem": {"p": 3, "q": 1}, "problems_with_this_many": {"1": 1, "3": 1},
                                            "problems_with_undecided_options": 1}
    assert main_bins_by_area(files) == {"GRP": {"proved unaided": 0, "no single fact helps": 1, "a problem": 1},
                                        "LAT": {"proved unaided": 0, "no single fact helps": 0, "a problem": 1}}


def test_problems_out_of_step_with_files_stop(tmp_path):
    (tmp_path / "files.jsonl").write_text(json.dumps({"path": "x", "bin": "proved unaided", "problem_id": "x"}) + "\n")
    (tmp_path / "problems.jsonl").write_text("")
    with pytest.raises(ReportError):
        report(tmp_path)


def test_tables_show_every_figure(summary):
    text = tables(summary[0])
    assert "Files read: 12" in text and "a problem                             2" in text
    assert "a problem                         0.500" in text
    assert "Right facts per problem (of 30): 1: 1 problems, 2: 1 problems" in text
    assert "Problems with an option whose call did not decide (their count is a lower bound): 1" in text
    assert text.splitlines()[-1].split() == ["BLG", "0", "1", "0"]


def test_the_files_and_axiom_sets_set_aside(tmp_path, stand_in):
    files = [{"why": made_up.UNSETTLED}, {"why": made_up.UNSETTLED}, {"why": "unaided call: term cap"}, {"why": None}]
    assert set_aside(files, {"unsettled": [{"files": ["a", "b"]}], "cut off differently": ["c"]}) == \
        {"axiom_sets": 1, "files": 2, "other_files_on_them": 0}
    # a set with no file set aside: its one file was proved unaided
    assert set_aside([{"why": None}], {"unsettled": [{"files": ["a"]}], "cut off differently": []}) == \
        {"axiom_sets": 1, "files": 0, "other_files_on_them": 1}
    summary = {"files": 1, "bins": {}, "main_shares": {}, "set_aside_unsettled": {"axiom_sets": 1, "files": 0,
               "other_files_on_them": 1}, "clauses_needed_proved_unaided": {"count": 0, "median": None, "max": None,
               "bands": {}}, "right_facts": {"problems_with_this_many": {}, "problems_with_undecided_options": 0},
               "main_bins_by_area": {}}
    assert ("Axiom sets where the two counts did not derive the same facts: 1; files set aside for that reason: 0 "
            "(the other 1 files on those sets did not need the facts)") in tables(summary)
    program = stand_in(made_up.unsettled_table())
    for name in ("first", "second"):
        count(made_up.LIBRARY, tmp_path / name, program, 20261112)
    settle(tmp_path / "first", tmp_path / "second", tmp_path)
    found = report(tmp_path)
    assert found["set_aside_unsettled"] == {"axiom_sets": 1, "files": 2, "other_files_on_them": 2}
    assert found["bins"]["stopped for another reason"] == 5 and found["bins"]["a problem"] == 0
