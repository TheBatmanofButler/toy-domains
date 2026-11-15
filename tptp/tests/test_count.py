"""Tests for count.py with the stand-in prover on the made-up library of twelve files: the bins worked out by
hand; every file in exactly one bin; one worker and four write the same files; a run stopped half-way and
started again writes the same files as an unbroken one."""
import gzip
import hashlib
import json
import os

import pytest

import made_up
from tptp_count import count as counting
from tptp_count import prover
from tptp_count.count import CountError, count, find_problems, library_files, library_version

SEED = 20261112
WRITTEN = ("files.jsonl", "problems.jsonl", "derived_facts.jsonl")


def _read(data, name):
    return [json.loads(line) for line in (data / name).read_text().splitlines()]


def _all_files(data):
    """Every file the run writes, by name, as bytes (calls/ included; work/ is not part of the output)."""
    found = {name: (data / name).read_bytes() for name in WRITTEN}
    found.update({f"calls/{p.name}": p.read_bytes() for p in sorted((data / "calls").iterdir())})
    return found


@pytest.fixture
def program(stand_in):
    return stand_in(made_up.table())


@pytest.fixture
def one_run(tmp_path, program):
    data = tmp_path / "one"
    count(made_up.LIBRARY, data, program, SEED, workers=1)
    return data


def test_the_bins_worked_out_by_hand(one_run):
    files = _read(one_run, "files.jsonl")
    assert [(f["path"], f["bin"], f["why"]) for f in files] == made_up.BINS
    assert {f["path"]: f["area"] for f in files}["Problems/BLG/BLG001-1.p"] == "BLG"


def test_every_file_is_in_exactly_one_bin(one_run):
    files = _read(one_run, "files.jsonl")
    assert [f["path"] for f in files] == library_files(made_up.LIBRARY)
    assert len(files) == 12 == len({f["path"] for f in files})


def test_problems_hold_what_the_calls_found(one_run):
    problems = {p["id"]: p for p in _read(one_run, "problems.jsonl")}
    assert list(problems) == ["ALG003-1", "ALG004-1", "ALG004-3", "ALG004-4", "ALG005-1", "ALG006-1", "BLG001-1"]
    first = problems["ALG004-1"]
    assert sorted(first["options"]) == sorted(made_up.FACTS)
    assert [first["options"][n] for n in first["right"]] == sorted(
        [made_up.FACTS[3], made_up.FACTS[11]], key=first["options"].index)
    assert first["unaided"]["ending"] == "clause limit" and first["seed"] == SEED
    assert first["goal"] == "m(a,b)=m(b,a)" and first["axioms"][1] == "m(e,X)=X"
    assert [problems["ALG004-4"]["options"][n] for n in problems["ALG004-4"]["right"]] == [made_up.FACTS[5]]
    assert "m(X1,m(e,e))=m(m(e,e),X1)" not in problems["ALG004-4"]["options"]
    # BLG001-1 gets the axiom set's facts in its own symbols
    assert all("m(" not in o and ("n(" in o) for o in problems["BLG001-1"]["options"])
    assert "options" not in problems["ALG003-1"] and "options" not in problems["ALG005-1"]
    assert problems["ALG003-1"]["unaided"]["processed"] == made_up.proved_clauses()
    # the problems.jsonl fields of the specification, and nothing kept only for the work folder
    assert set(first) == {"id", "path", "area", "axioms", "goal", "unaided", "options", "calls", "right",
                          "undecided_options", "seed"}
    assert set(problems["ALG003-1"]) == {"id", "path", "area", "axioms", "goal", "unaided", "seed"}


