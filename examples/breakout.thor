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
SPACE == 32
HASH == 35
BRICK == 61
BALL == 111
PADDLE == 95
SEMI == 59
CURSOR-H == 72
TICK-MS == 100
START-MS == 1700000000000
CMD-NONE == 0
CMD-LEFT == -1
CMD-RIGHT == 1

; --- terminal rendering ---
emit-hide-cursor == (UART-TX-BYTES [27 91 63 50 53 108])
emit-show-cursor == (UART-TX-BYTES [27 91 63 50 53 104])
emit-clear-home == (UART-TX-BYTES [27 91 50 74 27 91 72])
emit-title == (UART-TX-BYTES [66 82 69 65 75 79 85 84 32 50 48 120 49 50 10])
emit-score-label == (UART-TX-BYTES [83 67 79 82 69 58 32])
emit-lives-inline == (UART-TX-BYTES [32 32 76 73 86 69 83 58 32])
emit-help == (UART-TX-BYTES [65 82 82 79 87 83 32 77 79 86 69 59 32 81 32 81 85 73 84 83 10])
emit-board-top == (UART-TX-BYTES [35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 10])
emit-brick-row == (UART-TX-BYTES [35 32 61 61 61 61 61 61 61 61 61 61 61 61 61 61 61 32 32 35 10])
emit-empty-row == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 35 10])
emit-quit == (UART-TX-BYTES [81 85 73 84 10])
emit-win == (UART-TX-BYTES [87 73 78 10])
emit-lose == (UART-TX-BYTES [76 79 83 69 10])
emit-newline == (UART-TX NL)

emit-digit == (lambda (n) (UART-TX (+ 48 n)))

emit-two == (lambda (n)
  (if (>= n 10)
      (IO-THEN (emit-digit 1) (emit-digit (- n 10)))
      (emit-digit n)))

emit-score == (lambda (score)
  (IO-THEN emit-score-label (IO-THEN (emit-two score) emit-newline)))

emit-hud == (lambda (score lives)
  (IO-THEN emit-score-label
    (IO-THEN (emit-two score)
      (IO-THEN emit-lives-inline
        (IO-THEN (emit-digit lives) emit-newline)))))

emit-number == (lambda (n)
  (if (>= n 10)
      (IO-THEN (emit-digit 1) (emit-digit (- n 10)))
      (emit-digit n)))

emit-cursor == (lambda (row col)
  (IO-THEN (UART-TX ESC)
    (IO-THEN (UART-TX LBRACKET)
      (IO-THEN (emit-number row)
        (IO-THEN (UART-TX SEMI)
          (IO-THEN (emit-number col) (UART-TX CURSOR-H)))))))

screen-row == (lambda (y) (+ y 4))
screen-col == (lambda (x) (+ x 1))

emit-at == (lambda (x y byte)
  (IO-THEN (emit-cursor (screen-row y) (screen-col x)) (UART-TX byte)))

emit-ball-at == (lambda (x y) (emit-at x y BALL))
erase-ball-at == (lambda (x y) (emit-at x y SPACE))

draw-brick-cell == (lambda (x y) (emit-at x y BRICK))
erase-brick-cell == (lambda (x y) (emit-at x y SPACE))

draw-brick-run == (lambda (x right y byte)
  (if (> x right)
      (IO-RETURN NIL)
      (IO-THEN (emit-at x y byte) (draw-brick-run (+ x 1) right y byte))))

