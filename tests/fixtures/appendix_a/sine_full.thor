; Appendix A SINE full fixture.
; Transcribed from the dissertation benchmark with the missing sine-term helper
; made explicit for finite Taylor term selection.
sine-benchmark == (sine pi)

sine == (lambda (x)
  (period-maker sine-full (minus (/ pi 2)) (* 2 pi) x))

sine-full == (lambda (x)
  (reflection-maker sine-half (/ pi 2) x))

sine-half == (lambda (x)
  (let ((x2 (* x x)))
    (sine-series x x2)))

sine-series == (lambda (x x2)
  (if (= x 0.0)
      0.0
      (* x (horners-rule sine-coefficient
                      (sine-number-of-terms epsilon pi)
                      x2))))

sine-coefficient == (lambda (i)
  (/ (expt -1.0 i)
     (factorial (1+ (* 2 i)))))

sine-number-of-terms == (lambda (eps value)
  (letrec ((loop
            (lambda (i)
              (if (< (abs ((sine-term i) value))
                     (abs eps))
                  (1- i)
                  (loop (1+ i))))))
    (loop (ceiling (/ (- value 1) 2)))))

sine-term == (lambda (i)
  (lambda (x)
    (* (sine-coefficient i)
       (expt x (1+ (* 2 i))))))

epsilon == 0.000001

pi == 3.1415927

factorial == (lambda (n)
  (if (= n 0)
      1
      (* n (factorial (1- n)))))

horners-rule == (lambda (coefficient length variable)
  (letrec ((term
            (lambda (n)
              (if (= n length)
                  (coefficient n)
                  (+ (coefficient n)
                     (* variable (term (1+ n))))))))
    (term 0)))

period-maker == (lambda (fcn a period x)
  (let ((cycles (floor (/ (- x a) period))))
    (fcn (- x (* cycles period)))))

reflection-maker == (lambda (fcn axis x)
  (fcn (if (< x axis) x (- (* 2 axis) x))))

sine-benchmark
