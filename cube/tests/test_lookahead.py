"""Tests of programs/lookahead.py: perfect near solved, five cubes worked by hand, and the old run's scores."""
import pytest
from conftest import read_fixture

from cube_ladder.cube import SOLVED, TURNS, apply_turn, apply_turns
from cube_ladder.programs.lookahead import picks, search
from cube_ladder.scoring import score_pick


def weights_by_turn(pick):
    return {turn: weight for turn, weight in zip(TURNS, pick) if weight > 0}


def plain_right_turns(cube, distance, table):
    return [turn for turn in TURNS if table.get(apply_turn(cube, turn)) == distance - 1]


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_scores_1_on_every_cube_within_its_depth(depth, distance_table):
    # Depth 3 is checked on every cube within 3 turns; depths 1 and 2 on every cube within 1 and 2 turns.
    near = [(cube, d) for cube, d in distance_table.items() if 1 <= d <= depth]
    assert len(near) == {1: 18, 2: 261, 3: 3501}[depth]
    for cube, distance in near:
        (pick,) = picks([cube], depth)
        assert score_pick(pick, plain_right_turns(cube, distance, distance_table)) == pytest.approx(1)


def test_hand_worked_one_quarter_turn():
    # The cube after R: R' solves it at once.
    pick, examined = search(apply_turn(SOLVED, "R"), 1)
    assert weights_by_turn(pick) == {"R'": 1.0}
    assert examined == 18


def test_hand_worked_half_turn_stops_at_the_first_turn():
    # The cube after R2, looked at 3 turns deep: R2 solves it after one turn, so the search stops there and
    # examines only the 18 cubes one turn away.
    pick, examined = search(apply_turn(SOLVED, "R2"), 3)
    assert weights_by_turn(pick) == {"R2": 1.0}
    assert examined == 18


def test_hand_worked_two_opposite_faces_two_deep():
    # The cube after R L. R and L do not interfere, so both L' R' and R' L' solve it in two: a tie.
    pick, examined = search(apply_turns(SOLVED, "R L"), 2)
    assert weights_by_turn(pick) == {"R'": 0.5, "L'": 0.5}
    assert examined == 18 + 18 * 15


def test_hand_worked_two_opposite_faces_one_deep():
    # The cube after R L, one turn deep: nothing solves it. R' (or L') undoes one layer, leaving a cube one
    # quarter turn from solved: 12 pieces, 36 stickers in place. Any other turn leaves both R and L layers
    # out of place. A U turn, say, keeps at most the 2 untouched bottom middle edges (DF, DB) plus at most
    # the 8 pieces of the U layer: 10 < 12. R or R2 (and L or L2) leave both layers turned: only the
    # 4 middle-slice edges are home. So R' and L' tie for best.
    pick, _ = search(apply_turns(SOLVED, "R L"), 1)
    assert weights_by_turn(pick) == {"R'": 0.5, "L'": 0.5}


def test_hand_worked_two_faces_that_interfere():
    # The cube after R U. R and U do not commute, so the only two-turn solution is U' R'.
    pick, _ = search(apply_turns(SOLVED, "R U"), 2)
    assert weights_by_turn(pick) == {"U'": 1.0}


def test_full_depth_examines_every_sequence():
    # No solved cube within 3 turns: 18 + 18*15 + 18*15*15 sequences, none turning a face twice running.
    far = apply_turns(SOLVED, "R U F' L2 D B' R2 U'")
    assert search(far, 3)[1] == 18 + 270 + 4050


def test_agrees_with_the_old_run_far_from_solved():
    # The old states are 12 to 16 turns away, so stopping at solved never applies and the old lookahead
    # (which always looked exactly k turns ahead) must score the same.
    for state in read_fixture("old_run_states.jsonl"):
        for depth in (1, 2, 3):
            (pick,) = picks([state["cube"]], depth)
            assert score_pick(pick, state["right_turns"]) == pytest.approx(state["lookahead_scores"][depth - 1])


def test_depth_must_be_positive():
    with pytest.raises(ValueError):
        search(SOLVED, 0)
