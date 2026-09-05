build-list == (lambda (n)
  (if (= n 0)
      NIL
      (CONS n (build-list (1- n)))))
sum-list == (lambda (xs acc)
  (if (NULL? xs)
      acc
      (sum-list (CDR xs) (+ acc (CAR xs)))))
(sum-list (build-list 24) 0)
