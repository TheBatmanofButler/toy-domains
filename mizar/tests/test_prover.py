"""Tests for prover.py: how a call ended, on real outputs of every ending on these problems; the words each rests
on; the facts a real proof uses; the input text; running a call through the stand-in prover, which shows the
prover is started in the fixed environment and both its output streams are kept. Slow tests (need the prover):
the version check; the saved calls far from the limit, made again, give their ending (whatever the caller's
memory settings); one proof made three times at once is a proof each time. The prover's search changes from run
to run, so no test rests on its clause counts being the same twice."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import FIXTURES, environments_seen, read_json_gz
from made_up_outputs import output as made_up_output
from stand_in_prover import PRINT_ENVIRONMENT

from mizar_ladder import prover
from mizar_ladder.prover import (CLAUSE_LIMIT, ENDINGS, NOTHING_LEFT, PROVED, TERM_CAP_REACHED, UNREADABLE,
                                 ProverError, call, check_version, cleaned, command, counts, how_it_ended,
                                 input_text, used_facts)

# Endings that could not be produced on these problems with the pinned command line, and how they were made.
NOT_PRODUCED_WITH_PINNED_COMMAND = {"memory cap": "memory cap of 1 MB", "unreadable": "an input with a syntax error"}
FACTS = [("d1_a", "p(A)")]
THEOREM = ("t1_a", "q")


@pytest.fixture(scope="module")
def endings():
    return [dict(e, output=cleaned(e["output"], e["input_name"])) for e in read_json_gz("endings.json.gz")]


def test_every_ending_on_a_real_output(endings):
    assert sorted({e["ending"] for e in endings}) == sorted(ENDINGS)
    for saved in endings:
        assert how_it_ended(saved["output"], saved["limit"]) == saved["ending"], saved["theorem"]
    made = {e["ending"]: e["made_with"] for e in endings if e["made_with"] != "pinned command"}
    assert made == NOT_PRODUCED_WITH_PINNED_COMMAND


def test_the_words_each_ending_rests_on(endings):
    """The lines named in prover.py are in the saved outputs as written there."""
    words = {"proved": ["# Proof found!", "# SZS status Theorem"],
             "clause limit": ["# Failure: User resource limit exceeded!", "# SZS status ResourceOut"],
             "nothing left": ["# No proof found!", "# SZS status CounterSatisfiable"],
             "term cap": ["# Failure: User resource limit exceeded!", "# SZS status ResourceOut"],
             "memory cap": ["# Failure: Resource limit exceeded (memory)"],
             "time cap": ["# Failure: Resource limit exceeded (time)"]}
    for saved in endings:
        lines = saved["output"].splitlines()
        assert all(w in lines for w in words.get(saved["ending"], [])), saved["ending"]
        if saved["ending"] in prover.DECIDING:
            assert prover.every_axiom_read(saved["output"])
    term = next(e for e in endings if e["ending"] == "term cap")
    assert counts(term["output"])["terms"] >= prover.TERM_CAP and counts(term["output"])["processed"] < term["limit"]
    # In automatic mode the clauses processed in the presaturation interreduction are printed with the rest
    # but not counted against the limit: 672 printed at a limit of 250.
    past = [e for e in endings if e["ending"] == "clause limit" and counts(e["output"])["processed"] > e["limit"]]
    assert [counts(e["output"])["processed"] for e in past] == [672]


@pytest.mark.parametrize("text, ending", [
    ("", UNREADABLE),
    ("eprover: Type error\n", UNREADABLE),
    (made_up_output(CLAUSE_LIMIT, processed=250), CLAUSE_LIMIT),
    (made_up_output(CLAUSE_LIMIT, processed=900), CLAUSE_LIMIT),           # presaturation counted in the total
    (made_up_output(CLAUSE_LIMIT, processed=249), UNREADABLE),             # stopped before the limit, by something else
    (made_up_output(TERM_CAP_REACHED, processed=12), TERM_CAP_REACHED),
    (made_up_output(TERM_CAP_REACHED, processed=70000), TERM_CAP_REACHED),   # past both: the term cap, never "does not prove"
    (made_up_output(PROVED, ["d1_a"]), PROVED),
    (made_up_output(NOTHING_LEFT), NOTHING_LEFT),
    (made_up_output(PROVED, ["d1_a"]).replace("# No SInE strategy applied\n", ""), UNREADABLE),   # axioms may be pruned
    (made_up_output(PROVED, ["d1_a"]).replace("SinE    : 0", "SinE    : 3"), UNREADABLE),       # axioms were pruned
    (made_up_output(CLAUSE_LIMIT, processed=250).replace("# Removed by relevancy pruning/SinE    : 0\n", ""), UNREADABLE),
    (made_up_output(PROVED, ["d1_a"]) + made_up_output(CLAUSE_LIMIT, processed=250), UNREADABLE),   # two endings
    ("# Proof found!\n# SZS status Unsatisfiable\n", UNREADABLE),           # the status of the TPTP code's problems
    ("# Failure: User resource limit exceeded!\n# SZS status ResourceOut\n# Processed clauses : 250\n", UNREADABLE),
])
def test_outputs_that_fit_no_ending_or_more_than_one(text, ending):
    assert how_it_ended(text, 250) == ending


def test_counts_missing_or_printed_twice_are_none():
    assert counts("# Processed clauses : 3\n# Processed clauses : 4\n")["processed"] is None
    assert counts("") == {"processed": None, "generated": None, "terms": None}


def test_a_real_output_past_both_the_clause_limit_and_the_term_cap_is_the_term_cap(endings):
    term = next(e for e in endings if e["ending"] == "term cap")
    assert counts(term["output"])["processed"] >= 4000          # past any limit from 250 to 4,000 too
    assert how_it_ended(term["output"], 4000) == TERM_CAP_REACHED and how_it_ended(term["output"], 250) == TERM_CAP_REACHED


def test_nothing_left_needs_both_of_the_provers_lines(endings):
    saturated = next(e["output"] for e in endings if e["ending"] == "nothing left")
    for line in ("# No proof found!", "# SZS status CounterSatisfiable"):
        without = "\n".join(kept for kept in saturated.splitlines() if kept.strip() != line) + "\n"
        assert how_it_ended(without, 250) == UNREADABLE, line


def test_usage_lines_and_the_input_files_name_are_taken_out():
    saved = read_json_gz("endings.json.gz")
    raw = saved[0]
    assert "#    Propositional solver time         : 0.000" in raw["output"]
    assert f"file('{raw['input_name']}'," in raw["output"]
    clean = cleaned(raw["output"], raw["input_name"])
    assert "solver time" not in clean and raw["input_name"] not in clean
    assert "file('problem.p', t27_xtuple_0))." in clean
    memory = next(e for e in saved if e["ending"] == "memory cap")
    assert "# User time" in memory["output"] and "resident set size" in memory["output"]
    clean = cleaned(memory["output"], memory["input_name"])
    assert "# User time" not in clean and "resident set size" not in clean
    assert "# Failure: Resource limit exceeded (memory)" in clean


def test_used_facts_on_three_real_proofs():
    proofs = read_json_gz("proofs.json.gz")
    assert len(proofs) == 3
    for proof in proofs:
        found = used_facts(cleaned(proof["output"], proof["input_name"]))
        assert found == proof["used"] and proof["theorem"] not in found
        assert (proof["held_back"] in found) == proof["with_held_back"]
    assert used_facts(made_up_output(CLAUSE_LIMIT)) == [] and used_facts(made_up_output(PROVED, ["a_b", "a_b"])) == ["a_b"]


def test_input_text_for_a_fixed_problem_equals_the_saved_copy():
    parts = json.loads((FIXTURES / "input_parts_fixed_problem.json").read_text())
    text = input_text([tuple(f) for f in parts["facts"]], tuple(parts["option"]), tuple(parts["theorem"]))
    assert text == (FIXTURES / "input_text_fixed_problem.txt").read_text()
    lines = text.splitlines()
    assert len(lines) == len(parts["facts"]) + 2 and lines[-2].startswith(f"fof({parts['option'][0]}, axiom, ")
    assert lines[-1].startswith(f"fof({parts['theorem'][0]}, conjecture, ")
    assert input_text(FACTS, None, THEOREM) == "fof(d1_a, axiom, p(A)).\nfof(t1_a, conjecture, q).\n"


def test_command_is_the_pinned_one():
    assert command(250) == ["--print-statistics", "--silent", "--cpu-limit=60", "--processed-clauses-limit=250",
                            "--tb-insert-limit=1000000", "--memory-limit=2000", "--auto", "--proof-object",
                            "--free-numbers"]


def test_a_call_through_the_stand_in(stand_in_prover):
    program = stand_in_prover([(["--processed-clauses-limit=250 ", "fof(t2_a, axiom, r)."],
                                made_up_output(PROVED, ["t2_a", "d1_a"], processed=40))])
    result = call(FACTS, ("t2_a", "r"), THEOREM, 250, program=program)
    assert result["ending"] == PROVED and result["used"] == ["t2_a", "d1_a"] and result["processed"] == 40
    assert result["exit_code"] == 0 and "file('/tmp/tmpabc.p', t2_a)" in result["output"]
    nothing = call(FACTS, None, THEOREM, 250, program=program)
    assert nothing["ending"] == UNREADABLE and nothing["processed"] is None and nothing["used"] == []


def test_check_version_and_checksum(stand_in_prover, tmp_path):
    program = stand_in_prover([])
    check_version(program)
    with pytest.raises(ProverError):
        check_version(stand_in_prover([], version="E 2.5 Avongrove"))
    with open(program, "rb") as f:
        assert prover.program_checksum(program) == hashlib.sha256(f.read()).hexdigest()
    with pytest.raises(ProverError):
        prover.program_checksum(str(tmp_path / "no_such_program"))


# The memory settings of the C library that were seen to change E 2.6's search (by the TPTP code).
MEMORY_SETTINGS = {"MALLOC_MMAP_THRESHOLD_": "67108864", "MALLOC_TOP_PAD_": "1048576",
                   "GLIBC_TUNABLES": "glibc.malloc.mmap_threshold=67108864"}
FIXED = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}


@pytest.mark.parametrize("setting", [None, *MEMORY_SETTINGS])
def test_the_prover_is_started_in_the_fixed_environment(stand_in_prover, monkeypatch, tmp_path, setting):
    """Whatever the caller's environment holds, the prover sees exactly PATH=/usr/bin:/bin and LC_ALL=C."""
    if setting is not None:
        monkeypatch.setenv(setting, MEMORY_SETTINGS[setting])
    monkeypatch.setenv("SOMETHING_OF_THE_CALLERS", "1")
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/local/bin:/usr/bin:/bin")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    program = stand_in_prover([([], PRINT_ENVIRONMENT)])
    check_version(program)
    found = call(FACTS, None, THEOREM, 250, program=program)
    assert json.loads(found["output"]) == FIXED
    seen = [json.loads(line) for line in environments_seen(program).read_text().splitlines()]
    assert seen == [FIXED, FIXED]     # the version check and the call


