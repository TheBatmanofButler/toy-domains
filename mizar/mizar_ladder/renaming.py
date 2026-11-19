"""Renaming: the same problems with every symbol replaced by a meaningless code, and the model named against renamed.

Each distinct symbol gets one code, `s` and five digits (`s00412`), from a shuffle of the sorted symbols with a
generator made from the seed and the text "renaming", so similar symbols get unrelated codes. A renamed statement
is the library's statement with every symbol replaced by its code, each written in front of its arguments in
brackets (`s00412(A, B)`; a symbol without arguments is its code alone); the logic signs, `=`, the variables and
the numerals are left as they are (statements.written_in_front). `read_back` undoes it.

The comparison (`named_against_renamed`) pairs each named answer with the renamed answer to the same problem and
try. Per row: the model named and renamed with standard errors, the drop (the mean of the per-problem named score
minus renamed score) with its standard error, the shares of paired tries right under both, named only, renamed
only and neither, the forced share and mean thinking tokens under each, and the renamed model minus each program.
Scores come from scoring.py, judged afresh from the answers' text. Nothing here decides what counts as a drop.
"""
import json
import random
import re

from mizar_ladder import scoring, statements
from mizar_ladder.model_run import request_seed
from mizar_ladder.question import HEADINGS, NOTATION_RENAMED, RULE, build_question

CODE = re.compile(r"(?<![A-Za-z0-9_$])s[0-9]{5}(?![A-Za-z0-9_])")
WORD = re.compile(r"[A-Za-z0-9_]+")
LIMIT = 99999


class RenamingError(Exception):
    pass


def code_map(symbols, seed, forbidden=()):
    """{symbol: code} for the distinct `symbols`. Stops if a code would be one of `forbidden` (the symbols' names
    and the words of the question's fixed sentences)."""
    order = sorted(set(symbols))
    if len(order) > LIMIT:
        raise RenamingError(f"{len(order)} symbols, more than five digits can code")
    random.Random(f"{seed}:renaming").shuffle(order)
    codes = {symbol: f"s{n:05d}" for n, symbol in enumerate(order, 1)}
    clash = sorted(set(codes.values()) & set(forbidden))
    if clash:
        raise RenamingError(f"codes that are already names or words of the question: {clash[:5]}")
    return codes


def show_renamed(statement, codes):
    """The statement with every symbol replaced by its code. A symbol with no code stops it (RenamingError)."""
    try:
        return statements.written_in_front(statement, codes)
    except KeyError as error:
        raise RenamingError(f"a symbol without a code: {error}") from None


def read_back(text, codes):
    """The renamed text with each code replaced by its symbol again: the library's statement."""
    symbol_of = {code: symbol for symbol, code in codes.items()}

    def back(match):
        if match.group(0) not in symbol_of:
            raise RenamingError(f"an unknown code: {match.group(0)}")
        return symbol_of[match.group(0)]
    return CODE.sub(back, text)


def fixed_words(given_count):
    """The words of the renamed question that are neither variables, codes nor numerals: those of its fixed
    sentences and headings, and the labels of the given facts."""
    words = set(WORD.findall(" ".join((NOTATION_RENAMED, RULE) + HEADINGS)))
    return words | {f"G{n}" for n in range(1, given_count + 1)}


def stray_words(question, codes, variables, given_count):
    """The words (letters, digits, underscore) of a renamed question that are not a fixed word, a variable, a code
    or a numeral."""
    allowed = fixed_words(given_count) | set(codes.values()) | set(variables)
    return sorted({w for w in WORD.findall(question) if w not in allowed and not w.isdigit()})


def map_file(codes, seed):
    return json.dumps({"seed": seed, "codes": dict(sorted(codes.items()))}, indent=1) + "\n"


# ---- agreement with the named run -------------------------------------------------------------------------------
def named_run(answers, test_problems, run_seed):
    """What named_run.json holds, from the named run's answers: its settings record, model version, number of
    tries, run seed and the request seed of each problem and try. Stops (RenamingError) unless the answers are
    complete (every test problem, the same tries 1..n each, one settings record, one model version, none failed)
    and every request seed is the one `run_seed` gives."""
    if not answers:
        raise RenamingError("the named run has no answers")
    failed = [(a["problem_id"], a["try"]) for a in answers if a["failed"]]
    if failed:
        raise RenamingError(f"the named run has {len(failed)} failed answers, the first {failed[0]}")
    tries = {}
    for a in answers:
        tries.setdefault(a["problem_id"], []).append(a["try"])
    ids = [p["id"] for p in test_problems]
    if sorted(tries) != sorted(ids):
        raise RenamingError(f"the named run's problems are not the test problems: missing "
                            f"{sorted(set(ids) - set(tries))[:5]}, not test problems {sorted(set(tries) - set(ids))[:5]}")
    count = len(tries[ids[0]])
    uneven = sorted(i for i in ids if sorted(tries[i]) != list(range(1, count + 1)))
    if uneven:
        raise RenamingError(f"the named run does not have tries 1 to {count} of every problem: {uneven[:5]}")
    settings = {json.dumps(a["settings"], sort_keys=True) for a in answers}
    versions = {a["model_version"] for a in answers}
    if len(settings) != 1 or len(versions) != 1:
        raise RenamingError(f"the named run has {len(settings)} settings records and {len(versions)} model versions")
    wrong = [(a["problem_id"], a["try"]) for a in answers
             if a["request_seed"] != request_seed(run_seed, a["problem_id"], a["try"])]
    if wrong:
        raise RenamingError(f"the named run's request seeds are not those of run seed {run_seed}: "
                            f"{len(wrong)} differ, the first {wrong[0]}")
    seeds = {(a["problem_id"], a["try"]): a["request_seed"] for a in answers}
    return {"settings": answers[0]["settings"], "model_version": versions.pop(), "tries": count, "run_seed": run_seed,
            "request_seeds": {i: [seeds[(i, t)] for t in range(1, count + 1)] for i in sorted(ids)}}


