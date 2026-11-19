"""Tests of stage 1b on the made-up library's two test problems (seed 7: t2_xboole_1 and t4_xboole_1, see
test_problems.py): the files it writes, the same bytes twice, test_problems.jsonl left as it was, and each of its
three checks made to fail by a planted fault; named_run.json from a complete named run, and each way a named run
that is not complete stops it."""
import importlib.util
import json
from pathlib import Path

import pytest
from conftest import MADE_UP, checksums_of

from mizar_ladder import renaming, statements
from mizar_ladder.model_run import request_seed
from mizar_ladder.problems import read_jsonl
from mizar_ladder.question import NOTATION_RENAMED, build_question

STAGES = Path(__file__).resolve().parent.parent / "stages"


def stage(name):
    spec = importlib.util.spec_from_file_location(name, STAGES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def built(folder, library=MADE_UP):
    """Stage 1 on `library`, seed 7, 2 test problems, into folder/data; returns (data, checksums file)."""
    folder.mkdir(parents=True, exist_ok=True)
    checksums = folder / "checksums.json"
    checksums.write_text(json.dumps(checksums_of(library)))
    data = folder / "data"
    stage("1_build_problems").main(["--data", str(data), "--library", str(library), "--seed", "7", "--test-count",
                                    "2", "--checksums", str(checksums)])
    write_named(data, named_answers(data))
    return data, checksums


SETTINGS = {"thinking_allowance": 8000, "sampling": {"temperature": 0.6}}


def named_answers(data, run_seed=7, tries=5):
    """A complete named run: every test problem, tries 1 to `tries`, one settings record, one model version."""
    return [{"problem_id": p["id"], "try": t, "failed": False, "settings": dict(SETTINGS), "model_version": "m@1",
             "request_seed": request_seed(run_seed, p["id"], t), "answer_text": "FACT: 1"}
            for t in range(1, tries + 1) for p in read_jsonl(data / "test_problems.jsonl")]


def write_named(data, answers):
    (data / "raw").mkdir(exist_ok=True)
    (data / "raw" / "model_answers.jsonl").write_text("".join(json.dumps(a) + "\n" for a in answers))


def stage_1b(data, checksums, library=MADE_UP, module=None):
    (module or stage("1b_rename")).main(["--data", str(data), "--library", str(library), "--checksums",
                                         str(checksums)])


def test_the_files_written_twice_the_same(tmp_path, made_up, capsys):
    data, checksums = built(tmp_path)
    named = (data / "test_problems.jsonl").read_bytes()
    stage_1b(data, checksums)
    first = {name: (data / name).read_bytes() for name in ("rename_map.json", "test_problems_renamed.jsonl")}
    stage_1b(data, checksums)
    assert {name: (data / name).read_bytes() for name in first} == first
    assert (data / "test_problems.jsonl").read_bytes() == named
    problems, renamed = read_jsonl(data / "test_problems.jsonl"), read_jsonl(data / "test_problems_renamed.jsonl")
    mapping = json.loads(first["rename_map.json"])
    codes = mapping["codes"]
    assert mapping["seed"] == 7
    names = {n for p in problems for n in [p["theorem"]] + [f["name"] for f in p["given"] + p["options"]]}
    assert set(codes) == {s for n in names for s in statements.symbols(made_up.statement(n))}
    for problem, record in zip(problems, renamed):
        # The same record, every statement renamed, "renamed": true added at the end.
        assert list(record) == list(problem) + ["renamed"] and record["renamed"] is True
        assert {k: v for k, v in record.items() if k not in ("statement", "given", "options", "renamed")} == {
            k: v for k, v in problem.items() if k not in ("statement", "given", "options")}
        assert record["statement"] == renaming.show_renamed(made_up.statement(problem["theorem"]), codes)
        assert [o["name"] for o in record["options"]] == [o["name"] for o in problem["options"]]
        assert all(o["statement"] == renaming.show_renamed(made_up.statement(o["name"]), codes)
                   for o in record["options"])
        assert build_question(record).startswith(NOTATION_RENAMED)
    printed = capsys.readouterr().out
    assert f"{len(codes)} symbols coded (seed 7); the three checks hold on all 2 problems" in printed
    assert f"test-0001 theorem {problems[0]['theorem']}:" in printed


def test_a_fault_in_reading_back_stops_it(tmp_path, monkeypatch, capsys):
    data, checksums = built(tmp_path)
    module = stage("1b_rename")
    monkeypatch.setattr(module.renaming, "read_back", lambda text, codes: text)       # the codes stay
    with pytest.raises(SystemExit, match="failed checks on the renamed problems"):
        stage_1b(data, checksums, module=module)
    assert "read back is not the library's statement" in capsys.readouterr().out
    assert not (data / "test_problems_renamed.jsonl").exists()


def test_two_facts_with_one_renamed_text_stop_it(tmp_path, made_up_copy, capsys):
    # The copy's statement of one option of test-0001 is made that of another option, after the build.
    data, _ = built(tmp_path / "one", made_up_copy.path)
    options = read_jsonl(data / "test_problems.jsonl")[0]["options"]
    one, other = options[0]["name"], options[1]["name"]
    library = made_up_copy.load()
    path = made_up_copy.path / "statements"
    path.write_text(path.read_text().replace(f"fof({one}, axiom, {library.statement(one)}).",
                                             f"fof({one}, axiom, {library.statement(other)}).", 1))
    checksums = tmp_path / "checksums.json"
    checksums.write_text(json.dumps(checksums_of(made_up_copy.path)))
    with pytest.raises(SystemExit, match="failed checks"):
        stage_1b(data, checksums, made_up_copy.path)
    assert "test-0001: two of its facts have the same renamed text" in capsys.readouterr().out


def test_a_name_left_in_a_question_stops_it(tmp_path, monkeypatch, capsys):
    # A fault that leaves one symbol unrenamed: reading back still gives the statement, but the symbol's own
    # name is a word the renamed question may not hold.
    data, checksums = built(tmp_path)
    module = stage("1b_rename")
    real = module.renaming.show_renamed

    def leaky(statement, codes):
        return real(statement, dict(codes, k1_basic_0="k1_basic_0"))
    monkeypatch.setattr(module.renaming, "show_renamed", leaky)
    with pytest.raises(SystemExit, match="failed checks"):
        stage_1b(data, checksums, module=module)
    assert "words in its renamed question that are not allowed: ['k1_basic_0']" in capsys.readouterr().out


def test_problems_of_two_seeds_and_a_missing_code_stop_it(tmp_path, monkeypatch):
    data, checksums = built(tmp_path)
    problems = read_jsonl(data / "test_problems.jsonl")
    (data / "test_problems.jsonl").write_text(
        "".join(json.dumps(dict(p, seed=7 + n)) + "\n" for n, p in enumerate(problems)))
    with pytest.raises(SystemExit, match="built with 2 seeds"):
        stage_1b(data, checksums)
    data, checksums = built(tmp_path / "again")
    module = stage("1b_rename")
    real = module.renaming.code_map
    monkeypatch.setattr(module.renaming, "code_map",
                        lambda *a: {k: v for k, v in real(*a).items() if k != "k1_basic_0"})
    with pytest.raises(SystemExit, match="STOP: a symbol without a code"):
        stage_1b(data, checksums, module=module)


def test_named_run_json(tmp_path, capsys):
    data, checksums = built(tmp_path)
    stage_1b(data, checksums)
    named = json.loads((data / "named_run.json").read_text())
    assert named == {"settings": SETTINGS, "model_version": "m@1", "tries": 5, "run_seed": 7,
                     "request_seeds": {i: [request_seed(7, i, t) for t in range(1, 6)] for i in ("test-0001", "test-0002")}}
    assert "named run: 5 tries of 2 problems (10 request seeds), run seed 7, model m@1" in capsys.readouterr().out
    # Another run seed, given: its seeds are checked against it.
    write_named(data, named_answers(data, run_seed=3))
    with pytest.raises(SystemExit, match="not those of run seed 7: 10 differ, the first \\('test-0001', 1\\)"):
        stage_1b(data, checksums)
    module = stage("1b_rename")
    module.main(["--data", str(data), "--library", str(MADE_UP), "--checksums", str(checksums), "--run-seed", "3"])
    assert json.loads((data / "named_run.json").read_text())["run_seed"] == 3


def changed(answers, n, **fields):
    return [dict(a, **fields) if k == n else a for k, a in enumerate(answers)]


@pytest.mark.parametrize("change, message", [
    (lambda a: [], "the named run has no answers"),
    (lambda a: changed(a, 3, failed=True), "1 failed answers, the first \\('test-0002', 2\\)"),
    (lambda a: [x for x in a if x["problem_id"] != "test-0002"], "missing \\['test-0002'\\]"),
    (lambda a: a + [dict(a[0], problem_id="test-0009")], "not test problems \\['test-0009'\\]"),
    (lambda a: a[:-1], "does not have tries 1 to 5 of every problem: \\['test-0002'\\]"),
    (lambda a: changed(a, 4, settings={"thinking_allowance": 6000}), "2 settings records and 1 model versions"),
    (lambda a: changed(a, 4, model_version="m@2"), "1 settings records and 2 model versions"),
    (lambda a: changed(a, 5, request_seed=1), "1 differ, the first \\('test-0002', 3\\)"),
])
def test_a_named_run_that_is_not_complete_stops_it(tmp_path, change, message):
    data, checksums = built(tmp_path)
    write_named(data, change(named_answers(data)))
    with pytest.raises(SystemExit, match="STOP: .*" + message):
        stage_1b(data, checksums)
    assert not (data / "named_run.json").exists() and not (data / "test_problems_renamed.jsonl").exists()


def test_without_the_named_run_it_stops(tmp_path):
    data, checksums = built(tmp_path)
    (data / "raw" / "model_answers.jsonl").unlink()
    with pytest.raises(SystemExit, match="model_answers.jsonl does not exist: the named run comes first"):
        stage_1b(data, checksums)
