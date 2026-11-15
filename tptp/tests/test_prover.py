"""Tests for prover.py: how a call ended, on real outputs of every ending; the input text; running a call
through the stand-in prover, which shows the prover is started in the fixed environment and both its output
streams are kept. Slow tests: 200 calls rebuilt from the earlier pilot give its outcome and counts; one call run
three times at once gives the same result each time; 50 borderline pilot calls give the pilot's outcome and
counts whichever memory setting the caller's environment holds."""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import FIXTURES, read_json, read_jsonl_gz
from tptp_count import prover
from tptp_count.equations import read_equation, read_relation
from tptp_count.prover import (CLAUSE_LIMIT, ENDINGS, NOTHING_LEFT, PROVED, TERM_CAP_REACHED, UNREADABLE, ProverError,
                               call, check_version, command, counts, how_it_ended, input_text, printed_equations)
from conftest import environments_seen
from stand_in_prover import PRINT_ENVIRONMENT

PILOT_ENDING = {"proof": PROVED, "limit": CLAUSE_LIMIT}


@pytest.fixture(scope="module")
def endings():
    return read_json("endings.json")


@pytest.fixture(scope="module")
def pilot_calls():
    return read_jsonl_gz("pilot_calls.jsonl.gz")


def test_every_ending_on_a_real_output(endings):
    assert sorted(e["ending"] for e in endings) == sorted(ENDINGS)
    for saved in endings:
        assert how_it_ended(saved["output"]) == saved["ending"], saved["made_with"]


def test_the_words_each_ending_rests_on(endings):
    """The lines named in prover.py are in the saved outputs as written there."""
    words = {"proved": ["# Proof found!", "# SZS status Unsatisfiable"],
             "clause limit": ["# Failure: User resource limit exceeded!", "# SZS status ResourceOut"],
             "nothing left": ["# No proof found!", "# SZS status Satisfiable"],
             "term cap": ["# Failure: User resource limit exceeded!", "# SZS status ResourceOut"],
             "memory cap": ["# Failure: Resource limit exceeded (memory)"],
             "time cap": ["# Failure: Resource limit exceeded (time)"]}
    for saved in endings:
        lines = saved["output"].splitlines()
        assert all(w in lines for w in words.get(saved["ending"], [])), saved["ending"]
    term = next(e for e in endings if e["ending"] == "term cap")
    assert counts(term["output"])["terms"] >= prover.TERM_CAP and counts(term["output"])["processed"] < 160


def test_pilot_outputs_read_as_the_pilot_read_them(pilot_calls):
    assert len(pilot_calls) == 200
    for saved in pilot_calls:
        result = saved["pilot_result"]
        assert how_it_ended(saved["pilot_output"]) == PILOT_ENDING[result["status"]]
        assert counts(saved["pilot_output"]) == {"processed": result["processed"], "generated": result["generated"],
                                                 "terms": result["tb"]}


def _clause_limit_output(processed=160, terms=5000):
    return ("# Failure: User resource limit exceeded!\n# SZS status ResourceOut\n"
            f"# Processed clauses                    : {processed}\n"
            f"# Termbank termtop insertions          : {terms}\n")


@pytest.mark.parametrize("output, ending", [
    ("", UNREADABLE),
    ("eprover: some error\n", UNREADABLE),
    (_clause_limit_output(), CLAUSE_LIMIT),
    (_clause_limit_output(processed=159), UNREADABLE),               # stopped before the limit, by something else
    (_clause_limit_output(terms=prover.TERM_CAP), TERM_CAP_REACHED),
    (_clause_limit_output(processed=12, terms=2_000_000), TERM_CAP_REACHED),
    ("# Failure: User resource limit exceeded!\n# SZS status ResourceOut\n# Processed clauses : 160\n", UNREADABLE),
    ("# Proof found!\n# SZS status Unsatisfiable\n" + _clause_limit_output(), UNREADABLE),   # two endings at once
    ("# Proof found!\n# SZS status Satisfiable\n", UNREADABLE),
    ("# Proof found!\n", UNREADABLE),
    ("# Failure: User resource limit exceeded!\n# Processed clauses : 160\n# Termbank termtop insertions : 1\n",
     UNREADABLE),
])
def test_outputs_that_fit_no_ending_or_more_than_one(output, ending):
    assert how_it_ended(output) == ending