def test_calls_keep_every_full_output(one_run):
    with gzip.open(one_run / "calls" / "ALG004-1.jsonl.gz", "rt") as f:
        calls = [json.loads(line) for line in f]
    assert [c["call"] for c in calls] == ["unaided"] + list(range(30))
    assert "# SZS status ResourceOut" in calls[0]["output"]
    assert sorted(p.name for p in (one_run / "calls").iterdir()) == [
        f"{name}.jsonl.gz" for name in ("ALG003-1", "ALG004-1", "ALG004-3", "ALG004-4", "ALG005-1", "ALG006-1",
                                         "ALG007-1", "BLG001-1", "axiom_set_0", "axiom_set_1", "axiom_set_2",
                                         "axiom_set_3", "axiom_set_4")]


def test_the_deriving_runs_outputs_are_kept_without_their_clauses(one_run):
    with gzip.open(one_run / "calls" / "axiom_set_1.jsonl.gz", "rt") as f:
        runs = [json.loads(line) for line in f]
    assert [r["run"] for r in runs] == list(range(6)) and all(r["ending"] == "nothing left" for r in runs)
    assert all("# SZS status Satisfiable" in r["output"] and "cnf(" not in r["output"] for r in runs)
    assert runs[2]["setting"] == ["S1", 200, "KBO6"] and runs[2]["printed"] == 31


def test_after_nothing_left_no_options_are_drawn_and_no_option_calls_made(tmp_path, stand_in):
    """ALG006-1's unaided call ends with nothing left. Its axiom set is given 30 facts here, so that options
    could be drawn if the code went on past that ending."""
    real = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
    facts = (["--print-saturated=eE", "(t(X,Y)=t(Y,X))"], made_up._printed(made_up.FACTS) + real["nothing left"])
    data = tmp_path / "data"
    count(made_up.LIBRARY, data, stand_in([facts] + made_up.table()), SEED, workers=1)
    assert len(_read(data, "derived_facts.jsonl")[3]["facts"]) == 30
    problem = next(p for p in _read(data, "problems.jsonl") if p["id"] == "ALG006-1")
    assert problem["unaided"]["ending"] == "nothing left"
    assert not {"options", "calls", "right", "undecided_options"} & set(problem)
    with gzip.open(data / "calls" / "ALG006-1.jsonl.gz", "rt") as f:
        assert [json.loads(line)["call"] for line in f] == ["unaided"]


def test_undecided_options_are_recorded(one_run):
    problems = {p["id"]: p for p in _read(one_run, "problems.jsonl")}
    assert problems["ALG004-1"]["undecided_options"] == [] and problems["BLG001-1"]["undecided_options"] == []
    four = problems["ALG004-4"]
    assert [four["options"][n] for n in four["undecided_options"]] == [made_up.FACTS[6]]
    assert problems["ALG004-3"]["undecided_options"] == list(range(30))


