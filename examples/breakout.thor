; Breakout 20x12 over ANSI terminal UART.
; ESC [2J clears the terminal and ESC [H homes the cursor.
; Use left/right arrow keys to move. Press q to quit.

; --- constants ---
ESC == 27
LBRACKET == 91
LEFT == 68
RIGHT == 67
QLOW == 113
QUP == 81
NL == 10
COMMA == 44
TICK-MS == 100
WIDTH == 20
HEIGHT == 12
START-MS == 1700000000000
CMD-NONE == 0
CMD-LEFT == -1
CMD-RIGHT == 1

; --- terminal rendering ---
emit-clear-home == (UART-TX-BYTES [27 91 50 74 27 91 72])
emit-title == (UART-TX-BYTES [66 82 69 65 75 79 85 84 32 50 48 120 49 50 10])
emit-score-label == (UART-TX-BYTES [83 67 79 82 69 58 32])
emit-lives == (UART-TX-BYTES [76 73 86 69 83 58 32 51 10])
emit-paddle-label == (UART-TX-BYTES [80 65 68 68 76 69 58 32])
emit-ball-label == (UART-TX-BYTES [66 65 76 76 58 32])
emit-help == (UART-TX-BYTES [65 82 82 79 87 83 32 77 79 86 69 59 32 81 32 81 85 73 84 83 10])
emit-top-wall == (UART-TX-BYTES [35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 10])
emit-bricks-full == (UART-TX-BYTES [35 32 32 61 61 61 61 61 32 61 61 61 61 61 32 32 32 32 32 35 10])
emit-bricks-hit == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 35 10])
emit-empty-row == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 35 10])
emit-ball-row-10 == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 111 32 32 32 32 32 32 32 32 35 10])
emit-ball-row-11 == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 32 111 32 32 32 32 32 32 32 35 10])
emit-paddle-7 == (UART-TX-BYTES [35 32 32 32 32 32 32 95 95 95 95 95 32 32 32 32 32 32 32 35 10])
emit-paddle-8 == (UART-TX-BYTES [35 32 32 32 32 32 32 32 95 95 95 95 95 32 32 32 32 32 32 35 10])
emit-paddle-9 == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 95 95 95 95 95 32 32 32 32 32 35 10])
emit-quit == (UART-TX-BYTES [81 85 73 84 10])
emit-win == (UART-TX-BYTES [87 73 78 10])
emit-lose == (UART-TX-BYTES [76 79 83 69 10])
emit-newline == (UART-TX NL)

emit-digit == (lambda (n)
  (UART-TX (+ 48 n)))

emit-two == (lambda (n)
  (if (>= n 10)
      (IO-THEN (emit-digit 1) (emit-digit (- n 10)))
      (emit-digit n)))

emit-score == (lambda (score)
  (IO-THEN emit-score-label
    (IO-THEN (emit-two score) emit-newline)))

emit-paddle-status == (lambda (paddle-x)
  (IO-THEN emit-paddle-label
    (IO-THEN (emit-two paddle-x) emit-newline)))

emit-ball-status == (lambda (ball-x ball-y)
  (IO-THEN emit-ball-label
    (IO-THEN (emit-two ball-x)
      (IO-THEN (UART-TX COMMA)
        (IO-THEN (emit-two ball-y) emit-newline)))))

emit-brick-row == (lambda (score)
  (if (= score 0) emit-bricks-full emit-bricks-hit))

emit-ball-row-7 == (lambda (ball-x)
  (if (= ball-x 11) emit-ball-row-11 emit-empty-row))

emit-ball-row-8 == (lambda (ball-x)
  (if (= ball-x 10) emit-ball-row-10 emit-empty-row))

emit-board-row-7 == (lambda (ball-x ball-y)
  (if (= ball-y 7) (emit-ball-row-7 ball-x) emit-empty-row))

emit-board-row-8 == (lambda (ball-x ball-y)
  (if (= ball-y 8) (emit-ball-row-8 ball-x) emit-empty-row))

emit-paddle-row == (lambda (paddle-x)
  (if (= paddle-x 7)
      emit-paddle-7
      (if (= paddle-x 9) emit-paddle-9 emit-paddle-8)))

emit-board == (lambda (score paddle-x ball-x ball-y)
  (IO-THEN emit-top-wall
    (IO-THEN (emit-brick-row score)
      (IO-THEN emit-empty-row
        (IO-THEN emit-empty-row
          (IO-THEN emit-empty-row
            (IO-THEN emit-empty-row
              (IO-THEN (emit-board-row-7 ball-x ball-y)
                (IO-THEN (emit-board-row-8 ball-x ball-y)
                  (IO-THEN emit-empty-row
                    (IO-THEN emit-empty-row
                      (IO-THEN (emit-paddle-row paddle-x)
                        emit-top-wall))))))))))))