def differences_from_named_run(named, settings, model_version, tries, run_seed, problems, other_allowance=False):
    """What a renamed run about to start would do differently from the named run (`named`, named_run.json): its
    settings on any key but `renamed`, its model version, its number of tries, its problems, and the request seed
    of any problem and try. Empty when they agree. With `other_allowance`, `thinking_allowance` is left out of the
    settings compared, and must differ from the named run's."""
    found = []
    free = ("renamed", "thinking_allowance") if other_allowance else ("renamed",)
    mine = {k: v for k, v in settings.items() if k not in free}
    theirs = {k: v for k, v in named["settings"].items() if k not in free}
    if other_allowance and settings["thinking_allowance"] == named["settings"]["thinking_allowance"]:
        found.append(f"--other-allowance with the named run's own thinking allowance "
                     f"({named['settings']['thinking_allowance']})")
    keys = sorted(k for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k))
    if keys:
        found.append(f"settings differ: {', '.join(keys)}")
    if model_version != named["model_version"]:
        found.append(f"model version {model_version!r}, the named run's {named['model_version']!r}")
    if tries != named["tries"]:
        found.append(f"{tries} tries, the named run's {named['tries']}")
    ids = sorted(p["id"] for p in problems)
    if ids != sorted(named["request_seeds"]):
        found.append("the problems are not the named run's")
    else:
        for problem_id in ids:
            for t in range(1, min(tries, named["tries"]) + 1):
                if request_seed(run_seed, problem_id, t) != named["request_seeds"][problem_id][t - 1]:
                    found.append(f"request seeds differ (run seed {run_seed}, the named run's {named['run_seed']}): "
                                 f"the first at {problem_id} try {t}")
                    return found
    return found


def check_seeds_and_questions(named, renamed, renamed_problems):
    """Stops (RenamingError) at the first renamed answer whose request seed is not the named answer's for the same
    problem and try, or whose question is not the renamed question of its problem."""
    seeds = {(a["problem_id"], a["try"]): a["request_seed"] for a in named}
    problems = {p["id"]: p for p in renamed_problems}
    for a in renamed:
        if a["request_seed"] != seeds[(a["problem_id"], a["try"])]:
            raise RenamingError(f"{a['problem_id']} try {a['try']}: request seed {a['request_seed']}, the named "
                                f"answer's {seeds[(a['problem_id'], a['try'])]}")
        if a["problem_id"] not in problems or a["question"] != build_question(problems[a["problem_id"]]):
            raise RenamingError(f"{a['problem_id']} try {a['try']}: its question is not the renamed question of "
                                "its problem")


# ---- named against renamed ---------------------------------------------------------------------------------------
def _setting_key(answer, free=()):
    settings = {k: v for k, v in answer["settings"].items() if k != "renamed" and k not in free}
    return json.dumps({"settings": settings, "model_version": answer["model_version"]}, sort_keys=True)


def check_pairs(named, renamed, allowance=None):
    """Stops (RenamingError) unless the renamed answers are for the same problems and tries as the named ones,
    every renamed answer is marked renamed and no named one is, and both agree on every setting but `renamed`.
    With `allowance` (a renamed run at another thinking allowance), `thinking_allowance` may differ, and every
    renamed answer's must be `allowance`."""
    free = () if allowance is None else ("thinking_allowance",)
    if any(a["settings"].get("renamed") for a in named):
        raise RenamingError("the named answers hold renamed ones")
    if not all(a["settings"].get("renamed") is True for a in renamed):
        raise RenamingError("the renamed answers hold answers not marked renamed")
    pairs = [(a["problem_id"], a["try"]) for a in named]
    others = [(a["problem_id"], a["try"]) for a in renamed]
    if sorted(pairs) != sorted(others) or len(set(others)) != len(others):
        missing = sorted(set(pairs) - set(others))[:5]
        extra = sorted(set(others) - set(pairs))[:5]
        raise RenamingError(f"the renamed answers are not for the named answers' problems and tries: missing "
                            f"{missing}, not named {extra}")
    keys = {_setting_key(a, free) for a in named} | {_setting_key(a, free) for a in renamed}
    if len(keys) != 1:
        raise RenamingError("the named and renamed answers were not asked under the same settings (apart from "
                            + ("`renamed` and `thinking_allowance`" if free else "`renamed`")
                            + f"): {len(keys)} different settings")
    if allowance is not None:
        other = sorted({a["settings"]["thinking_allowance"] for a in renamed} - {allowance})
        if other:
            raise RenamingError(f"answers in the file for a thinking allowance of {allowance} were asked with {other}")