def test_nothing_left_needs_both_of_the_provers_lines(endings):
    saturated = next(e["output"] for e in endings if e["ending"] == "nothing left")
    assert how_it_ended(saturated) == NOTHING_LEFT
    for line in ("# No proof found!", "# SZS status Satisfiable"):
        without = "\n".join(kept for kept in saturated.splitlines() if kept.strip() != line) + "\n"
        assert how_it_ended(without) == UNREADABLE, line


def test_lines_on_time_and_memory_used_are_never_kept(stand_in, endings):
    memory = next(e["output"] for e in endings if e["ending"] == "memory cap")
    proof = next(e["output"] for e in endings if e["ending"] == "proved")
    usage = ["# User time                : 0.005 s", "# System time              : 0.000 s",
             "# Total time               : 0.005 s", "# Maximum resident set size: 123916 pages",
             "#    Propositional solver time         : 0.000"]
    assert all(line in memory + proof for line in usage)
    program = stand_in([(["--print-saturated=eE"], "cnf(c_0_1, plain, (f(X1,X1)=X1)).\n" + memory),
                        ([], proof + memory)])
    found = call([read_equation("g(X)=X")], None, read_equation("f(a)=g(a)"), program=program)
    run = prover.derive([read_equation("g(X)=X")], "S3", 150, "LPO4", 220, 4, program=program)
    for output in (found["output"], run["output"]):
        assert not any(line in output for line in usage)
        assert "# Failure: Resource limit exceeded (memory)" in output and "eprover: Out of Memory" in output
    assert "# Processed clauses                    : 125" in found["output"]
    assert counts(found["output"]) == counts(proof) and run["ending"] == prover.MEMORY_CAP_REACHED


def test_unprocessed_is_read_from_the_output(endings):
    proof = next(e["output"] for e in endings if e["ending"] == "proved")
    assert prover.unprocessed(proof) == 1221 and prover.unprocessed("") is None


def test_the_limit_and_a_run_with_no_term_cap():
    assert how_it_ended(_clause_limit_output(processed=200), limit=200) == CLAUSE_LIMIT
    assert how_it_ended(_clause_limit_output(processed=200, terms=10**9), limit=200, term_cap=None) == CLAUSE_LIMIT


def test_counts_missing_or_printed_twice_are_none():
    assert counts("# Processed clauses : 3\n# Processed clauses : 4\n")["processed"] is None
    assert counts("") == {"processed": None, "generated": None, "terms": None}


def test_input_text_for_a_fixed_problem_equals_the_saved_copy():
    from tptp_count.tptp_file import axioms_and_goal, read_file
    axioms, goal = axioms_and_goal(read_file("Problems/GRP/GRP001-2.p", FIXTURES / "tptp"))
    option = read_equation("multiply(inverse(X),multiply(X,Y))=Y")
    assert input_text(axioms, option, goal) == (FIXTURES / "input_text_GRP001-2.txt").read_text()
    assert input_text(axioms, None, goal).count("\n") == 8
    assert "goal" not in input_text(axioms, None, None)


def test_input_text_is_the_pilots_but_for_the_options_name_and_role(pilot_calls):
    for saved in pilot_calls:
        ours = _our_input(saved)
        theirs = re.sub(r"^cnf\(lem\d+,lemma,", "cnf(option,axiom,", saved["pilot_input"], flags=re.M)
        assert ours == theirs


def _our_input(saved):
    axioms, option, goal = _our_call(saved)
    return input_text(axioms, option, goal)


def _our_call(saved):
    axioms = [read_equation(a) for a in saved["axioms"]]
    option = None if saved["option"] is None else read_equation(saved["option"])
    sign, goal = read_relation(saved["goal_denied"])
    assert sign == "!="
    return axioms, option, goal


def test_command_is_the_pinned_one():
    assert command() == ["--print-statistics", "--silent", "--cpu-limit=60", "--processed-clauses-limit=160",
                         "--tb-insert-limit=1000000", "--memory-limit=2000", "-tKBO6", "-WNoSelection",
                         "-H(1*FIFOWeight(ConstPrio),1*Clauseweight(ConstPrio,1,1,1))"]
    assert "--processed-clauses-limit=20" in command(20)


