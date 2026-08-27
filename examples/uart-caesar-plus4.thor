; Caesar cipher over the simulated UART. Letters rotate by +4; other bytes pass
; through unchanged. ESC (byte 27) stops the loop. Ctrl-C stops the host process.
;
; Run with:
;   uv run thor-spec --io --model thor --file examples/uart-caesar-plus4.thor

rot-upper == (lambda (byte)
  (+ 65 (MOD (+ (- byte 65) 4) 26)))

rot-lower == (lambda (byte)
  (+ 97 (MOD (+ (- byte 97) 4) 26)))

rot == (lambda (byte)
  (if (AND (>= byte 65) (<= byte 90))
      (rot-upper byte)
      (if (AND (>= byte 97) (<= byte 122))
          (rot-lower byte)
          byte)))

loop == (lambda (ignored)
  (IO-BIND (UART-RX)
    (LAMBDA (byte)
      (if (= byte 27)
          (IO-RETURN NIL)
          (IO-THEN (UART-TX (rot byte))
                   (loop NIL))))))

(loop NIL)
