%------
% File     : ALG003-1 : TPTP v0.0 (made up, for tests).
% Domain   : Made up, for tests
% Status   : Unsatisfiable
%------
cnf(right_unit,axiom, p(X,q) = X ).
cnf(left_unit,axiom, p(q,X) = X ).
cnf(g,negated_conjecture, p(a,p(q,b)) != p(a,b) ).
