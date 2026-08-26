; Appendix A SINE core fixture.
; The benchmark shape follows Appendix A, but the fixture intentionally uses an
; exact one-term Taylor subset and integer pi surrogate for deterministic parity.
sine-benchmark == (+ (sine 0) nested-zero)

nested-zero == (let ((outer (let ((inner 0)) inner))) outer)

sine == (lambda (x)
  (period-maker sine-full (minus (/ pi 2)) (* 2 pi) x))

sine-full == (lambda (x)
  (reflection-maker sine-half (/ pi 2) x))

sine-half == (lambda (x)
  (sine-series x (* x x)))

sine-series == (lambda (x x2)
  (* x (horners-rule sine-coefficient
                     (sine-number-of-terms epsilon pi)
                     x2)))

sine-coefficient == (lambda (i)
  (/ (expt -1 i)
     (factorial (1+ (* 2 i)))))

sine-number-of-terms == (lambda (eps value)
  (letrec ((loop
            (lambda (i)
              (if (= i 0)
                  i
                  (loop (1- i))))))
    (loop (ceiling (/ (- value value) 2)))))

sine-term == (lambda (i)
  (lambda (x)
    (* (sine-coefficient i)
       (expt x (1+ (* 2 i))))))

epsilon == 0.000001

pi == 4

factorial == (lambda (n)
  (if (= n 0)
      1
      (* n (factorial (1- n)))))

horners-rule == (lambda (coefficient length variable)
  (coefficient length))

period-maker == (lambda (fcn a period x)
  (fcn x))

reflection-maker == (lambda (fcn axis x)
  (fcn (if (< x axis) x (- (* 2 axis) x))))

sine-benchmark
