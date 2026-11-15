"""The whole chain on the made-up library with the stand-in prover: stages/1_count.py (two counts, settled),
then stages/2_report.py, each run as its own command. The final table must equal the one worked out by hand,
also where one axiom set is unsettled."""
import hashlib
import json
import resource
import subprocess
import sys

import pytest

import made_up
from tptp_count.count import count
from conftest import ROOT, environments_seen
from test_checks import pilot_calls_file

STAGES = ROOT / "stages"


def stage(script, *arguments, limit=None):
    """Runs a stage as its own command; `limit`: (resource, value) set as a shell limit of that command."""
    def set_limit():
        resource.setrlimit(limit[0], (limit[1], resource.getrlimit(limit[0])[1]))
    return subprocess.run([sys.executable, str(STAGES / script), *map(str, arguments)], capture_output=True, text=True,
                          preexec_fn=set_limit if limit else None)


def first_stage(program, data, pilot, *more, limit=None):
    return stage("1_count.py", "--library", made_up.LIBRARY, "--data", data, "--prover", program, "--pilot-calls", pilot,
                 "--seed", 20261112, *more, limit=limit)


def hand_worked_table():
    """The table for the made-up library, written out from made_up.py's hand-worked figures."""
    needed = made_up.proved_clauses()
    bands = "\n".join(f"  {f'{low + 1 if low else 0}-{low + 20}':>9}: {int(low < needed <= low + 20)}"
                      for low in range(0, 160, 20))
    return f"""Files read: 12

Bin                               Files
left out: not usable                  2
left out: status                      1
left out: duplicate                   1
left out: too few facts               1
proved unaided                        1
no single fact helps                  1
a problem                             2
stopped for another reason            3
Axiom sets where the two counts did not derive the same facts: 0; files set aside for that reason: 0

Main bin                          Share
proved unaided                    0.250
no single fact helps              0.250
a problem                         0.500

Clauses needed when proved unaided (limit 160): 1 files, median {needed}, most {needed}
{bands}

Right facts per problem (of 30): 1: 1 problems, 2: 1 problems
Problems with an option whose call did not decide (their count is a lower bound): {made_up.UNDECIDED}

Area           proved unaided   no single fact helps              a problem
ALG                         1                      0                      2
BLG                         0                      1                      0
"""


def test_count_then_report(tmp_path, stand_in):
    program = stand_in(made_up.table())
    pilot = pilot_calls_file(tmp_path / "pilot.jsonl.gz", None)
    counted = first_stage(program, tmp_path / "data", pilot, "--workers", 2)
    assert counted.returncode == 0, counted.stdout + counted.stderr
    assert "CHECK FAILED" not in counted.stdout and counted.stdout.count("check held") == 4
    reported = stage("2_report.py", "--data", tmp_path / "data")
    assert reported.returncode == 0, reported.stderr
    assert reported.stdout == hand_worked_table()


def test_a_pilot_call_that_differs_stops_the_stage_before_counting(tmp_path, stand_in):
    program = stand_in(made_up.table())
    counted = first_stage(program, tmp_path / "data", pilot_calls_file(tmp_path / "pilot.jsonl.gz", 3))
    assert counted.returncode == 1
    assert counted.stdout.splitlines()[0] == "CHECK FAILED: pilot calls, before counting (1):"
    assert "files read" not in counted.stdout and not (tmp_path / "data").exists()
    assert counted.stdout.splitlines()[-1].startswith("time taken: ")


def _stage_module():
    from importlib import util
    spec = util.spec_from_file_location("count_stage", STAGES / "1_count.py")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_failed_check_after_the_count_is_printed_first_and_stops_the_stage(tmp_path, stand_in, monkeypatch, capsys):
    module = _stage_module()
    monkeypatch.setattr(module.checks, "repeat", lambda data, program: ["a repeated call differs"])
    pilot = pilot_calls_file(tmp_path / "pilot.jsonl.gz", None)
    assert module.main(["--library", str(made_up.LIBRARY), "--data", str(tmp_path / "data"), "--prover",
                        stand_in(made_up.table()), "--pilot-calls", str(pilot), "--seed", "20261112"]) == 1
    after_count = capsys.readouterr().out.split("with no usable list in either count cut off differently\n", 1)[-1]
    assert after_count.splitlines()[:2] == ["CHECK FAILED: repeat of one call in twenty (1):", "  a repeated call differs"]


# A limit each, far above what the stage needs, but not unlimited.
SHELL_LIMITS = {"computing time": (resource.RLIMIT_CPU, 100_000), "address space": (resource.RLIMIT_AS, 2**40),
                "data": (resource.RLIMIT_DATA, 2**40)}


