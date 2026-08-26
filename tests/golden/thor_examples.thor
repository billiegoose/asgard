# One expression per non-comment line.
((LAMBDA (X) X) 42)
(+ 2 3)
(IF TRUE (+ 1 2) (BAD BAD))
(CAR {PAIR (+ 2 3) (BAD BAD)})
(LETREC ((x [1 | y]) (y [2 | x])) x)
