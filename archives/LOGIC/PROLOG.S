;;; Small Prolog interpreter described in the article "The world's shortest
;;; Prolog interpreter?" by M. Nilsson

;;; Mike Hilton, 30 March 1989

(define *toplevel* nil)
(define *database* nil)


(define (lvl x) (car x))
(define (xpr x) (cadr x))
(define (molec x y) (list x y))
(define (bind x y e) (cons (cons x y) e))
(define (bond x e) (cdr (or (assoc x e) '(nil))))
(define (but-first-goal x) (cons (cdar x) (cdr x)))


(define (prove goals)
  (seek (list goals) '(0) '((bottom-of-env)) 1))

(define (seek to-prove nlist env n)
  (cond ((null? to-prove) (*toplevel* env))
        ((null? (car to-prove)) (seek (cdr to-prove) (cdr nlist) env n))
        (else
          (let ((goalmolec (molec (car nlist) (caar to-prove)))
                (rest (but-first-goal to-prove))
                (env2 nil)
                (tmp nil))
            (let loop ((clauses *database*))
              (if (null? clauses)
                  nil
                  (let ((head (caar clauses))
                        (tail (cdar clauses)))
                    (if (set! env2 (unify goalmolec (molec n head) env))
                        (if (set! tmp (seek (cons tail rest) (cons n nlist) 
                                            env2 (1+ n)))
                            (and (null? (equal? tmp n)) tmp)
                            (loop (cdr clauses)))
                        (loop (cdr clauses))))))))))

(define (unify x y env)
  (cond ((equal? (set! x (lookup x env)) (set! y (lookup y env))) env)
        ((var (xpr x)) (bind x y env))
        ((var (xpr y)) (bind y x env))
        ((or (atom? (xpr x)) (atom? (xpr y)))
         (and (equal? (xpr x) (xpr y)) env))
        ((set! env (unify (molec (lvl x) (car (xpr x)))
                          (molec (lvl y) (car (xpr y)))
                          env))
         (unify (molec (lvl x) (cdr (xpr x)))
                (molec (lvl y) (cdr (xpr y)))
                env))))

(define (lookup p env)
  (if (and p (var (xpr p)) (bond p env))
      (lookup (bond p env) env)
      p))

(define (var x) (not (not (member x '(?a ?b ?c ?x ?y ?z ?u ?v ?w)))))


(set! *database*
      '(((father medium-ben small-ben))
        ((father big-ben medium-ben))
        ((grandfather ?x ?y) (father ?x ?z) (father ?z ?y))))
(set! *toplevel* (lambda (x) x))


                            