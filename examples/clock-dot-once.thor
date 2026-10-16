DOT == 46
SECOND-MS == 1000

wait-dot ==
  (Y
    (LAMBDA (self)
      (LAMBDA (start)
        (IO-BIND (CLOCK)
          (LAMBDA (now)
            (if (>= (- now start) SECOND-MS)
                (UART-TX DOT)
                (self start)))))))

(IO-BIND (CLOCK)
  (LAMBDA (start)
    (wait-dot start)))
