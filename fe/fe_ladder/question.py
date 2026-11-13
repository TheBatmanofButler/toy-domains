"""The text the model is shown for one problem.

Everything up to the list of substitutions is the earlier run's layout, unchanged: the sentence about f, the
numbered equation, the goal, what counts as proved, the 13 substitutions with their numbers, the note on
two-part substitutions and how to write a substitution. The last paragraph states the rule for a right move.
The text depends on the equation and the goal only: it never contains the depth, the right moves or anything
from the planted proof.
"""
from fe_ladder.identities import SUBSTITUTIONS

SYSTEM_TEXT = "You are an expert in functional equations. Follow the requested answer format exactly."

INTRO = ("Let f be an unknown function from the rationals to the rationals. The numbered identities below hold for "
         "all rational x and y.")
PROVED = ("The goal counts as proved once it is a linear combination, with rational coefficients, of the numbered "
          "identities (each distinct term f(...) and each monomial in x, y is treated as an independent unknown).")
SUBSTITUTIONS_HEAD = ("Substitutions. A move applies one of the substitutions below to one numbered identity; the "
                      "resulting identity is added to the list with the next number. The allowed substitutions are "
                      "exactly:")
TWO_PARTS = "Substitutions with two parts (σ1, σ8, σ13) are applied simultaneously."
HOW_TO_WRITE = "Write the substitution as shown (for example `y=0` or `x=x+y, y=-y`)."
RULE = ("A move is correct if it is the first move of a shortest possible proof of the goal. Each substitution "
        "applied to one identity counts as one move. Give one correct move, with the substitution written exactly "
        "as it appears in the list. Answer with `MOVE: (<identity number>) <substitution>`.")


def build_question(equation_text, goal_text):
    """`equation_text`, `goal_text`: as in the problem files (identity_text.write_identity)."""
    listed = "\n".join(f"  σ{n}: {s}" for n, s in enumerate(SUBSTITUTIONS, 1))
    return (f"{INTRO}\n\n(1) {equation_text}\n\nGoal: prove the identity {goal_text}\n{PROVED}\n\n"
            f"{SUBSTITUTIONS_HEAD}\n{listed}\n{TWO_PARTS}\n{HOW_TO_WRITE}\n\n{RULE}")
