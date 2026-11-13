"""Same wrong turns: when the model is wrong, is it wrong in the way a program is?

Worked out afterwards from the saved answers and picks; nothing new is asked of the model. For each program
and each distance:
- A wrong try is a try whose answer reads as one of the 18 turns (read afresh from the answer text, as in the
  rest of the scoring, never from the stored `turn`) and that turn is not right. Unreadable and failed tries
  are left out, so a cube whose tries are all right or unreadable takes no part.
- A cube's match value is the average, over its wrong tries, of the weight the program's pick puts on the
  model's turn (a program torn between three turns puts a third on each). The match rate is the average over
  the cubes with a wrong try.
- Uniform figure: per such cube, the program's total weight on wrong turns over the number of wrong turns;
  what a program guessing evenly among the wrong turns would score; averaged over the same cubes.
- Shuffle figure: per wrong try, the average weight the program puts on that same turn over every other test
  cube at that distance (whether or not the turn is right there); averaged by cube as the match value is. It
  shows how many matches come from habits alone (a model or a program that favours certain turns). It uses
  every other cube, so no random numbers are needed.
- Excess: match minus shuffle, cube by cube; and for each control program the difference between this
  program's excess and the control's on the same cubes.

Everything is by cube, because the five tries on one cube are not independent: the standard errors (as in
scoring.py: n - 1, over the square root of n) are across cubes, and there is none with fewer than two cubes.
Numbers only: nothing here decides what counts as a resemblance.
"""
from cube_ladder import scoring
from cube_ladder.cube import TURNS

PLACE = {turn: n for n, turn in enumerate(TURNS)}


def control_programs(names):
    """The programs that do no search, which serve as controls: both versions of recall and the strict
    surface reader, as named among `names` (the programs in the picks file)."""
    return sorted(name for name in names if name.startswith("recall_") or name == "surface_strict")


def wrong_tries(test_states, answers):
    """{state id: the model's readable wrong turns, one per such try}; states without one are left out."""
    right_turns = {s["id"]: s["right_turns"] for s in test_states}
    found = {}
    for state_id, records in scoring._by_state(answers, test_states, "answer").items():
        turns = [scoring.model_turn(r) for r in records]
        wrong = [t for t in turns if t is not None and t not in right_turns[state_id]]
        if wrong:
            found[state_id] = wrong
    return found


def _mean(values):
    return sum(values) / len(values) if values else None


def _cube_figures(weights, wrong, ids, right_turns):
    """{cube: (match, uniform, shuffle)} for one program at one distance, over the cubes in `wrong`.
    `weights` maps each state id to its pick; shuffle is None when the distance has no other cube."""
    figures = {}
    for cube in ids:
        if cube not in wrong:
            continue
        pick = weights[cube]
        match = _mean([pick[PLACE[t]] for t in wrong[cube]])
        wrong_turns = [t for t in TURNS if t not in right_turns[cube]]
        uniform = sum(pick[PLACE[t]] for t in wrong_turns) / len(wrong_turns)
        others = [i for i in ids if i != cube]
        shuffle = _mean([_mean([weights[i][PLACE[t]] for i in others]) for t in wrong[cube]]) if others else None
        figures[cube] = (match, uniform, shuffle)
    return figures


def _mean_and_error(values):
    return {"mean": _mean(values), "standard_error": scoring.standard_error(values)}


def same_wrong_turns(test_states, program_picks, answers, controls=None):
    """{program: {distance: row}}. Each row: `cubes` (cubes with a wrong try) and `wrong_tries` behind every
    figure; `match_rate` and its standard error; `uniform`; `shuffle`; `excess` and its standard error; and
    `excess_over_control`, {control: mean and standard error of this program's excess minus the control's,
    cube by cube} for each control other than the program itself. `controls` defaults to control_programs of
    the programs in `program_picks`. A figure that cannot be worked out (no cube with a wrong try, or for the
    shuffle no other cube at the distance) is None."""
    scoring.program_scores(test_states, program_picks)   # the same checks on the picks as the scores get
    programs = sorted({p["program"] for p in program_picks})
    controls = control_programs(programs) if controls is None else controls
    weights = {name: {p["state_id"]: p["weights"] for p in program_picks if p["program"] == name}
               for name in programs}
    right_turns = {s["id"]: s["right_turns"] for s in test_states}
    wrong = wrong_tries(test_states, answers)
    distances = sorted({s["distance"] for s in test_states})
    ids = {d: [s["id"] for s in test_states if s["distance"] == d] for d in distances}
    figures = {name: {d: _cube_figures(weights[name], wrong, ids[d], right_turns) for d in distances}
               for name in programs}

    def excess(name, d):
        return {cube: match - shuffle for cube, (match, _, shuffle) in figures[name][d].items()
                if shuffle is not None}

    table = {}
    for name in programs:
        table[name] = {}
        for d in distances:
            here = figures[name][d]
            mine = excess(name, d)
            matches = [match for match, _, _ in here.values()]
            row = {"cubes": len(here), "wrong_tries": sum(len(wrong[cube]) for cube in here),
                   "match_rate": _mean(matches), "match_rate_standard_error": scoring.standard_error(matches),
                   "uniform": _mean([uniform for _, uniform, _ in here.values()]),
                   "shuffle": _mean([shuffle for _, _, shuffle in here.values() if shuffle is not None])}
            excess_figures = _mean_and_error(list(mine.values()))
            row["excess"], row["excess_standard_error"] = excess_figures["mean"], excess_figures["standard_error"]
            row["excess_over_control"] = {}
            for control in controls:
                if control != name:
                    theirs = excess(control, d)
                    row["excess_over_control"][control] = _mean_and_error([mine[c] - theirs[c] for c in mine])
            table[name][d] = row
    return table
