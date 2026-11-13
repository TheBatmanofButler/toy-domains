"""Every figure in the report is worked out here, and only here.

Scores: a pick scores the weight it puts on right turns; a model try scores 1 if its turn is right. A state's
model score is the share of its tries that are right; a distance's score is the average over its states.
Room at a distance is one minus the best simple program there. State by state, the model "gets" a state when
more than half its tries are right (3 of 5), and a program gets it when more than half its weight is on right
turns; the same bar for both. The model's turns are read afresh from its answer text, so the answer reader
can change without asking the model again.

Margins of error are given as numbers only; nothing here decides what counts as "above". A standard error is
the sample standard deviation (n - 1 in the divisor) of the per-state figures over the square root of the
number of states; with one state there is none (None). It reflects the choice of test states only.
"""
from math import comb, sqrt
from statistics import stdev

from cube_ladder.answers import read_turn
from cube_ladder.cube import TURNS

# Scores closer than this are tied (they are averages of the same few fractions).
TIE = 1e-12


class ScoringError(Exception):
    pass


def score_pick(weights, right_turns):
    if len(weights) != len(TURNS) or abs(sum(weights) - 1) > 1e-9 or min(weights) < 0:
        raise ScoringError(f"not a pick: {weights}")
    return sum(weight for weight, turn in zip(weights, TURNS) if turn in right_turns)


def _by_state(records, test_states, kind):
    """Group records by their `state_id`; every test state must be there. `kind` names the records in errors."""
    grouped = {s["id"]: [] for s in test_states}
    for record in records:
        if record["state_id"] not in grouped:
            raise ScoringError(f"{kind} for {record['state_id']}, which is not a test state")
        grouped[record["state_id"]].append(record)
    return grouped


def model_turn(answer):
    """The turn read from a saved answer's text (None if unreadable or the request failed)."""
    return None if answer["failed"] else read_turn(answer["answer_text"])


def model_right_counts(test_states, answers, tries):
    """{state id: number of right tries}, judged afresh against the state's right turns. Stops if a state
    lacks a try or an answer failed."""
    right_turns = {s["id"]: s["right_turns"] for s in test_states}
    counts = {}
    for state_id, records in _by_state(answers, test_states, "answer").items():
        if sorted(r["try"] for r in records) != list(range(1, tries + 1)):
            raise ScoringError(f"{state_id}: tries {sorted(r['try'] for r in records)}, expected 1 to {tries}")
        failed = [r["try"] for r in records if r["failed"]]
        if failed:
            raise ScoringError(f"{state_id}: tries {failed} failed; ask them again before scoring")
        counts[state_id] = sum(model_turn(r) in right_turns[state_id] for r in records)
    return counts


def program_scores(test_states, program_picks):
    """{program: {state id: score}}, scored afresh from the weights. Stops if a program lacks a state, has
    one twice, or saved a score that differs from the weights."""
    right_turns = {s["id"]: s["right_turns"] for s in test_states}
    programs = sorted({p["program"] for p in program_picks})
    scores = {}
    for program in programs:
        mine = [p for p in program_picks if p["program"] == program]
        grouped = _by_state(mine, test_states, program)
        for state_id, picks in grouped.items():
            if len(picks) != 1:
                raise ScoringError(f"{program} has {len(picks)} picks for {state_id}")
        scores[program] = {state_id: score_pick(picks[0]["weights"], right_turns[state_id])
                           for state_id, picks in grouped.items()}
        for state_id, picks in grouped.items():
            if abs(picks[0]["score"] - scores[program][state_id]) > 1e-9:
                raise ScoringError(f"{program} on {state_id}: saved score {picks[0]['score']} does not match its weights")
    return scores


def _mean(values):
    return sum(values) / len(values)


def standard_error(values):
    """Standard error of the mean of `values`; None for fewer than two values."""
    return stdev(values) / sqrt(len(values)) if len(values) > 1 else None


def chance_model_gets(right_turn_count, tries):
    """Chance that a model guessing evenly among the 18 turns is right on more than half of its tries."""
    p = right_turn_count / len(TURNS)
    return sum(comb(tries, k) * p ** k * (1 - p) ** (tries - k) for k in range(tries + 1) if 2 * k > tries)


