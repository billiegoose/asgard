; Tail-recursive Fibonacci, also exercised by the Basys 3 live runner.
fib == (lambda (n)
  (letrec ((fib-iter
            (lambda (i current next)
              (if (= i 0)
                  current
                  (fib-iter (1- i) next (+ current next))))))
    (fib-iter n 0 1)))

fib-six == (fib 6)

fib-six
