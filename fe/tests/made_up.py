"""Made-up problems for the scoring tests: every problem has the same 18 options, so figures worked out by hand
on the cube's 18 turns carry over unchanged. Option n holds one move: substitution n % 13 on identity
1 + n // 13. The options' results are not needed by the scoring and are left empty."""
from fe_ladder.identities import SUBSTITUTIONS
from fe_ladder.programs.common import pick_on

OPTIONS = [{"result": "", "moves": [[1 + n // 13, SUBSTITUTIONS[n % 13]]]} for n in range(18)]
NOT_AVAILABLE = "MOVE: (3) y=x"        # identity 3 is on no made-up page


def move_text(n):
    number, substitution = OPTIONS[n]["moves"][0]
    return f"MOVE: ({number}) {substitution}"


def pick(chosen):
    """Equal weight on the option numbers in `chosen`, out of 18."""
    return pick_on(18, chosen)
