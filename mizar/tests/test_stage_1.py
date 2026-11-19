"""Tests of stage 1 on the made-up library (tests/test_problems.py works it out by hand): the files and summary
it writes, and that a failed check (a checksum, a check of the build, two builds that differ) stops it with the
message printed first."""
import importlib.util
import json
from pathlib import Path

import pytest
from conftest import MADE_UP, checksums_of

from mizar_ladder import problems

STAGES = Path(__file__).resolve().parent.parent / "stages"


def stage_1():
    spec = importlib.util.spec_from_file_location("stage_1", STAGES / "1_build_problems.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(tmp_path, library=MADE_UP, checksums=None, seed="7"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "checksums.json").write_text(json.dumps(checksums or checksums_of(library)))
    stage_1().main(["--data", str(tmp_path / "data"), "--library", str(library), "--seed", seed, "--test-count", "2",
                    "--checksums", str(tmp_path / "checksums.json")])
    return tmp_path / "data"


def test_the_files_and_the_summary(tmp_path, capsys):
    data = run(tmp_path)
    records = problems.read_jsonl(data / "theorems.jsonl")
    assert len(records) == 10 and sum(r["test"] for r in records) == 2
    assert len(problems.read_jsonl(data / "test_problems.jsonl")) == 2
    assert len(problems.read_jsonl(data / "train_problems.jsonl")) == 3
    summary = json.loads((data / "build_summary.json").read_text())
    assert summary["seed"] == 7 and summary["test_problems"] == 2 and summary["training_problems"] == 3
    assert summary["bins"] == {"all": {"not usable": 3, "too few neighbours": 2, "qualifies": 5},
                               "xboole_0": {"not usable": 2, "too few neighbours": 1, "qualifies": 2},
                               "xboole_1": {"not usable": 1, "too few neighbours": 1, "qualifies": 3}}
    options = summary["options"]
    # Both test problems hold back a theorem of basic_0, an earlier article; every option is from basic_0.
    assert options["all_options_from_one_article"] == 2 and options["held_back_from_an_earlier_article"] == 2
    assert options["held_back_from_the_theorems_own_article"] == 0
    assert options["held_back_theorems"] == 2 and options["held_back_lemmas"] == 0
    # Every theorem of basic_0 has 3 symbols and 3 variables, and a constant with no Mizar name.
    assert options["right_option_length_mean"] == 6
    assert options["problems_showing_a_symbol_without_a_mizar_name"] == 2
    printed = capsys.readouterr().out
    assert "wrote 10 theorems, 2 test problems and 3 training problems" in printed
    assert "bins: not usable 3, too few neighbours 2, qualifies 5" in printed


def test_the_same_seed_writes_the_same_files(tmp_path):
    one, two = run(tmp_path / "one"), run(tmp_path / "two")
    for name in ("theorems.jsonl", "test_problems.jsonl", "train_problems.jsonl", "build_summary.json"):
        assert (one / name).read_bytes() == (two / name).read_bytes()


def test_how_close_the_wrong_options_are_worked_by_hand(made_up):
    # One made-up test problem: right option t2 (length 4), wrong options t3 and t5 (lengths 6 and 8), stated
    # 1, 0 and 3 facts above the theorem.
    class Library:
        def mizar_names(self):
            return {"r1_a": "<"}

        def statement(self, name):
            return {"t2_aa": "r1_a(A, B)", "t3_aa": "r1_a(A, k1_b(B, C))", "t5_aa": "r1_a(k1_b(A, B), k1_b(C, D))",
                    "t9_aa": "r1_a(A, A)"}[name]

        def position(self, name):
            return {"t5_aa": 0, "t2_aa": 2, "t3_aa": 3, "t9_aa": 4}[name]
    test = [{"theorem": "t9_aa", "article": "aa", "given": [], "held_back": 1,
             "options": [{"name": "t2_aa"}, {"name": "t3_aa"}, {"name": "t5_aa"}]}]
    found = stage_1().options_summary(test, Library())
    assert found["right_option_length_mean"] == 3 and found["wrong_option_length_mean"] == (5 + 7) / 2
    assert found["right_option_facts_above_theorem_mean"] == 1 and found["wrong_option_facts_above_theorem_mean"] == 1.5
    assert found["problems_showing_a_symbol_without_a_mizar_name"] == 1 and found["held_back_from_the_theorems_own_article"] == 1


def test_a_wrong_checksum_stops_the_stage(tmp_path):
    checksums = dict(checksums_of(MADE_UP), seq="0" * 64)
    with pytest.raises(SystemExit, match="STOP: seq: sha256"):
        run(tmp_path, checksums=checksums)
    assert not (tmp_path / "data" / "theorems.jsonl").exists()


def test_a_failed_check_of_the_build_stops_the_stage(tmp_path, made_up_copy):
    path = made_up_copy.path / "problems_small_consist" / "xboole_0" / "xboole_0__t3_xboole_0"
    path.write_text("".join(line for line in path.read_text().splitlines(keepends=True) if "t10_basic_0" not in line))
    with pytest.raises(SystemExit, match="STOP: t3_xboole_0: cited fact t10_basic_0 is not in its problem file"):
        run(tmp_path, library=made_up_copy.path)


def test_two_builds_that_differ_stop_the_stage(tmp_path, monkeypatch):
    real, calls = problems.build, []

    def build(*args):
        calls.append(1)
        records, test, train = real(*args)
        return records, (test if len(calls) == 1 else test[::-1]), train
    monkeypatch.setattr(problems, "build", build)
    with pytest.raises(SystemExit, match="STOP: building twice from the same seed gave different problems"):
        run(tmp_path)
