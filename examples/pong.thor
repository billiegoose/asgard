; Pong 20x12 over ANSI terminal UART.
; Use up/down arrow keys to move the left paddle. Press q to quit.

; --- constants ---
ESC == 27
LBRACKET == 91
UP == 65
DOWN == 66
QLOW == 113
QUP == 81
SPACE == 32
HASH == 35
BALL == 111
PADDLE == 124
SEMI == 59
CURSOR-H == 72
TICK-MS == 200
CMD-NONE == 0
CMD-UP == -1
CMD-DOWN == 1

; --- terminal rendering ---
emit-hide-cursor == (UART-TX-BYTES [27 91 63 50 53 108])
emit-show-cursor == (UART-TX-BYTES [27 91 63 50 53 104])
emit-clear-home == (UART-TX-BYTES [27 91 50 74 27 91 72])
emit-title == (UART-TX-BYTES [80 79 78 71 32 50 48 120 49 50 10])
emit-help == (UART-TX-BYTES [65 82 82 79 87 83 32 85 80 47 68 79 87 78 59 32 81 32 81 85 73 84 83 10])
emit-board-top == (UART-TX-BYTES [35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 35 10])
emit-empty-row == (UART-TX-BYTES [35 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 32 35 10])
emit-quit == (UART-TX-BYTES [81 85 73 84 10])

emit-digit == (lambda (n) (UART-TX (+ 48 n)))
emit-score == (lambda (left right)
  (IO-THEN (UART-TX-BYTES [76 58])
    (IO-THEN (emit-digit left)
      (IO-THEN (UART-TX-BYTES [32 32 82 58])
        (IO-THEN (emit-digit right) (UART-TX 10))))))

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

emit-paddle-three == (lambda (x y byte)
  (IO-THEN (emit-at x y byte)
    (IO-THEN (emit-at x (+ y 1) byte)
      (emit-at x (+ y 2) byte))))
draw-left-paddle == (lambda (y) (emit-paddle-three 2 y PADDLE))
erase-left-paddle == (lambda (y) (emit-paddle-three 2 y SPACE))
draw-right-paddle == (lambda (y) (emit-paddle-three 17 y PADDLE))

render-empty-rows == (lambda (n)
  (if (= n 0)
      (IO-RETURN NIL)
      (IO-THEN emit-empty-row (render-empty-rows (- n 1)))))

render-initial == (lambda (left-score right-score left-y right-y ball-x ball-y)
  (IO-THEN emit-clear-home
    (IO-THEN emit-title
      (IO-THEN emit-help
        (IO-THEN (emit-score left-score right-score)
          (IO-THEN emit-board-top
            (IO-THEN (render-empty-rows 10)
              (IO-THEN emit-board-top
                (IO-THEN (draw-left-paddle left-y)
                  (IO-THEN (draw-right-paddle right-y)
                    (emit-ball-at ball-x ball-y)))))))))))

; --- input decoding ---
up-paddle == (lambda (y) (if (> y 1) (- y 1) y))
down-paddle == (lambda (y) (if (< y 8) (+ y 1) y))
paddle-after-input == (lambda (y command)
  (if (= command CMD-UP)
      (up-paddle y)
      (if (= command CMD-DOWN) (down-paddle y) y)))

handle-escape ==
  (lambda (left-score right-score left-y right-y ball-x ball-y dx dy last-tick ignored)
    (IO-BIND (UART-RX)
      (LAMBDA (second)
        (IO-BIND (UART-RX)
          (LAMBDA (third)
            (if (= second LBRACKET)
                (if (= third UP)
                    (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-UP)
                    (if (= third DOWN)
                        (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-DOWN)
                        (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-NONE)))
                (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-NONE)))))))

handle-byte ==
  (lambda (left-score right-score left-y right-y ball-x ball-y dx dy last-tick byte)
    (if (= byte NIL)
        (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-NONE)
        (if (OR (= byte QLOW) (= byte QUP))
            (IO-THEN (emit-cursor 17 1)
              (IO-THEN emit-show-cursor
                (IO-THEN emit-quit (IO-RETURN NIL))))
            (if (= byte ESC)
                (handle-escape left-score right-score left-y right-y ball-x ball-y dx dy last-tick NIL)
                (step left-score right-score left-y right-y ball-x ball-y dx dy last-tick CMD-NONE)))))

