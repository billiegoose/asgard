; Print ASCII digits and letters over the simulated UART, then stop.
;
; Run with:
;   uv run thor-spec --io --model thor --file examples/uart-alphanumerics.thor

emit-range == (lambda (from to next)
  (if (<= from to)
      (IO-THEN (UART-TX from)
               (emit-range (1+ from) to next))
      next))

(IO-THEN
  (emit-range 48 57
    (emit-range 65 90
      (emit-range 97 122
        (UART-TX 10))))
  (IO-RETURN NIL))
