(defclause (x) (P x) (not (Q x)) (not (R x)))
(defclause () (Q 1))
(defclause () (Q 2))
(defclause (x) (R x) (not (P x)))
(defclause () (R 1))

(defclause goal (x) (not (P x)))