erase-brick-at == (lambda (x y)
  (if (AND (= y 2) (AND (>= x 2) (<= x 4)))
      (draw-brick-run 2 4 2 SPACE)
      (if (AND (= y 2) (AND (>= x 5) (<= x 7)))
          (draw-brick-run 5 7 2 SPACE)
          (if (AND (= y 2) (AND (>= x 8) (<= x 10)))
              (draw-brick-run 8 10 2 SPACE)
              (if (AND (= y 2) (AND (>= x 11) (<= x 13)))
                  (draw-brick-run 11 13 2 SPACE)
                  (if (AND (= y 2) (AND (>= x 14) (<= x 16)))
                      (draw-brick-run 14 16 2 SPACE)
                      (if (AND (= y 3) (AND (>= x 2) (<= x 4)))
                          (draw-brick-run 2 4 3 SPACE)
                          (if (AND (= y 3) (AND (>= x 5) (<= x 7)))
                              (draw-brick-run 5 7 3 SPACE)
                              (if (AND (= y 3) (AND (>= x 8) (<= x 10)))
                                  (draw-brick-run 8 10 3 SPACE)
                                  (if (AND (= y 3) (AND (>= x 11) (<= x 13)))
                                      (draw-brick-run 11 13 3 SPACE)
                                      (if (AND (= y 3) (AND (>= x 14) (<= x 16)))
                                          (draw-brick-run 14 16 3 SPACE)
                                          (IO-RETURN NIL))))))))))))

paddle-at? == (lambda (x y paddle-x)
  (AND (= y 10) (AND (>= x paddle-x) (< x (+ paddle-x 5)))))

emit-paddle-cell == (lambda (x paddle-x)
  (if (OR (= x 0) (= x 19))
      (UART-TX HASH)
      (if (paddle-at? x 10 paddle-x) (UART-TX PADDLE) (UART-TX SPACE))))

render-paddle-cells == (lambda (x paddle-x)
  (if (> x 19)
      emit-newline
      (IO-THEN (emit-paddle-cell x paddle-x)
        (render-paddle-cells (+ x 1) paddle-x))))

draw-paddle == (lambda (paddle-x)
  (IO-THEN (emit-cursor (screen-row 10) 1)
    (render-paddle-cells 0 paddle-x)))

update-score == (lambda (score)
  (IO-THEN (emit-cursor 3 8) (IO-THEN (emit-two score) (UART-TX SPACE))))

update-lives == (lambda (lives)
  (IO-THEN (emit-cursor 3 18) (emit-digit lives)))

render-initial == (lambda (score lives paddle-x ball-x ball-y)
  (IO-THEN emit-clear-home
    (IO-THEN emit-title
      (IO-THEN emit-help
        (IO-THEN (emit-hud score lives)
          (IO-THEN emit-board-top
            (IO-THEN emit-empty-row
              (IO-THEN emit-brick-row
                (IO-THEN emit-brick-row
                  (IO-THEN emit-empty-row
                    (IO-THEN emit-empty-row
                      (IO-THEN emit-empty-row
                        (IO-THEN emit-empty-row
                          (IO-THEN emit-empty-row
                            (IO-THEN emit-empty-row
                              (IO-THEN emit-empty-row
                                (IO-THEN emit-board-top
                                  (IO-THEN (emit-ball-at ball-x ball-y)
                                    (draw-paddle paddle-x)))))))))))))))))))

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
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 ignored)
    (IO-BIND (UART-RX)
      (LAMBDA (second)
        (IO-BIND (UART-RX)
          (LAMBDA (third)
            (if (= second LBRACKET)
                (if (= third LEFT)
                    (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-LEFT)
                    (if (= third RIGHT)
                        (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-RIGHT)
                        (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-NONE)))
                (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-NONE)))))))

handle-byte ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 byte)
    (if (= byte NIL)
        (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-NONE)
        (if (OR (= byte QLOW) (= byte QUP))
            (IO-THEN (emit-cursor 16 1) (IO-THEN emit-show-cursor (IO-THEN emit-quit (IO-RETURN NIL))))
            (if (= byte ESC)
                (handle-escape score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 NIL)
                (step score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 CMD-NONE)))))

; --- game physics ---
tick-due? == (lambda (now last-tick)
  (>= (- now last-tick) TICK-MS))

