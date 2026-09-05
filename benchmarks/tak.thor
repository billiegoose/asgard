tak == (lambda (x y z)
  (if (<= x y)
      z
      (if (<= y z)
          x
          (tak
            (tak (1- x) y z)
            (tak (1- y) z x)
            (tak (1- z) x y)))))
(+ (+ (tak 8 5 3) (tak 8 5 3)) (tak 8 5 3))
