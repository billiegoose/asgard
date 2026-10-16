; Integer Fibonacci with at most one pending accumulator addition.
; INTEGER? is strict: it evaluates next and shares the resulting integer.
fib == (lambda (n)
  (letrec ((fib-iter
            (lambda (i current next)
              (if (= i 0)
                  current
                  (if (INTEGER? next)
                      (fib-iter (1- i) next (+ current next))
                      0)))))
    (fib-iter n 0 1)))

fib-six == (fib 6)

fib-six