brick-1? == (lambda (x y) (AND (= y 2) (AND (>= x 2) (<= x 4))))
brick-2? == (lambda (x y) (AND (= y 2) (AND (>= x 5) (<= x 7))))
brick-3? == (lambda (x y) (AND (= y 2) (AND (>= x 8) (<= x 10))))
brick-4? == (lambda (x y) (AND (= y 2) (AND (>= x 11) (<= x 13))))
brick-5? == (lambda (x y) (AND (= y 2) (AND (>= x 14) (<= x 16))))
brick-6? == (lambda (x y) (AND (= y 3) (AND (>= x 2) (<= x 4))))
brick-7? == (lambda (x y) (AND (= y 3) (AND (>= x 5) (<= x 7))))
brick-8? == (lambda (x y) (AND (= y 3) (AND (>= x 8) (<= x 10))))
brick-9? == (lambda (x y) (AND (= y 3) (AND (>= x 11) (<= x 13))))
brick-10? == (lambda (x y) (AND (= y 3) (AND (>= x 14) (<= x 16))))

brick-at? == (lambda (x y b1 b2 b3 b4 b5 b6 b7 b8 b9 b10)
  (OR (AND b1 (brick-1? x y))
    (OR (AND b2 (brick-2? x y))
      (OR (AND b3 (brick-3? x y))
        (OR (AND b4 (brick-4? x y))
          (OR (AND b5 (brick-5? x y))
            (OR (AND b6 (brick-6? x y))
              (OR (AND b7 (brick-7? x y))
                (OR (AND b8 (brick-8? x y))
                  (OR (AND b9 (brick-9? x y))
                      (AND b10 (brick-10? x y))))))))))))

paddle-hit? == (lambda (x y paddle-x)
  (AND (= y 10) (AND (>= x paddle-x) (< x (+ paddle-x 5)))))

paddle-dx == (lambda (x paddle-x)
  (if (< (- x paddle-x) 2) -1 (if (= (- x paddle-x) 2) 0 1)))

wall-dx == (lambda (ball-x dx)
  (if (<= (+ ball-x dx) 1) 1 (if (>= (+ ball-x dx) 18) -1 dx)))

wall-dy == (lambda (ball-y dy)
  (if (<= (+ ball-y dy) 1) 1 dy))

next-b1 == (lambda (b x y hit) (if (AND hit (brick-1? x y)) FALSE b))
next-b2 == (lambda (b x y hit) (if (AND hit (brick-2? x y)) FALSE b))
next-b3 == (lambda (b x y hit) (if (AND hit (brick-3? x y)) FALSE b))
next-b4 == (lambda (b x y hit) (if (AND hit (brick-4? x y)) FALSE b))
next-b5 == (lambda (b x y hit) (if (AND hit (brick-5? x y)) FALSE b))
next-b6 == (lambda (b x y hit) (if (AND hit (brick-6? x y)) FALSE b))
next-b7 == (lambda (b x y hit) (if (AND hit (brick-7? x y)) FALSE b))
next-b8 == (lambda (b x y hit) (if (AND hit (brick-8? x y)) FALSE b))
next-b9 == (lambda (b x y hit) (if (AND hit (brick-9? x y)) FALSE b))
next-b10 == (lambda (b x y hit) (if (AND hit (brick-10? x y)) FALSE b))
score-after-hit == (lambda (score hit) (if hit (+ score 1) score))
dy-after-hit == (lambda (dy hit) (if hit (MINUS dy) dy))

redraw-after-tick ==
  (lambda (score lives paddle-x old-x old-y new-x new-y next-score hit)
    (IO-THEN (erase-ball-at old-x old-y)
      (IO-THEN (if hit (erase-brick-at new-x new-y) (IO-RETURN NIL))
        (IO-THEN (emit-ball-at new-x new-y)
          (update-score next-score)))))