def test_both_output_streams_are_in_a_calls_output(stand_in_prover, endings):
    memory = next(e["output"] for e in endings if e["ending"] == "memory cap")
    assert "eprover: Out of Memory" in memory
    on_stdout = "\n".join(line for line in memory.splitlines() if "Out of Memory" not in line) + "\n"
    program = stand_in_prover([([], [on_stdout, "eprover: Out of Memory\n"])])
    found = call(FACTS, None, THEOREM, 250, program=program)
    assert found["output"] == on_stdout + "eprover: Out of Memory\n" and found["ending"] == prover.MEMORY_CAP_REACHED


def far_from_the_limit(saved):
    """The saved calls whose ending a change in the prover's search will not move: proofs and finished searches
    in a fifth of the limit or less, the memory cap of 1 MB, and the input with a syntax error. (A call at the
    clause limit, the term cap or the time cap sits at a boundary that the next run may cross.)"""
    processed = counts(cleaned(saved["output"], saved["input_name"]))["processed"]
    return (saved["ending"] in ("proved", "nothing left") and processed <= saved["limit"] / 5
            or saved["ending"] in ("memory cap", "unreadable"))


@pytest.mark.slow
def test_the_real_version_and_the_saved_calls_far_from_the_limit_again(real_prover):
    check_version(real_prover)
    chosen = [s for s in read_json_gz("endings.json.gz") if far_from_the_limit(s)]
    assert sorted(s["ending"] for s in chosen) == ["memory cap", "nothing left", "proved", "unreadable"]
    for saved in chosen:
        output, _ = prover._run(real_prover, saved["arguments"], saved["input"])
        assert how_it_ended(output, saved["limit"]) == saved["ending"], saved["theorem"]


@pytest.mark.slow
@pytest.mark.parametrize("setting", list(MEMORY_SETTINGS))
def test_the_real_prover_under_the_callers_memory_settings(real_prover, monkeypatch, setting):
    """The saved calls far from the limit, made with a memory setting in the caller's environment that would
    change E's search if it reached it: the same endings."""
    monkeypatch.setenv(setting, MEMORY_SETTINGS[setting])
    for saved in read_json_gz("endings.json.gz"):
        if far_from_the_limit(saved):
            output, _ = prover._run(real_prover, saved["arguments"], saved["input"])
            assert how_it_ended(output, saved["limit"]) == saved["ending"], (setting, saved["theorem"])


@pytest.mark.slow
def test_one_proof_three_times_at_once_is_a_proof_each_time(real_prover):
    # The fixed problem with its held-back fact proves at 4,000 in under 300 clauses: far from the limit.
    parts = json.loads((FIXTURES / "input_parts_fixed_problem.json").read_text())
    facts, option, theorem = [tuple(f) for f in parts["facts"]], tuple(parts["option"]), tuple(parts["theorem"])
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda _: call(facts, option, theorem, 4000, program=real_prover), range(3)))
    assert all(r["ending"] == PROVED for r in results)