def test_a_call_through_the_stand_in(stand_in, endings):
    proof = next(e["output"] for e in endings if e["ending"] == "proved")
    program = stand_in([(["--processed-clauses-limit=160", "cnf(option,axiom,(f(X)=X))"], proof)])
    result = call([read_equation("g(X)=X")], read_equation("f(X)=X"), read_equation("f(a)=g(a)"), program=program)
    assert result["ending"] == PROVED and result["output"] == prover.without_usage(proof) and result["exit_code"] == 0
    assert result["processed"] == counts(proof)["processed"] and result["generated"] is not None
    nothing = call([read_equation("g(X)=X")], None, read_equation("f(a)=g(a)"), program=program)
    assert nothing["ending"] == UNREADABLE and nothing["processed"] is None


def test_check_version(stand_in):
    check_version(stand_in([]))
    with pytest.raises(ProverError):
        check_version(stand_in([], version="E 2.5 Avongrove"))


# The memory settings of the C library that were seen to change E 2.6's search.
MEMORY_SETTINGS = {"MALLOC_MMAP_THRESHOLD_": "67108864", "MALLOC_TOP_PAD_": "1048576",
                   "GLIBC_TUNABLES": "glibc.malloc.mmap_threshold=67108864"}


# The environment the prover must see, written out here rather than taken from the code under test.
FIXED = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}


@pytest.mark.parametrize("setting", [None, *MEMORY_SETTINGS])
def test_the_prover_is_started_in_the_fixed_environment(stand_in, monkeypatch, tmp_path, setting):
    """Whatever the caller's environment holds (a memory setting, its own PATH, anything else), the prover sees
    exactly PATH=/usr/bin:/bin and LC_ALL=C: in the version check, in calls and in deriving runs."""
    if setting is not None:
        monkeypatch.setenv(setting, MEMORY_SETTINGS[setting])
    monkeypatch.setenv("SOMETHING_OF_THE_CALLERS", "1")
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/local/bin:/usr/bin:/bin")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    program = stand_in([([], PRINT_ENVIRONMENT)])
    check_version(program)
    found = call([read_equation("g(X)=X")], None, read_equation("f(a)=g(a)"), program=program)
    assert json.loads(found["output"]) == FIXED
    run = prover.derive([read_equation("g(X)=X")], "S3", 150, "LPO4", 220, 4, program=program)
    assert json.loads(run["output"]) == FIXED
    seen = [json.loads(line) for line in environments_seen(program).read_text().splitlines()]
    assert seen == [FIXED, FIXED, FIXED]     # the version check, the call, the deriving run


def test_both_output_streams_are_in_a_calls_output(stand_in, endings):
    """E prints some of its stops on the error stream: running out of memory, for one."""
    memory = next(e["output"] for e in endings if e["ending"] == "memory cap")
    assert "eprover: Out of Memory" in memory
    on_stdout = "\n".join(line for line in memory.splitlines() if "Out of Memory" not in line) + "\n"
    program = stand_in([([], [on_stdout, "eprover: Out of Memory\n"])])
    found = call([read_equation("g(X)=X")], None, read_equation("f(a)=g(a)"), program=program)
    assert found["output"] == prover.without_usage(on_stdout) + "eprover: Out of Memory\n"
    assert found["ending"] == prover.MEMORY_CAP_REACHED
    run = prover.derive([read_equation("g(X)=X")], "S3", 150, "LPO4", 220, 4, program=program)
    assert "eprover: Out of Memory" in run["output"] and "# Failure: Resource limit exceeded (memory)" in run["output"]
    assert run["ending"] == prover.MEMORY_CAP_REACHED