@pytest.mark.parametrize("ending", ["time cap", "memory cap", "unreadable"])
def test_a_deriving_run_that_did_not_finish_stops_every_file_on_its_axiom_set(tmp_path, stand_in, ending):
    """The fourth deriving run of ALG004's axiom set (S3 150 LPO4) prints its facts but does not finish; the
    axiom set then has no usable list of facts, and its files whose unaided call reached the clause limit go to
    "stopped for another reason". ALG003-1's set is not touched."""
    real = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
    stop = real[ending] if ending != "unreadable" else "eprover: a stop the code has no words for\n"
    printed = "".join(f"cnf(c_0_{n}, plain, ({fact})).\n" for n, fact in enumerate([made_up.G] + made_up.FACTS))
    first = (["--print-saturated=eE", "--processed-clauses-limit=150", "-tLPO4", "(m(X,m(Y,Z))=m(m(X,Y),Z))"],
             printed + stop)
    data = tmp_path / "data"
    count(made_up.LIBRARY, data, stand_in([first] + made_up.table()), SEED, workers=1)
    reason = "no usable list of facts: a deriving run of its axiom set did not finish"
    expected = {path: (bin_name, why) for path, bin_name, why in made_up.BINS}
    for name in ("ALG004-1", "ALG004-3", "ALG004-4"):
        expected[f"Problems/ALG/{name}.p"] = ("stopped for another reason", reason)
    expected["Problems/BLG/BLG001-1.p"] = ("stopped for another reason", reason)
    assert {f["path"]: (f["bin"], f["why"]) for f in _read(data, "files.jsonl")} == expected
    sets = _read(data, "derived_facts.jsonl")
    assert sets[1]["facts"] is None and sets[1]["not_finished"] == "deriving run 3 (S3 150 LPO4): " + ending
    assert [r["ending"] for r in sets[1]["runs"]][3] == ending and sets[0]["facts"] == []
    # of the run that did not finish, only how it ended is written: not what it had printed, not its output
    assert sets[1]["runs"][3] == {"setting": ["S3", 150, "LPO4"], "ending": ending}
    assert all(set(r) == {"setting", "ending", "printed"} for n, r in enumerate(sets[1]["runs"]) if n != 3)
    assert sets[1]["printed"] == 5 * 31
    with gzip.open(data / "calls" / "axiom_set_1.jsonl.gz", "rt") as f:
        runs = [json.loads(line) for line in f]
    assert runs[3] == {"run": 3, "setting": ["S3", 150, "LPO4"], "ending": ending}
    assert all("output" in r for n, r in enumerate(runs) if n != 3)
    problems = {p["id"]: p for p in _read(data, "problems.jsonl")}
    assert "options" not in problems["ALG004-1"] and "no_facts" not in problems["ALG004-1"]
    with gzip.open(data / "calls" / "ALG004-1.jsonl.gz", "rt") as f:
        assert len(f.readlines()) == 1


def test_the_problem_key_takes_the_goal_as_the_goal():
    """Two files with the same equations in all, where one's goal is the other's axiom: different problems."""
    def file(path, axioms, goal):
        return {"path": path, "area": "A", "status": "Unsatisfiable", "usable": True, "axioms": axioms, "goal": goal}
    first = file("A/P1.p", ["m(X,e)=X", "m(e,X)=X"], "m(a,a)=a")
    second = file("A/P2.p", ["m(X,e)=X", "m(a,a)=a"], "m(e,X)=X")
    problems, duplicates, sets = find_problems([first, second])
    assert [p["id"] for p in problems] == ["P1", "P2"] and duplicates == {} and len(sets) == 2


def test_withdrawn_files_are_not_read(tmp_path):
    (tmp_path / "Problems" / "ABC").mkdir(parents=True)
    for name in ("ABC001-1.p", "ABC002-1.rm", "ABC003-1.p"):
        (tmp_path / "Problems" / "ABC" / name).write_text("")
    assert library_files(tmp_path) == ["Problems/ABC/ABC001-1.p", "Problems/ABC/ABC003-1.p"]


def test_the_tptp_version_is_read_from_the_first_file(tmp_path):
    assert library_version(made_up.LIBRARY, library_files(made_up.LIBRARY)) == "0.0"
    (tmp_path / "Problems").mkdir()
    (tmp_path / "Problems" / "X.p").write_text("% File     : X : no version here\n")
    with pytest.raises(CountError):
        library_version(tmp_path, ["Problems/X.p"])
    with pytest.raises(CountError):
        library_version(tmp_path, [])


def test_derived_facts_once_per_axiom_set(one_run):
    sets = _read(one_run, "derived_facts.jsonl")
    assert [s["first_file"] for s in sets] == ["Problems/ALG/ALG003-1.p", "Problems/ALG/ALG004-1.p",
                                               "Problems/ALG/ALG005-1.p", "Problems/ALG/ALG006-1.p",
                                               "Problems/ALG/ALG007-1.p"]
    assert sets[1]["facts"] == [made_up.G] + made_up.FACTS and sets[1]["printed"] == 6 * 31
    assert [r["ending"] for r in sets[1]["runs"]] == ["nothing left"] * 6
    assert len(sets[4]["facts"]) == 5


def test_one_worker_and_four_write_the_same_files(one_run, tmp_path, program):
    four = tmp_path / "four"
    count(made_up.LIBRARY, four, program, SEED, workers=4)
    assert _all_files(four) == _all_files(one_run)