render == (lambda (score lives paddle-x ball-x ball-y)
  (IO-THEN emit-clear-home
    (IO-THEN emit-title
      (IO-THEN (emit-score score)
        (IO-THEN emit-lives
          (IO-THEN (emit-paddle-status paddle-x)
            (IO-THEN (emit-ball-status ball-x ball-y)
              (IO-THEN emit-help
                (emit-board score paddle-x ball-x ball-y)))))))))

; --- input decoding ---
left-paddle == (lambda (paddle-x)
  (if (> paddle-x 1) (- paddle-x 1) paddle-x))

right-paddle == (lambda (paddle-x)
  (if (< paddle-x 14) (+ paddle-x 1) paddle-x))

paddle-after-input == (lambda (paddle-x command)
  (if (= command CMD-LEFT)
      (left-paddle paddle-x)
      (if (= command CMD-RIGHT) (right-paddle paddle-x) paddle-x)))

handle-escape ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick ignored)
    (IO-BIND (UART-RX)
      (LAMBDA (second)
        (IO-BIND (UART-RX)
          (LAMBDA (third)
            (if (= second LBRACKET)
                (if (= third LEFT)
                    (step score lives paddle-x ball-x ball-y dx dy last-tick CMD-LEFT)
                    (if (= third RIGHT)
                        (step score lives paddle-x ball-x ball-y dx dy last-tick CMD-RIGHT)
                        (step score lives paddle-x ball-x ball-y dx dy last-tick CMD-NONE)))
                (step score lives paddle-x ball-x ball-y dx dy last-tick CMD-NONE)))))))

handle-byte ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick byte)
    (if (OR (= byte QLOW) (= byte QUP))
        (IO-THEN emit-quit (IO-RETURN NIL))
        (if (= byte ESC)
            (handle-escape score lives paddle-x ball-x ball-y dx dy last-tick NIL)
            (step score lives paddle-x ball-x ball-y dx dy last-tick CMD-NONE))))

; --- game physics ---
tick-due? == (lambda (now last-tick)
  (>= (- now last-tick) TICK-MS))

ball-x-after-tick == (lambda (ball-x dx)
  (+ ball-x dx))

ball-y-after-tick == (lambda (ball-y dy)
  (+ ball-y dy))

dx-after-tick == (lambda (ball-x dx)
  (if (>= ball-x 18) -1 (if (<= ball-x 1) 1 dx)))

dy-after-tick == (lambda (ball-y dy)
  (if (<= ball-y 1) 1 (if (>= ball-y 10) -1 dy)))

score-after-tick == (lambda (score ball-x ball-y)
  (if (AND (= score 0) (AND (= ball-x 11) (= ball-y 7)))
      1
      score))

; --- game loop ---
step-tick ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick next-paddle)
    (IO-BIND (IO-RETURN (ball-x-after-tick ball-x dx))
      (LAMBDA (next-ball-x)
        (IO-BIND (IO-RETURN (ball-y-after-tick ball-y dy))
          (LAMBDA (next-ball-y)
            (IO-BIND (IO-RETURN (score-after-tick score next-ball-x next-ball-y))
              (LAMBDA (next-score)
                (IO-THEN (render next-score lives next-paddle next-ball-x next-ball-y)
                  (loop next-score lives next-paddle next-ball-x next-ball-y
                        (dx-after-tick next-ball-x dx)
                        (dy-after-tick next-ball-y dy)
                        (+ last-tick TICK-MS))))))))))

step ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick command)
    (IO-BIND (CLOCK)
      (LAMBDA (now)
        (IO-BIND (IO-RETURN (paddle-after-input paddle-x command))
          (LAMBDA (next-paddle)
            (if (tick-due? now last-tick)
                (step-tick score lives next-paddle ball-x ball-y dx dy last-tick next-paddle)
                (IO-THEN (render score lives next-paddle ball-x ball-y)
                  (loop score lives next-paddle ball-x ball-y dx dy last-tick))))))))

loop ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick)
    (if (>= score 3)
        (IO-THEN emit-win (IO-RETURN NIL))
        (if (<= lives 0)
            (IO-THEN emit-lose (IO-RETURN NIL)
            )
            (IO-BIND (UART-RX)
              (LAMBDA (byte)
                (handle-byte score lives paddle-x ball-x ball-y dx dy last-tick byte))))))

; --- top-level action ---
(IO-THEN (render 0 3 8 10 8)
  (loop 0 3 8 10 8 1 -1 START-MS))
