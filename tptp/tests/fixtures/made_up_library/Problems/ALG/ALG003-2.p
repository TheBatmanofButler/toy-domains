%------
% File     : ALG003-2 : TPTP v0.0 (made up, for tests).
% Domain   : Made up, for tests
% Status   : Unsatisfiable
%------
cnf(left_unit,axiom, r(z,Y) = Y ).
cnf(right_unit,axiom, r(Y,z) = Y ).
cnf(g,negated_conjecture, r(c,r(z,d)) != r(c,d) ).