def test_a_run_stopped_half_way_and_started_again(one_run, tmp_path, program, monkeypatch):
    again = tmp_path / "again"
    done = []
    real_task = counting.problem_task

    def stopping(task):
        if len(done) == 3:
            raise KeyboardInterrupt("stopped half-way")
        done.append(task[0]["id"])
        real_task(task)
    monkeypatch.setattr(counting, "problem_task", stopping)
    with pytest.raises(KeyboardInterrupt):
        count(made_up.LIBRARY, again, program, SEED, workers=1)
    assert not (again / "files.jsonl").exists()
    monkeypatch.setattr(counting, "problem_task", real_task)
    seen = []
    monkeypatch.setattr(counting, "problem_task", lambda task: (seen.append(task[0]["id"]), real_task(task)))
    count(made_up.LIBRARY, again, program, SEED, workers=1)
    assert len(seen) == 8 - 3 and not set(seen) & set(done)    # what was saved is not done again
    assert _all_files(again) == _all_files(one_run)


def test_a_saved_run_with_another_seed_is_refused(one_run, program):
    with pytest.raises(CountError):
        count(made_up.LIBRARY, one_run, program, SEED + 1, workers=1)


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_the_settings_are_saved(one_run, program):
    saved = json.loads((one_run / "work" / "settings.json").read_text())
    assert saved == {"seed": SEED, "limit": 160, "prover_version": prover.VERSION,
                     "prover_checksum": _sha256(program), "prover_program_checksum": None,
                     "prover_environment": {"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                     "shell_limits": {"computing time": "unlimited", "address space": "unlimited", "data": "unlimited"},
                     "c_library": os.confstr("CS_GNU_LIBC_VERSION"), "tptp_version": "0.0"}


def test_the_prover_program_behind_a_start_script_is_recorded_and_checked(tmp_path, program, stand_in):
    """The stand-in's own code stands for the prover program behind the start script."""
    data = tmp_path / "data"
    behind = made_up.FIXTURES.parent / "stand_in_prover.py"
    count(made_up.LIBRARY, data, program, SEED, workers=1, prover_program=str(behind))
    saved = json.loads((data / "work" / "settings.json").read_text())
    assert saved["prover_program_checksum"] == _sha256(behind) and saved["prover_checksum"] == _sha256(program)
    other = tmp_path / "other_program"
    other.write_text("another program\n")
    other.chmod(0o755)
    with pytest.raises(CountError, match="prover_program_checksum"):
        count(made_up.LIBRARY, data, program, SEED, workers=1, prover_program=str(other))
    with pytest.raises(CountError, match="prover_program_checksum"):
        count(made_up.LIBRARY, data, program, SEED, workers=1)


@pytest.mark.parametrize("name", ["seed", "limit", "prover_version", "prover_checksum", "prover_program_checksum",
                                  "prover_environment", "shell_limits", "c_library", "tptp_version"])
def test_a_run_started_again_refuses_any_difference_in_the_settings(one_run, program, name):
    path = one_run / "work" / "settings.json"
    saved = json.loads(path.read_text())
    path.write_text(json.dumps({**saved, name: "something else"}))
    with pytest.raises(CountError, match=name):
        count(made_up.LIBRARY, one_run, program, SEED, workers=1)


def test_another_prover_program_is_refused(one_run, stand_in):
    with pytest.raises(CountError, match="prover_checksum"):
        count(made_up.LIBRARY, one_run, stand_in(made_up.table()[1:]), SEED, workers=1)


def test_find_problems_on_hand_made_files():
    def file(path, axioms, goal, status="Unsatisfiable"):
        return {"path": path, "area": path[:3], "status": status, "usable": True, "axioms": axioms, "goal": goal}
    files = [file("A/P1.p", ["f(X,e)=X"], "f(a,e)=a"), file("A/P2.p", ["g(Y,c)=Y"], "g(b,c)=b"),
             file("A/P3.p", ["g(Y,c)=Y"], "g(c,b)=c"), file("A/P4.p", ["f(X,e)=X"], "a=b", "Satisfiable"),
             {"path": "A/P5.p", "area": "A", "status": "Unsatisfiable", "usable": "no goal"}]
    problems, duplicates, sets = find_problems(files)
    assert [p["id"] for p in problems] == ["P1", "P3"] and duplicates == {"A/P2.p": "A/P1.p"}
    assert len(sets) == 1 and sets[0]["first_file"] == "A/P1.p" and problems[1]["axiom_set"] == 0
    with pytest.raises(CountError):
        find_problems([file("A/P1.p", ["f(X)=X"], "f(a)=a"), file("B/P1.p", ["g(X,X)=X"], "g(a,a)=a")])


def test_facts_for_a_file_whose_axioms_are_no_renaming_stop_loudly():
    problem = {"path": "x", "axiom_set": 0, "axioms": ["g(X)=X"]}
    with pytest.raises(CountError):
        counting._facts_for(problem, [{"axioms": ["f(X,X)=X"]}], {"facts": []})


@pytest.mark.parametrize("ending, undecided", [("term cap", True), ("memory cap", True), ("time cap", True),
                                               ("unreadable", True), ("nothing left", False),
                                               ("clause limit", False)])
def test_an_undecided_option_is_one_whose_call_did_not_decide(tmp_path, stand_in, ending, undecided):
    """ALG004-4's option F6 answered with each ending in turn (F5 still proves the goal)."""
    real = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
    real["unreadable"] = "eprover: a stop the code has no words for\n"
    four_goal = made_up.GOAL["ALG004-4"].replace("cnf(g,", "cnf(goal,")
    f6 = (["cnf(goal,negated_conjecture,(m(a,m(e,e))!=m(m(e,e),a)))", f"cnf(option,axiom,({made_up.FACTS[6]}))."],
          real[ending])
    assert f6[0][0] in four_goal
    data = tmp_path / "data"
    count(made_up.LIBRARY, data, stand_in([f6] + made_up.table()), SEED, workers=1)
    four = next(p for p in _read(data, "problems.jsonl") if p["id"] == "ALG004-4")
    number = four["options"].index(made_up.FACTS[6])
    assert four["calls"][number]["ending"] == ending
    assert four["undecided_options"] == ([number] if undecided else [])


def test_two_runs_write_the_same_files_when_a_cut_off_run_prints_a_different_amount(tmp_path, stand_in):
    """The fourth deriving run of ALG004's axiom set prints a different number of clauses on each start before
    it reaches the time cap (each clause written over two lines, as E writes a long one, so that its output
    apart from the clauses differs too), and reports a different time used; ALG005-1's unaided call reports a
    different time used on each start. Every compared file is still the same."""
    real = {e["ending"]: e["output"] for e in json.loads((made_up.FIXTURES / "endings.json").read_text())}
    varying = (["--print-saturated=eE", "--processed-clauses-limit=150", "-tLPO4", "(m(X,m(Y,Z))=m(m(X,Y),Z))"],
               {"repeat": "cnf(c_0_1, plain, (m(X1,m(X2,X1))=\n    m(X2,X1))).\n",
                "then": "# User time                : {seconds} s\n" + real["time cap"]})
    timed = ([made_up.GOAL["ALG005-1"].replace("cnf(g,", "cnf(goal,")],
             {"repeat": "", "then": real["term cap"] + "# User time                : {seconds} s\n"})
    program = stand_in([varying, timed] + made_up.table())
    first, second = tmp_path / "first", tmp_path / "second"
    count(made_up.LIBRARY, first, program, SEED, workers=1)
    count(made_up.LIBRARY, second, program, SEED, workers=2)
    assert _all_files(first) == _all_files(second)
    assert _read(first, "derived_facts.jsonl")[1]["runs"][3] == {"setting": ["S3", 150, "LPO4"], "ending": "time cap"}