@pytest.mark.parametrize("name", list(SHELL_LIMITS))
def test_the_stage_refuses_to_start_under_a_shell_limit(tmp_path, stand_in, name):
    program = stand_in(made_up.table())
    counted = first_stage(program, tmp_path / "data", pilot_calls_file(tmp_path / "pilot.jsonl.gz", None),
                          limit=SHELL_LIMITS[name])
    assert counted.returncode == 1, counted.stdout + counted.stderr
    assert counted.stdout.startswith(f"REFUSED: the shell limits {name} to {SHELL_LIMITS[name][1]}")
    assert not (tmp_path / "data").exists() and not environments_seen(program).exists()   # the prover never ran


def test_a_wrong_prover_version_stops_the_stage(tmp_path, stand_in):
    """The stage stops at the version check: before the pilot check (the prover is started once, for its
    version) and before any count."""
    program = stand_in(made_up.table(), version="E 3.0")
    counted = first_stage(program, tmp_path / "data", pilot_calls_file(tmp_path / "pilot.jsonl.gz", None))
    assert counted.returncode != 0 and "not the pinned" in counted.stderr
    assert not (tmp_path / "data").exists()
    assert len(environments_seen(program).read_text().splitlines()) == 1


def test_settle_only_settles_two_given_counts_and_starts_no_prover(tmp_path, stand_in):
    program = stand_in(made_up.table())
    for name in ("first", "second"):
        count(made_up.LIBRARY, tmp_path / name, program, 20261112)
    log = environments_seen(program)
    log.unlink()
    settled = stage("1_count.py", "--data", tmp_path / "data", "--settle", tmp_path / "first", tmp_path / "second")
    assert settled.returncode == 0, settled.stdout + settled.stderr
    assert not log.exists()
    assert (tmp_path / "data" / "files.jsonl").read_bytes() == (tmp_path / "first" / "files.jsonl").read_bytes()
    assert json.loads((tmp_path / "data" / "settled.json").read_text()) == {"unsettled": [], "cut off differently": []}


def test_the_two_counts_are_kept_and_a_difference_between_them_stops_the_stage(tmp_path, stand_in):
    program = stand_in(made_up.table())
    pilot = pilot_calls_file(tmp_path / "pilot.jsonl.gz", None)
    assert first_stage(program, tmp_path / "data", pilot).returncode == 0
    data = tmp_path / "data"
    for name in ("files.jsonl", "problems.jsonl", "derived_facts.jsonl"):
        assert (data / "first" / name).read_bytes() == (data / "second" / name).read_bytes() == (data / name).read_bytes()
    saved = data / "second" / "work" / "problems" / "ALG004-1.json"     # a right fact lost in the second count
    result = json.loads(saved.read_text())
    saved.write_text(json.dumps({**result, "right": result["right"][:1]}))
    again = first_stage(program, data, pilot)     # both counts are finished: their files are written again, and settled
    assert again.returncode == 1 and again.stderr == ""
    assert "CHECK FAILED: the two counts agree (1):\n  Problems/ALG/ALG004-1.p: differs" in again.stdout
    assert "repeat of one call in twenty" not in again.stdout       # the stage stopped there


def test_the_prover_program_is_passed_to_both_counts(tmp_path, stand_in):
    program = stand_in(made_up.table())
    behind = ROOT / "tests" / "stand_in_prover.py"     # stands for the prover program behind the start script
    counted = first_stage(program, tmp_path / "data", pilot_calls_file(tmp_path / "pilot.jsonl.gz", None),
                          "--prover-program", behind)
    assert counted.returncode == 0, counted.stdout + counted.stderr
    for name in ("first", "second"):
        saved = json.loads((tmp_path / "data" / name / "work" / "settings.json").read_text())
        assert saved["prover_checksum"] == hashlib.sha256(open(program, "rb").read()).hexdigest()
        assert saved["prover_program_checksum"] == hashlib.sha256(behind.read_bytes()).hexdigest()


