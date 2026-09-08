;;; Test file for FULL.S


;;; P(x) <- Q(x), R(x)

(defclause  (x) (P x) (not (Q x)) (not (R x)))

(defclause () (Q 1))
(defclause () (Q 2))

(defclause (x) (R x) (not (S x)) (not (T x)))

(defclause () (S 1))
(defclause () (S 2))

(defclause () (T 2))

(defclause goal (x) (not (P x)))