step-after-move ==
  (lambda (score lives paddle-x old-x old-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 new-x new-y new-dx new-dy hit)
    (IO-BIND (IO-RETURN hit)
      (LAMBDA (real-hit)
        (IO-BIND (IO-RETURN (score-after-hit score real-hit))
          (LAMBDA (next-score)
            (IO-BIND (IO-RETURN (next-b1 b1 new-x new-y real-hit))
              (LAMBDA (nb1)
                (IO-BIND (IO-RETURN (next-b2 b2 new-x new-y real-hit))
                  (LAMBDA (nb2)
                    (IO-BIND (IO-RETURN (next-b3 b3 new-x new-y real-hit))
                      (LAMBDA (nb3)
                        (IO-BIND (IO-RETURN (next-b4 b4 new-x new-y real-hit))
                          (LAMBDA (nb4)
                            (IO-BIND (IO-RETURN (next-b5 b5 new-x new-y real-hit))
                              (LAMBDA (nb5)
                                (IO-BIND (IO-RETURN (next-b6 b6 new-x new-y real-hit))
                                  (LAMBDA (nb6)
                                    (IO-BIND (IO-RETURN (next-b7 b7 new-x new-y real-hit))
                                      (LAMBDA (nb7)
                                        (IO-BIND (IO-RETURN (next-b8 b8 new-x new-y real-hit))
                                          (LAMBDA (nb8)
                                            (IO-BIND (IO-RETURN (next-b9 b9 new-x new-y real-hit))
                                              (LAMBDA (nb9)
                                                (IO-BIND (IO-RETURN (next-b10 b10 new-x new-y real-hit))
                                                  (LAMBDA (nb10)
                                                    (IO-THEN (redraw-after-tick score lives paddle-x old-x old-y new-x new-y next-score real-hit)
                                                      (loop next-score lives paddle-x new-x new-y new-dx (dy-after-hit new-dy real-hit) (+ last-tick TICK-MS) nb1 nb2 nb3 nb4 nb5 nb6 nb7 nb8 nb9 nb10)))))))))))))))))))))))))))

step-tick ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 next-paddle)
    (IO-BIND (IO-RETURN (wall-dx ball-x dx))
      (LAMBDA (dx1)
        (IO-BIND (IO-RETURN (wall-dy ball-y dy))
          (LAMBDA (dy1)
            (IO-BIND (IO-RETURN (+ ball-x dx1))
              (LAMBDA (x1)
                (IO-BIND (IO-RETURN (+ ball-y dy1))
                  (LAMBDA (y1)
                    (if (AND (> y1 10) (NOT (paddle-hit? x1 10 next-paddle)))
                        (IO-THEN (erase-ball-at ball-x ball-y)
                          (IO-THEN (emit-ball-at 10 8)
                            (IO-THEN (update-lives (- lives 1))
                              (loop score (- lives 1) next-paddle 10 8 1 -1 (+ last-tick TICK-MS) b1 b2 b3 b4 b5 b6 b7 b8 b9 b10))))
                        (if (paddle-hit? x1 y1 next-paddle)
                            (step-after-move score lives next-paddle ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 x1 9 (paddle-dx x1 next-paddle) -1 FALSE)
                            (step-after-move score lives next-paddle ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 x1 y1 dx1 dy1
                              (brick-at? x1 y1 b1 b2 b3 b4 b5 b6 b7 b8 b9 b10)))))))))))))

step ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 command)
    (IO-BIND (CLOCK)
      (LAMBDA (now)
        (IO-BIND (IO-RETURN (paddle-after-input paddle-x command))
          (LAMBDA (next-paddle)
            (IO-THEN (if (= next-paddle paddle-x) (IO-RETURN NIL) (draw-paddle next-paddle))
              (if (tick-due? now last-tick)
                  (step-tick score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 next-paddle)
                  (loop score lives next-paddle ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10))))))))

; --- game loop ---
loop ==
  (lambda (score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10)
    (if (>= score 10)
        (IO-THEN (emit-cursor 16 1) (IO-THEN emit-show-cursor (IO-THEN emit-win (IO-RETURN NIL))))
        (if (<= lives 0)
            (IO-THEN (emit-cursor 16 1) (IO-THEN emit-show-cursor (IO-THEN emit-lose (IO-RETURN NIL))))
            (IO-BIND (UART-RX)
              (LAMBDA (byte)
                (handle-byte score lives paddle-x ball-x ball-y dx dy last-tick b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 byte))))))

; --- top-level action ---
(IO-THEN emit-hide-cursor
  (IO-THEN (render-initial 0 3 8 10 8)
    (loop 0 3 8 10 8 1 -1 START-MS TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE)))