def unsettled_table_text():
    """The final table for the pair of counts in made_up.unsettled_table, worked out by hand: ALG004's axiom set
    is unsettled. ALG004-3 (proved unaided) and ALG004-4 (unaided call: term cap) are as counted; ALG004-1 ("a
    problem" in the first count) and BLG001-1 ("no single fact helps" there) are set aside."""
    needed = made_up.proved_clauses()
    bands = "\n".join(f"  {f'{low + 1 if low else 0}-{low + 20}':>9}: {2 * int(low < needed <= low + 20)}"
                      for low in range(0, 160, 20))
    return f"""Files read: 12

Bin                               Files
left out: not usable                  2
left out: status                      1
left out: duplicate                   1
left out: too few facts               1
proved unaided                        2
no single fact helps                  0
a problem                             0
stopped for another reason            5
Axiom sets where the two counts did not derive the same facts: 1; files set aside for that reason: 2 (the other 2 files on those sets did not need the facts)

Main bin                          Share
proved unaided                    1.000
no single fact helps              0.000
a problem                         0.000

Clauses needed when proved unaided (limit 160): 2 files, median {(needed + needed) / 2}, most {needed}
{bands}

Right facts per problem (of 30): no problems
Problems with an option whose call did not decide (their count is a lower bound): 0

Area           proved unaided   no single fact helps              a problem
ALG                         2                      0                      0
"""


def test_count_twice_settle_and_report_with_an_unsettled_set(tmp_path, stand_in):
    program = stand_in(made_up.unsettled_table())
    counted = first_stage(program, tmp_path / "data", pilot_calls_file(tmp_path / "pilot.jsonl.gz", None),
                          "--workers", 2)
    assert counted.returncode == 0, counted.stdout + counted.stderr
    assert "CHECK FAILED" not in counted.stdout and counted.stdout.count("check held") == 4
    assert f"  unsettled: {made_up.SET_1} ({', '.join(made_up.UNSETTLED_FILES)})" in counted.stdout
    files = [json.loads(line) for line in (tmp_path / "data" / "files.jsonl").read_text().splitlines()]
    assert [(f["path"], f["bin"], f["why"]) for f in files] == made_up.UNSETTLED_BINS
    reported = stage("2_report.py", "--data", tmp_path / "data")
    assert reported.returncode == 0, reported.stderr
    assert reported.stdout == unsettled_table_text()


def test_settle_only_ends_with_a_failure_when_the_counts_cannot_be_settled(tmp_path, stand_in):
    program = stand_in(made_up.table())
    for name in ("first", "second"):
        count(made_up.LIBRARY, tmp_path / name, program, 20261112)
    path = tmp_path / "second" / "files.jsonl"
    path.write_text(path.read_text().replace('"bin": "a problem"', '"bin": "no single fact helps"', 1))
    settled = stage("1_count.py", "--data", tmp_path / "data", "--settle", tmp_path / "first", tmp_path / "second")
    assert settled.returncode == 1
    assert "CHECK FAILED: the two counts agree (1):\n  Problems/ALG/ALG004-1.p: differs" in settled.stdout


def test_the_checks_run_on_the_final_files(tmp_path, stand_in):
    """In the first count ALG004-1 is "a problem" with 30 option calls; in the final files its axiom set is
    unsettled and it keeps only its unaided call. The repeat check (every twentieth call, counting from
    ALG003-1's unaided call) reaches ALG004-1's option call 18 in the first count's files, and not in the final
    files. The stand-in answers that one call one way the first time and another way after, so the check fails
    on the first count's files and holds on the final ones."""
    from tptp_count.equations import read_equation, universal_form, write_equation
    from tptp_count.options import draw
    axioms = [read_equation("m(X,m(Y,Z))=m(m(X,Y),Z)")]
    goal = universal_form(read_equation("m(a,b)=m(b,a)"), axioms)
    option_18 = draw([read_equation(f) for f in [made_up.G] + made_up.FACTS], goal, 20261112, "ALG004-1")[18]
    real = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
    row = ([made_up.GOAL["ALG004-1"].replace("cnf(g,", "cnf(goal,"),
            f"cnf(option,axiom,({write_equation(option_18)}))."],
           {"first time": real["clause limit"], "after": real["proved"]})
    program = stand_in([row] + made_up.unsettled_table())
    pilot = pilot_calls_file(tmp_path / "pilot.jsonl.gz", None)
    counted = first_stage(program, tmp_path / "data", pilot)
    assert counted.returncode == 0, counted.stdout + counted.stderr
    assert "check held: repeat of one call in twenty" in counted.stdout
    first = [json.loads(line) for line in (tmp_path / "data" / "first" / "problems.jsonl").read_text().splitlines()]
    four = next(p for p in first if p["id"] == "ALG004-1")
    assert four["calls"][18]["ending"] == "clause limit"
    from tptp_count import checks
    assert checks.repeat(tmp_path / "data", program) == []
    assert checks.repeat(tmp_path / "data" / "first", program) == [
        "ALG004-1 call 20: again proved 125, saved clause limit 160"]