def _right(answers, test_problems):
    right = {p["id"]: scoring.right_options(p) for p in test_problems}
    return {(a["problem_id"], a["try"]): scoring.model_option(a) in right[a["problem_id"]] for a in answers}


def named_against_renamed(test_problems, program_picks, named, renamed, tries=5, allowance=None):
    check_pairs(named, renamed, allowance)
    by_name = scoring.scores_by_row(test_problems, program_picks, named, tries)
    by_code = scoring.scores_by_row(test_problems, program_picks, renamed, tries)
    named_right, renamed_right = _right(named, test_problems), _right(renamed, test_problems)
    named_counts = scoring.model_right_counts(test_problems, named, tries)
    renamed_counts = scoring.model_right_counts(test_problems, renamed, tries)
    table = {}
    for name_of_row, ids in scoring.rows(test_problems).items():
        one, two = by_name[name_of_row], by_code[name_of_row]
        drops = [(named_counts[i] - renamed_counts[i]) / tries for i in ids]
        paired = [(named_right[(i, t)], renamed_right[(i, t)]) for i in ids for t in range(1, tries + 1)]
        table[name_of_row] = {
            "problems": len(ids), "tries_paired": len(paired),
            "model_named": one["model"], "model_named_standard_error": one["model_standard_error"],
            "model_renamed": two["model"], "model_renamed_standard_error": two["model_standard_error"],
            "drop": {"mean": sum(drops) / len(drops), "standard_error": scoring.standard_error(drops)},
            "both_right": sum(a and b for a, b in paired) / len(paired),
            "named_only": sum(a and not b for a, b in paired) / len(paired),
            "renamed_only": sum(b and not a for a, b in paired) / len(paired),
            "neither": sum(not a and not b for a, b in paired) / len(paired),
            "forced_share_named": one["forced_share"], "forced_share_renamed": two["forced_share"],
            "thinking_tokens_named": one["thinking_tokens_mean"],
            "thinking_tokens_renamed": two["thinking_tokens_mean"],
            "renamed_minus_program": two["model_minus_program"]}
    return table


def two_allowances(test_problems, plain, other, tries=5):
    """The renamed model at the named run's thinking allowance (`plain`) and at another (`other`), on the same
    problems and tries (both already checked against the named answers): per row, each score with its standard
    error, the difference (the mean over problems of the score at the other allowance minus the score at the
    named one) with its standard error, the shares of paired tries right under both, at the named allowance only,
    at the other only and neither, and the forced share and mean thinking tokens under each."""
    plain_right, other_right = _right(plain, test_problems), _right(other, test_problems)
    plain_counts = scoring.model_right_counts(test_problems, plain, tries)
    other_counts = scoring.model_right_counts(test_problems, other, tries)
    table = {}
    for name_of_row, ids in scoring.rows(test_problems).items():
        id_set = set(ids)
        one = scoring.answer_use([a for a in plain if a["problem_id"] in id_set])
        two = scoring.answer_use([a for a in other if a["problem_id"] in id_set])
        first = [plain_counts[i] / tries for i in ids]
        second = [other_counts[i] / tries for i in ids]
        differences = [b - a for a, b in zip(first, second)]
        paired = [(plain_right[(i, t)], other_right[(i, t)]) for i in ids for t in range(1, tries + 1)]
        table[name_of_row] = {
            "problems": len(ids), "tries_paired": len(paired),
            "at_named_allowance": sum(first) / len(ids),
            "at_named_allowance_standard_error": scoring.standard_error(first),
            "at_other_allowance": sum(second) / len(ids),
            "at_other_allowance_standard_error": scoring.standard_error(second),
            "difference": {"mean": sum(differences) / len(ids),
                           "standard_error": scoring.standard_error(differences)},
            "both_right": sum(a and b for a, b in paired) / len(paired),
            "named_allowance_only": sum(a and not b for a, b in paired) / len(paired),
            "other_allowance_only": sum(b and not a for a, b in paired) / len(paired),
            "neither": sum(not a and not b for a, b in paired) / len(paired),
            "forced_share_named_allowance": one["forced_share"], "forced_share_other_allowance": two["forced_share"],
            "thinking_tokens_named_allowance": one["thinking_tokens_mean"],
            "thinking_tokens_other_allowance": two["thinking_tokens_mean"]}
    return table
