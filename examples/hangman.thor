; Hangman over the simulated UART. The fixed word is ASGARD.
;
; Run with:
;   mise run thor examples/hangman.thor --quantum 5000
;   mise run red2 examples/hangman.thor --quantum 5000
;   printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000

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
EMPTY == 0

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

wrong-known? == (lambda (guess w1 w2 w3 w4 w5 w6)
  (OR (= guess w1)
      (OR (= guess w2)
          (OR (= guess w3)
              (OR (= guess w4)
                  (OR (= guess w5) (= guess w6)))))))

wrong1-after == (lambda (w1 guess)
  (if (= w1 EMPTY) guess w1))

wrong2-after == (lambda (w1 w2 guess)
  (if (= w1 EMPTY) w2 (if (= w2 EMPTY) guess w2)))

wrong3-after == (lambda (w1 w2 w3 guess)
  (if (OR (= w1 EMPTY) (= w2 EMPTY)) w3 (if (= w3 EMPTY) guess w3)))

wrong4-after == (lambda (w1 w2 w3 w4 guess)
  (if (OR (= w1 EMPTY) (OR (= w2 EMPTY) (= w3 EMPTY)))
      w4
      (if (= w4 EMPTY) guess w4)))

wrong5-after == (lambda (w1 w2 w3 w4 w5 guess)
  (if (OR (= w1 EMPTY) (OR (= w2 EMPTY) (OR (= w3 EMPTY) (= w4 EMPTY))))
      w5
      (if (= w5 EMPTY) guess w5)))

wrong6-after == (lambda (w1 w2 w3 w4 w5 w6 guess)
  (if (OR (= w1 EMPTY)
          (OR (= w2 EMPTY) (OR (= w3 EMPTY) (OR (= w4 EMPTY) (= w5 EMPTY)))))
      w6
      (if (= w6 EMPTY) guess w6)))

; --- UART text utilities ---
emit-2 == (lambda (a b)
  (IO-THEN (UART-TX a) (UART-TX b)))

emit-3 == (lambda (a b c)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b) (UART-TX c))))

emit-4 == (lambda (a b c d)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c) (UART-TX d)))))

emit-5 == (lambda (a b c d e)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d) (UART-TX e))))))

emit-6 == (lambda (a b c d e f)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          (IO-THEN (UART-TX e) (UART-TX f)))))))

emit-7 == (lambda (a b c d e f g)
  (IO-THEN (UART-TX a)
    (IO-THEN (UART-TX b)
      (IO-THEN (UART-TX c)
        (IO-THEN (UART-TX d)
          (IO-THEN (UART-TX e)
            (IO-THEN (UART-TX f) (UART-TX g))))))))

emit-newline == (UART-TX NL)

emit-known == (lambda (known byte)
  (if known
      (UART-TX byte)
      (UART-TX UNDERSCORE)))

emit-wrong-slot == (lambda (slot)
  (if (= slot EMPTY)
      (IO-RETURN NIL)
      (UART-TX slot)))

; --- Hangman rendering ---
emit-instructions ==
  (IO-THEN (emit-6 71 85 69 83 83 SPACE)
    (IO-THEN (emit-7 76 69 84 84 69 82 83)
      (IO-THEN (emit-6 59 SPACE 69 83 67 SPACE)
        (IO-THEN (emit-5 81 85 73 84 83)
          emit-newline))))

emit-word-label == (emit-6 87 79 82 68 58 SPACE)

emit-guessed-label ==
  (IO-THEN (emit-7 71 85 69 83 83 69 68)
    (UART-TX 58))

emit-guessed == (lambda (w1 w2 w3 w4 w5 w6)
  (IO-THEN emit-guessed-label
    (if (= w1 EMPTY)
        emit-newline
        (IO-THEN (UART-TX SPACE)
          (IO-THEN (emit-wrong-slot w1)
            (IO-THEN (emit-wrong-slot w2)
              (IO-THEN (emit-wrong-slot w3)
                (IO-THEN (emit-wrong-slot w4)
                  (IO-THEN (emit-wrong-slot w5)
                    (IO-THEN (emit-wrong-slot w6) emit-newline))))))))))

emit-word == (lambda (known-a known-s known-g known-r known-d)
  (IO-THEN (emit-known known-a A)
    (IO-THEN (emit-known known-s S)
      (IO-THEN (emit-known known-g G)
        (IO-THEN (emit-known known-a A)
          (IO-THEN (emit-known known-r R)
            (emit-known known-d D)))))))

render == (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6)
  (IO-THEN emit-word-label
    (IO-THEN (emit-word known-a known-s known-g known-r known-d)
      (IO-THEN emit-newline
        (emit-guessed w1 w2 w3 w4 w5 w6)))))

emit-win == (emit-4 87 73 78 NL)

; --- game loop ---
loop-updated ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6)
    (IO-THEN
      (render known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6)
      (loop known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 NIL)))

handle-right ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)
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
                        (loop-updated next-a next-s next-g next-r next-d
                                      w1 w2 w3 w4 w5 w6))))))))))))

handle-new-wrong ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)
    (IO-BIND (IO-RETURN (wrong1-after w1 guess))
      (LAMBDA (next-w1)
        (IO-BIND (IO-RETURN (wrong2-after w1 w2 guess))
          (LAMBDA (next-w2)
            (IO-BIND (IO-RETURN (wrong3-after w1 w2 w3 guess))
              (LAMBDA (next-w3)
                (IO-BIND (IO-RETURN (wrong4-after w1 w2 w3 w4 guess))
                  (LAMBDA (next-w4)
                    (IO-BIND (IO-RETURN (wrong5-after w1 w2 w3 w4 w5 guess))
                      (LAMBDA (next-w5)
                        (IO-BIND (IO-RETURN (wrong6-after w1 w2 w3 w4 w5 w6 guess))
                          (LAMBDA (next-w6)
                            (loop-updated known-a known-s known-g known-r known-d
                                          next-w1 next-w2 next-w3 next-w4
                                          next-w5 next-w6))))))))))))))

handle-wrong ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)
    (if (wrong-known? guess w1 w2 w3 w4 w5 w6)
        (loop-updated known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6)
        (handle-new-wrong known-a known-s known-g known-r known-d
                          w1 w2 w3 w4 w5 w6 guess)))

handle-letter ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)
    (if (hit? guess)
        (handle-right known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)
        (handle-wrong known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 guess)))

handle-guess ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 raw-guess)
    (if (= raw-guess ESC)
        (IO-RETURN NIL)
        (if (line-ending? raw-guess)
            (loop known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 NIL)
            (IO-BIND (IO-RETURN (to-upper raw-guess))
              (LAMBDA (guess)
                (handle-letter known-a known-s known-g known-r known-d
                               w1 w2 w3 w4 w5 w6 guess))))))

loop ==
  (lambda (known-a known-s known-g known-r known-d w1 w2 w3 w4 w5 w6 ignored)
    (if (win? known-a known-s known-g known-r known-d)
        (IO-THEN emit-win (IO-RETURN NIL))
        (IO-BIND (UART-RX)
          (LAMBDA (raw-guess)
            (handle-guess known-a known-s known-g known-r known-d
                          w1 w2 w3 w4 w5 w6 raw-guess)))))

; --- top-level action ---
(IO-THEN emit-instructions
  (IO-THEN
    (render FALSE FALSE FALSE FALSE FALSE EMPTY EMPTY EMPTY EMPTY EMPTY EMPTY)
    (loop FALSE FALSE FALSE FALSE FALSE EMPTY EMPTY EMPTY EMPTY EMPTY EMPTY NIL)))
