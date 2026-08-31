DOT == 46
SECOND-MS == 1000

loop ==
  (Y
    (LAMBDA (self)
      (LAMBDA (last)
        (IO-BIND (CLOCK)
          (LAMBDA (now)
            (if (>= (- now last) SECOND-MS)
                (IO-THEN
                  (UART-TX DOT)
                  (self now))
                (self last)))))))

(IO-BIND (CLOCK)
  (LAMBDA (start)
    (loop start)))