; --- game physics ---
tick-due? == (lambda (now last-tick) (>= (- now last-tick) TICK-MS))
vertical-dy == (lambda (ball-y dy)
  (if (<= (+ ball-y dy) 1) 1
      (if (>= (+ ball-y dy) 10) -1 dy)))
left-paddle-hit? == (lambda (x y paddle-y)
  (AND (= x 2) (AND (>= y paddle-y) (<= y (+ paddle-y 2)))))
right-paddle-hit? == (lambda (x y paddle-y)
  (AND (= x 17) (AND (>= y paddle-y) (<= y (+ paddle-y 2)))))
horizontal-dx == (lambda (next-x next-y dx left-y right-y)
  (if (<= next-x 1)
      1
      (if (>= next-x 18)
          -1
          (if (AND (< dx 0) (left-paddle-hit? next-x next-y left-y))
              1
              (if (AND (> dx 0) (right-paddle-hit? next-x next-y right-y)) -1 dx)))))
ai-paddle == (lambda (right-y ball-y)
  (if (< ball-y right-y) (up-paddle right-y)
      (if (> ball-y (+ right-y 2)) (down-paddle right-y) right-y)))

redraw-paddles == (lambda (old-left new-left right-y)
  (if (= old-left new-left)
      (IO-RETURN NIL)
      (IO-THEN (erase-left-paddle old-left)
        (IO-THEN (draw-left-paddle new-left) (draw-right-paddle right-y)))))

step-tick ==
  (lambda (left-score right-score left-y right-y ball-x ball-y dx dy last-tick new-left)
    (IO-BIND (IO-RETURN (vertical-dy ball-y dy))
      (LAMBDA (next-dy)
        (IO-BIND (IO-RETURN (+ ball-y next-dy))
          (LAMBDA (next-y)
            (IO-BIND (IO-RETURN (+ ball-x dx))
              (LAMBDA (raw-x)
                (IO-BIND (IO-RETURN (horizontal-dx raw-x next-y dx new-left right-y))
                  (LAMBDA (next-dx)
                    (IO-BIND (IO-RETURN (+ ball-x next-dx))
                      (LAMBDA (next-x)
                        (IO-BIND (IO-RETURN (ai-paddle right-y next-y))
                          (LAMBDA (new-right)
                            (IO-THEN (erase-ball-at ball-x ball-y)
                              (IO-THEN (redraw-paddles left-y new-left new-right)
                                (IO-THEN (emit-ball-at next-x next-y)
                                  (loop left-score right-score new-left new-right next-x next-y next-dx next-dy (+ last-tick TICK-MS))))))))))))))))))

step ==
  (lambda (left-score right-score left-y right-y ball-x ball-y dx dy last-tick command)
    (IO-BIND (CLOCK)
      (LAMBDA (now)
        (IO-BIND (IO-RETURN (paddle-after-input left-y command))
          (LAMBDA (new-left)
            (if (tick-due? now last-tick)
                (step-tick left-score right-score left-y right-y ball-x ball-y dx dy last-tick new-left)
                (IO-THEN (redraw-paddles left-y new-left right-y)
                  (loop left-score right-score new-left right-y ball-x ball-y dx dy last-tick))))))))

; --- game loop ---
loop ==
  (lambda (left-score right-score left-y right-y ball-x ball-y dx dy last-tick)
    (IO-BIND (UART-RX)
      (LAMBDA (byte)
        (handle-byte left-score right-score left-y right-y ball-x ball-y dx dy last-tick byte))))

; --- top-level action ---
(IO-BIND (CLOCK)
  (LAMBDA (start-ms)
    (IO-THEN emit-hide-cursor
      (IO-THEN (render-initial 0 0 4 4 10 6)
        (loop 0 0 4 4 10 6 1 -1 start-ms)))))
