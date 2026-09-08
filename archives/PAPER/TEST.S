
(define c1 (defclause c1 (x y) (not (P x (f y))) (not (Q (f x) (f y)))))
(define c2 (defclause c2 (x y) (P x y) (P y x) (Q x y)))
(define c3 (defclause c3 (x y) (Q x (f x)) (Q x y)))