def test_a_deriving_run_through_the_stand_in(stand_in):
    lines = ["cnf(c_0_1, plain, (f(X1,X1)=X1)).", "cnf(c_0_2, plain, (f(X1,X2)!=X1)).", "cnf(c_0_3, plain, ($false)).",
             "cnf(c_0_4, plain, (f(X1,X2)=X1|X1=X2)).", "cnf(c_0_5, plain, (g(" + "a," * 120 + "a)=b)).",
             "cnf(c_0_6, plain, (g(X1)=X1))."]
    output = "\n".join(lines) + "\n" + _clause_limit_output(processed=150, terms=10**8)
    program = stand_in([(["--print-saturated=eE", "-tLPO4", "-H(1*FIFOWeight(ConstPrio))"], output)])
    run = prover.derive([read_equation("f(X,X)=X")], "S3", 150, "LPO4", 220, 4, program=program)
    assert run["ending"] == CLAUSE_LIMIT and run["printed"] == 6
    assert run["clauses"] == lines[:4]     # the long line is passed over, and only 4 lines are read
    assert "cnf(" not in run["output"]
    assert printed_equations(run["clauses"]) == [read_equation("f(X1,X1)=X1")]


def test_a_printed_clause_in_an_unexpected_form_stops_loudly():
    with pytest.raises(ProverError):
        printed_equations(["cnf(c_0_1, plain, (f(X1)=X1), inference(x))."])
    with pytest.raises(ProverError):
        printed_equations(["cnf(c_0_1, plain, (f(X1=X1)))."])
    with pytest.raises(ProverError):
        printed_equations(["cnf(c_0_1, plain)."])


@pytest.mark.slow
def test_200_pilot_calls_give_the_pilots_outcome_and_counts(pilot_calls, real_prover):
    check_version(real_prover)
    differences = []
    for saved in pilot_calls:
        axioms, option, goal = _our_call(saved)
        result = call(axioms, option, goal, program=real_prover)
        pilot = saved["pilot_result"]
        ours = (result["ending"], result["processed"], result["generated"], result["terms"],
                counts_unprocessed(result["output"]))
        theirs = (PILOT_ENDING[pilot["status"]], pilot["processed"], pilot["generated"], pilot["tb"], pilot["unprocessed"])
        if ours != theirs:
            differences.append(f"{saved['theory']} {saved['gi']} {saved['call']}: ours {ours}, pilot's {theirs}")
    assert not differences, f"{len(differences)} of 200 calls differ:\n" + "\n".join(differences)


def counts_unprocessed(output):
    found = re.findall(r"^# Current number of unprocessed clauses:\s*(\d+)", output, re.M)
    return int(found[0]) if found else None


@pytest.mark.slow
def test_one_call_three_times_at_once_gives_the_same_result(pilot_calls, real_prover):
    saved = next(c for c in pilot_calls if c["option"] is not None and c["pilot_result"]["status"] == "limit")
    axioms, option, goal = _our_call(saved)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda _: call(axioms, option, goal, program=real_prover), range(3)))
    assert results[0]["ending"] == CLAUSE_LIMIT
    assert all(r == results[0] for r in results)


@pytest.mark.slow
@pytest.mark.parametrize("setting", list(MEMORY_SETTINGS))
def test_borderline_calls_whatever_memory_setting_the_caller_has(real_prover, monkeypatch, setting):
    """50 pilot calls near an ending's edge (proved in 140 or more clauses, or stopped at the limit of 160),
    run with one of the memory settings that change E's search in the caller's environment."""
    monkeypatch.setenv(setting, MEMORY_SETTINGS[setting])
    borderline = read_jsonl_gz("borderline_calls.jsonl.gz")
    assert len(borderline) == 50
    differences = []
    for saved in borderline:
        result = call(*_our_call(saved), program=real_prover)
        pilot = saved["pilot_result"]
        ours = (result["ending"], result["processed"], result["generated"], result["terms"],
                counts_unprocessed(result["output"]))
        theirs = (PILOT_ENDING[pilot["status"]], pilot["processed"], pilot["generated"], pilot["tb"], pilot["unprocessed"])
        if ours != theirs:
            differences.append(f"{saved['theory']} {saved['gi']} {saved['call']}: ours {ours}, pilot's {theirs}")
    assert not differences, f"{len(differences)} of 50 calls differ with {setting} set:\n" + "\n".join(differences)


def test_program_checksum(stand_in, tmp_path):
    program = stand_in([])
    with open(program, "rb") as f:
        assert prover.program_checksum(program) == hashlib.sha256(f.read()).hexdigest()
    with pytest.raises(ProverError):
        prover.program_checksum(str(tmp_path / "no_such_program"))
