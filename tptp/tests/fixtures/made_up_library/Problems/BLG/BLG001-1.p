%------
% File     : BLG001-1 : TPTP v0.0 (made up, for tests).
% Domain   : Made up, for tests
% Status   : Unsatisfiable
%------
cnf(associativity,axiom, n(X,n(Y,Z)) = n(n(X,Y),Z) ).
cnf(left_identity,axiom, n(u,X) = X ).
cnf(left_inverse,axiom, n(j(X),X) = u ).
cnf(g,negated_conjecture, n(a,j(a)) != u ).
