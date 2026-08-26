; Appendix A GAME core fixture.
; The full move generator is replaced by a finite tree so the smoke test can
; focus on Appendix A tree/list/static evaluation parity.
game-benchmark == (evaluate 1)

tree |= label subtrees

empty-board == [E E E E E E E E E]

evaluate == (lambda (depth)
  (maximise (prune depth gametree)))

gametree == (make-tree (static (++ [X] [E]))
                       (cons (make-tree (static (++ [X] [O])) [])
                             []))

maptree == (lambda (f)
  (redtree (lambda (label subtrees)
             (make-tree (f label) subtrees))
           cons
           []))

maximise == (lambda (tree)
  (if (null? (tree-subtrees tree))
      (tree-label tree)
      (maximum (map minimise
                    (tree-subtrees tree)))))

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
      (minimum (map maximise
                    (tree-subtrees tree)))))

minimum == (lambda (list)
  (letrec ((minimum1
            (lambda (list x)
              (if (null? list)
                  x
                  (minimum1 (cdr list)
                            (min x (car list)))))))
    (minimum1 (cdr list) (car list))))

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

static == (lambda (board)
  (static-eval board (whose-turn? board) 0 0))

static-eval == (lambda (board player rating best)
  (if (null? board)
      (max best rating)
      (if (OR (equal? (car board) player)
              (equal? (car board) E))
          (static-eval (cdr board) player (1+ rating) best)
          (static-eval (cdr board) player 0 (max rating best)))))

whose-turn? == (lambda (board)
  (letrec ((ecount
            (lambda (l)
              (if (null? l)
                  0
                  (if (equal? E (car l))
                      (+ 1 (ecount (cdr l)))
                      (ecount (cdr l)))))))
    (if (even? (ecount board)) X O)))

++ == (lambda (a b) (reduce cons b a))

game-benchmark
