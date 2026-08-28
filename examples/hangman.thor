; Hangman over the simulated UART. The fixed word is ASGARD.
;
; Run with:
;   uv run thor-spec --io --model thor --file examples/hangman.thor
;   uv run thor-spec compile-red2 --file examples/hangman.thor --output /tmp/hangman.red2
;   printf 'A\nS\nG\nR\nD\n' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io --quantum 3000

; --- constants ---
A == 65
S == 83
G == 71
R == 82
D == 68
ESC == 27
CR == 13
NL == 10
SPACE == 32
UNDERSCORE == 95

; --- list utilities ---
member? == (lambda (needle items)
  (if (NULL? items)
      FALSE
      (if (EQUAL? needle (CAR items))
          TRUE
          (member? needle (CDR items)))))

append-one == (lambda (items item)
  (if (NULL? items)
      (CONS item NIL)
      (CONS (CAR items) (append-one (CDR items) item))))

; --- boolean and state utilities ---
line-ending? == (lambda (guess)
  (OR (= guess NL) (= guess CR)))

to-upper == (lambda (guess)
  (if (AND (>= guess 97) (<= guess 122))
      (- guess 32)
      guess))

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

wrong-after == (lambda (wrongs guess)
  (if (hit? guess)
      wrongs
      (if (member? guess wrongs)
          wrongs
          (append-one wrongs guess))))

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

emit-byte-list == (lambda (items next)
  (if (NULL? items)
      next
      (IO-THEN (UART-TX (CAR items))
        (emit-byte-list (CDR items) next))))

; --- Hangman rendering ---
emit-instructions == (lambda (next)
  (emit-6 71 85 69 83 83 SPACE
    (emit-7 76 69 84 84 69 82 83
      (emit-6 59 SPACE 69 83 67 SPACE
        (emit-5 81 85 73 84 83
          (emit-newline next))))))

emit-word-label == (lambda (next)
  (emit-6 87 79 82 68 58 SPACE next))

emit-guessed-label == (lambda (next)
  (emit-7 71 85 69 83 83 69 68
    (IO-THEN (UART-TX 58) next)))

emit-guessed == (lambda (wrongs next)
  (emit-guessed-label
    (if (NULL? wrongs)
        (emit-newline next)
        (IO-THEN (UART-TX SPACE)
          (emit-byte-list wrongs
            (emit-newline next))))))

emit-word == (lambda (known-a known-s known-g known-r known-d next)
  (emit-known known-a A
    (emit-known known-s S
      (emit-known known-g G
        (emit-known known-a A
          (emit-known known-r R
            (emit-known known-d D
              next)))))))

render == (lambda (known-a known-s known-g known-r known-d wrongs next)
  (emit-word-label
    (emit-word known-a known-s known-g known-r known-d
      (emit-newline
        (emit-guessed wrongs next)))))

emit-win == (lambda (ignored)
  (emit-4 87 73 78 NL (IO-RETURN NIL)))

; --- game loop ---
loop-updated == (lambda (known-a known-s known-g known-r known-d wrongs)
  (IO-THEN
    (render known-a known-s known-g known-r known-d wrongs (IO-RETURN NIL))
    (loop known-a known-s known-g known-r known-d wrongs NIL)))

handle-letter == (lambda (known-a known-s known-g known-r known-d wrongs guess)
  (IO-BIND (IO-RETURN (known-a-after known-a guess))
    (LAMBDA (next-a)
      (IO-BIND (IO-RETURN (known-s-after known-s guess))
        (LAMBDA (next-s)
          (IO-BIND (IO-RETURN (known-g-after known-g guess))
            (LAMBDA (next-g)
              (IO-BIND (IO-RETURN (known-r-after known-r guess))
                (LAMBDA (next-r)
                  (IO-BIND (IO-RETURN (known-d-after known-d guess))
                    (LAMBDA (next-d)
                      (IO-BIND (IO-RETURN (wrong-after wrongs guess))
                        (LAMBDA (next-wrongs)
                          (loop-updated next-a next-s next-g next-r next-d
                                        next-wrongs))))))))))))))

handle-guess == (lambda (known-a known-s known-g known-r known-d wrongs raw-guess)
  (if (= raw-guess ESC)
      (IO-RETURN NIL)
      (if (line-ending? raw-guess)
          (loop known-a known-s known-g known-r known-d wrongs NIL)
          (IO-BIND (IO-RETURN (to-upper raw-guess))
            (LAMBDA (guess)
              (handle-letter known-a known-s known-g known-r known-d wrongs guess))))))

loop == (lambda (known-a known-s known-g known-r known-d wrongs ignored)
  (if (win? known-a known-s known-g known-r known-d)
      (emit-win NIL)
      (IO-BIND (UART-RX)
        (LAMBDA (raw-guess)
          (handle-guess known-a known-s known-g known-r known-d wrongs raw-guess)))))

; --- top-level action ---
(IO-THEN
  (emit-instructions (IO-RETURN NIL))
  (IO-THEN
    (render FALSE FALSE FALSE FALSE FALSE NIL (IO-RETURN NIL))
    (loop FALSE FALSE FALSE FALSE FALSE NIL NIL)))