def scores_by_distance(test_states, program_picks, answers=None, tries=5):
    """Per distance: number of states, each program's score and its standard error, the best programs, room
    and the standard error of the best program's score (`room_standard_error_of` names it: the first of the
    tied best, alphabetically), and the mean positions each lookahead examined; with answers, also the model's
    score and standard error, the mean per-state difference between the model and each program on the same
    states with its standard error, and the model's use of the answers (see answer_use)."""
    programs = program_scores(test_states, program_picks)
    right_counts = model_right_counts(test_states, answers, tries) if answers is not None else None
    searchers = sorted({p["program"] for p in program_picks if "positions_examined" in p})
    table = {}
    for distance in sorted({s["distance"] for s in test_states}):
        ids = [s["id"] for s in test_states if s["distance"] == distance]
        id_set = set(ids)
        row = {"states": len(ids), "programs": {name: _mean([scores[i] for i in ids]) for name, scores in programs.items()},
               "programs_standard_error": {name: standard_error([scores[i] for i in ids])
                                           for name, scores in programs.items()}}
        best = max(row["programs"].values())
        row["best_programs"] = sorted(name for name, score in row["programs"].items() if score >= best - TIE)
        row["room"] = 1 - best
        row["room_standard_error_of"] = row["best_programs"][0]
        row["room_standard_error"] = row["programs_standard_error"][row["room_standard_error_of"]]
        if searchers:
            row["positions_examined_mean"] = {name: _mean([p["positions_examined"] for p in program_picks
                                                           if p["program"] == name and p["state_id"] in id_set])
                                              for name in searchers}
        if answers is not None:
            model = {i: right_counts[i] / tries for i in ids}
            row["model"] = _mean(list(model.values()))
            row["model_standard_error"] = standard_error(list(model.values()))
            row["model_minus_program"] = {}
            for name, scores in programs.items():
                differences = [model[i] - scores[i] for i in ids]
                row["model_minus_program"][name] = {"mean": _mean(differences),
                                                    "standard_error": standard_error(differences)}
            row.update(answer_use([a for a in answers if a["state_id"] in id_set]))
        table[distance] = row
    return table


def state_by_state(test_states, program_picks, answers, tries=5):
    """Per program and distance: states both get, only the model, only the program, neither, and two figures
    for how many "only the model" states to expect by chance: if the model were guessing evenly among the 18
    turns, and if the model got states independently of the program (m x p: m states the program misses, p the
    share of states the model gets at that distance), with that figure's standard error sqrt(m p (1 - p))
    (None at a distance with one state)."""
    programs = program_scores(test_states, program_picks)
    right_counts = model_right_counts(test_states, answers, tries)
    table = {}
    for program, scores in programs.items():
        table[program] = {}
        for distance in sorted({s["distance"] for s in test_states}):
            here = [s for s in test_states if s["distance"] == distance]
            row = {"both": 0, "only_model": 0, "only_program": 0, "neither": 0, "only_model_expected_by_chance": 0.0}
            for state in here:
                model_gets = 2 * right_counts[state["id"]] > tries
                program_gets = scores[state["id"]] > 0.5
                key = {(True, True): "both", (True, False): "only_model",
                       (False, True): "only_program", (False, False): "neither"}[(model_gets, program_gets)]
                row[key] += 1
                if not program_gets:
                    row["only_model_expected_by_chance"] += chance_model_gets(len(state["right_turns"]), tries)
            model_gets_share = (row["both"] + row["only_model"]) / len(here)
            misses = row["only_model"] + row["neither"]
            row["only_model_expected_if_independent"] = misses * model_gets_share
            row["only_model_if_independent_standard_error"] = (
                sqrt(misses * model_gets_share * (1 - model_gets_share)) if len(here) > 1 else None)
            table[program][distance] = row
    return table


def answer_use(answers):
    """Shares of failed, unreadable, forced and cut-off-but-already-readable answers, and token use per answer
    that did not fail. An answer is unreadable when the request worked but no turn could be read from it.
    `thinking_tokens_mean` is exact but None unless the server gave token ids for every answer;
    `tokens_used_mean` counts every token the model wrote (thinking, answer, forced answer), so it is an
    upper limit on thinking."""
    worked = [a for a in answers if not a["failed"]]
    thinking = [a["thinking_tokens"] for a in worked]
    return {"answers": len(answers),
            "failed_share": _mean([bool(a["failed"]) for a in answers]),
            "unreadable_share": _mean([not a["failed"] and model_turn(a) is None for a in answers]),
            "forced_share": _mean([bool(a["forced"]) for a in answers]),
            "cut_off_but_readable_share": _mean([bool(a["cut_off_but_readable"]) for a in answers]),
            "thinking_tokens_mean": _mean(thinking) if worked and None not in thinking else None,
            "tokens_used_mean": _mean([a["tokens_used"] for a in worked]) if worked else None}


def most_cubes_written(tokens_used, tokens_per_cube):
    """An upper limit only: how many whole cubes the model could have written out in the tokens it used."""
    return tokens_used / tokens_per_cube
