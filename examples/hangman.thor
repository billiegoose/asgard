; Hangman over the simulated UART. The fixed word is ASGARD.
;
; Run with:
;   uv run thor-spec --io --model thor --file examples/hangman.thor
;   uv run thor-spec compile-red2 --file examples/hangman.thor --output /tmp/hangman.red2
;   printf 'ASGRD' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io

; --- constants ---
A == 65
S == 83
G == 71
R == 82
D == 68
ESC == 27
NL == 10
SPACE == 32
UNDERSCORE == 95
MAX-MISSES == 6

; --- boolean and state utilities ---
win? == (lambda (known-a known-s known-g known-r known-d)
  (AND known-a (AND known-s (AND known-g (AND known-r known-d)))))

hit? == (lambda (guess)
  (OR (= guess A)
      (OR (= guess S)
          (OR (= guess G)
              (OR (= guess R) (= guess D))))))

known-a-after == (lambda (known-a guess)
  (OR known-a (= guess A)))

known-s-after == (lambda (known-s guess)
  (OR known-s (= guess S)))

known-g-after == (lambda (known-g guess)
  (OR known-g (= guess G)))

known-r-after == (lambda (known-r guess)
  (OR known-r (= guess R)))

known-d-after == (lambda (known-d guess)
  (OR known-d (= guess D)))

misses-after == (lambda (misses guess)
  (if (hit? guess)
      misses
      (+ misses 1)))

; --- UART text utilities ---
emit-2 == (lambda (a b next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      next)))

emit-3 == (lambda (a b c next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        next))))

emit-4 == (lambda (a b c d next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          next)))))

emit-5 == (lambda (a b c d e next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          (IO-THEN (UART-TX e)
            next))))))

emit-6 == (lambda (a b c d e f next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          (IO-THEN (UART-TX e)
            (IO-THEN (UART-TX f)
              next)))))))

emit-7 == (lambda (a b c d e f g next)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          (IO-THEN (UART-TX e)
            (IO-THEN (UART-TX f)
              (IO-THEN (UART-TX g)
                next))))))))

emit-newline == (lambda (next)
  (IO-THEN (UART-TX NL) next))

emit-known == (lambda (known byte next)
  (if known
      (IO-THEN (UART-TX byte) next)
      (IO-THEN (UART-TX UNDERSCORE) next)))

; --- Hangman rendering ---
emit-instructions == (lambda (next)
  (emit-6 71 85 69 83 83 SPACE
    (emit-7 76 69 84 84 69 82 83
      (emit-6 59 SPACE 69 83 67 SPACE
        (emit-5 81 85 73 84 83
          (emit-newline next))))))

emit-hit == (lambda (next)
  (emit-4 72 73 84 NL next))

emit-miss == (lambda (next)
  (emit-5 77 73 83 83 NL next))

emit-feedback == (lambda (guess next)
  (if (hit? guess)
      (emit-hit next)
      (emit-miss next)))

emit-title == (lambda (next)
  (emit-6 72 65 78 71 58 SPACE next))

emit-word == (lambda (known-a known-s known-g known-r known-d next)
  (emit-known known-a A
    (emit-known known-s S
      (emit-known known-g G
        (emit-known known-a A
          (emit-known known-r R
            (emit-known known-d D
              next)))))))

emit-misses == (lambda (misses next)
  (emit-5 SPACE 77 73 83 83
    (emit-3 58 SPACE (+ 48 misses) next)))

render == (lambda (known-a known-s known-g known-r known-d misses next)
  (emit-title
    (emit-word known-a known-s known-g known-r known-d
      (emit-misses misses
        (emit-newline next)))))

emit-win == (lambda (ignored)
  (emit-4 87 73 78 NL (IO-RETURN NIL)))

emit-lose == (lambda (ignored)
  (emit-5 76 79 83 69 NL (IO-RETURN NIL)))

; --- game loop ---
loop == (lambda (known-a known-s known-g known-r known-d misses ignored)
  (if (win? known-a known-s known-g known-r known-d)
      (emit-win NIL)
      (if (>= misses MAX-MISSES)
          (emit-lose NIL)
          (IO-BIND (UART-RX)
            (LAMBDA (guess)
              (if (= guess ESC)
                  (IO-RETURN NIL)
                  (IO-THEN
                    (emit-feedback guess (IO-RETURN NIL))
                    (loop (known-a-after known-a guess)
                          (known-s-after known-s guess)
                          (known-g-after known-g guess)
                          (known-r-after known-r guess)
                          (known-d-after known-d guess)
                          (misses-after misses guess)
                          NIL))))))))

; --- top-level action ---
(IO-THEN
  (emit-instructions (IO-RETURN NIL))
  (IO-THEN
    (render FALSE FALSE FALSE FALSE FALSE 0 (IO-RETURN NIL))
    (loop FALSE FALSE FALSE FALSE FALSE 0 NIL)))
