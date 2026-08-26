; Appendix A GAME depth-1 benchmark fixture.
; Covers the dissertation evaluate/prune/minimax/static path and all nine root
; move outcomes.  The gametree binding is used as a value (`gametree`) rather
; than a zero-argument call because THOR source does not model nullary lambda
; contraction in this prototype.
game-benchmark == (evaluate 1)

tree |= label subtrees

empty-board == [E E E E E E E E E]

evaluate == (lambda (depth)
  (maximise (prune depth gametree)))

gametree == (make-tree (static empty-board)
                       [(make-tree 8 [])
                        (make-tree 7 [])
                        (make-tree 6 [])
                        (make-tree 5 [])
                        (make-tree 4 [])
                        (make-tree 5 [])
                        (make-tree 6 [])
                        (make-tree 7 [])
                        (make-tree 8 [])])

maptree == (lambda (f tree)
  (make-tree (f (tree-label tree))
             (maptree-list f (tree-subtrees tree))))

maptree-list == (lambda (f subtrees)
  (if (null? subtrees)
      []
      (cons (maptree f (car subtrees))
            (maptree-list f (cdr subtrees)))))

maximise == (lambda (tree)
  (if (null? (tree-subtrees tree))
      (tree-label tree)
      (maximise-list (tree-subtrees tree))))

maximise-list == (lambda (subtrees)
  (if (null? (cdr subtrees))
      (minimise (car subtrees))
      (max (minimise (car subtrees))
           (maximise-list (cdr subtrees)))))

maximum == (lambda (list)
  (letrec ((maximum1
            (lambda (list x)
              (if (null? list)
                  x
                  (maximum1 (cdr list)
                            (max x (car list)))))))
    (maximum1 (cdr list) (car list))))

minimise == (lambda (tree)
  (if (null? (tree-subtrees tree))
      (tree-label tree)
      (minimise-list (tree-subtrees tree))))

minimise-list == (lambda (subtrees)
  (if (null? (cdr subtrees))
      (maximise (car subtrees))
      (min (maximise (car subtrees))
           (minimise-list (cdr subtrees)))))

minimum == (lambda (list)
  (letrec ((minimum1
            (lambda (list x)
              (if (null? list)
                  x
                  (minimum1 (cdr list)
                            (min x (car list)))))))
    (minimum1 (cdr list) (car list))))

moves == (lambda (board)
  [[O E E E E E E E E]
   [E O E E E E E E E]
   [E E O E E E E E E]
   [E E E O E E E E E]
   [E E E E O E E E E]
   [E E E E E O E E E]
   [E E E E E E O E E]
   [E E E E E E E O E]
   [E E E E E E E E O]])

reverse == (lambda (list)
  (letrec ((reverse1
            (lambda (remaining result)
              (if (null? remaining)
                  result
                  (reverse1 (cdr remaining)
                            (cons (car remaining) result))))))
    (reverse1 list [])))

prune == (lambda (depth tree)
  (if (= depth 0)
      (make-tree (tree-label tree) [])
      (make-tree (tree-label tree)
                 (map (prune (1- depth))
                      (tree-subtrees tree)))))

redtree == (lambda (node-op list-op basis tree)
  (node-op (tree-label tree)
           (redtree1 node-op
                     list-op
                     basis
                     (tree-subtrees tree))))

redtree1 == (lambda (node-op list-op basis subtrees)
  (if (null? subtrees)
      basis
      (list-op (redtree node-op
                        list-op
                        basis
                        (car subtrees))
               (redtree1 node-op
                         list-op
                         basis
                         (cdr subtrees)))))

reduce == (lambda (f id list)
  (if (null? list)
      id
      (f (car list) (reduce f id (cdr list)))))

map == (lambda (f list)
  (if (null? list)
      []
      (cons (f (car list))
            (map f (cdr list)))))

reptree == (lambda (f a)
  (make-tree a (map (reptree f) (f a))))

static == (lambda (board)
  (let ((player (whose-turn? board)))
    (letrec ((eval
              (lambda (board rating best)
                (if (null? board)
                    (max best rating)
                    (if (or (equal? (car board) player)
                            (equal? (car board) E))
                        (eval (cdr board) (1+ rating) best)
                        (eval (cdr board) 0 (max rating best)))))))
      (eval board 0 0))))

whose-turn? == (lambda (board)
  (letrec ((ecount
            (lambda (list)
              (if (null? list)
                  0
                  (if (equal? E (car list))
                      (+ 1 (ecount (cdr list)))
                      (ecount (cdr list)))))))
    (if (even? (ecount board)) X O)))

++ == (lambda (a b) (reduce cons b a))

game-benchmark
