;;; Full First Order Predicate Logic Interpreter,
;;; based on the article "An interpreting algorithm for Prolog Programs,"
;;; by M. H. van Emden
;;; Mike Hilton, 6 April 1989

(set! pcs-debug-mode #f)
(load "format.s")
(set! pcs-debug-mode #t)
(define debug #T)


;;;; DATA STRUCTURE DECLARATIONS

(define-structure clause bindings literals var-names label)
(define-printer
  clause
  (let ((lits (mapcar object->string (clause-literals clause))))
    (apply string-append 
           (cons "{" (reverse! (cons "}" (reverse! lits)))))))

(define-structure literal sign body clause)
(define-printer
  literal
  (if (eq? (literal-sign literal) 'NEGATIVE)
      (string-append " -" (object->string (literal-body literal)))
      (string-append " " (object->string (literal-body literal)))))

(define-structure logic-var val id)
(define-printer logic-var
                (string-append "<logic-var "
                               (symbol->string (logic-var-id logic-var)) ": "
                               (object->string (logic-var-val logic-var)) ">"))

(define-structure var index name)
(define-printer var
                (string-append "<var " (symbol->string (var-name var))
                               ":" (integer->string (var-index var) 10) ">"))

(define-structure frame
                  id
                  call
                  father
                  continue
                  proc
                  env
                  reset
                  next-clause
                  skip)
(define-printer 
  frame
  (format 
    #F 
    "~%#<frame ~A:~%  call = ~A~%  proc = ~A~%  env = ~A~%  reset = ~A~%  next-clause = ~A~%  skip = ~A~%  father = ~A~%  continue = ~A"
    (frame-id frame) (frame-call frame) (frame-proc frame) (frame-env frame)
    (frame-reset frame) (frame-next-clause frame) (frame-skip frame)
    (and (frame-father frame) (frame-id (frame-father frame)))
    (frame-continue frame)))



;;;; GLOBAL VARIABLES

(define predicates nil) ; list of all predicates entered into the database


(define answer nil)
(define curr-call nil)
(define curr-env nil)
(define curr-frame nil)
(define curr-proc nil)
(define curr-skip nil)
(define new-env nil)
(define new-frame nil)
(define res-list nil)

;;; STACK IMPLEMENTATION

(define *stack* nil)
(define (push frame) (set! *stack* (cons frame *stack*)))
(define (pop-stack) (set! *stack* (cdr *stack*)))
(define (stack-top) (car *stack*))
(define (print-stack)
  (format #t "~%stack = ")
  (for-each (lambda (x) (format #t "~A " (frame-id x))) *stack*))

(define (print-env env)
  (do ((index 0 (1+ index))
       (vars env (cdr vars))
       (var (make-var 'index 0) (set! (var-index var) index)))
      ((null? vars) (writeln))
      (let ((value (lookup var env)))
        (format #T "~%  var ~A: ~A"  index value))))



;;;; CLAUSE DEFINITION FUNCTIONS

;;; CLEAR
;;; Clear the database of all clauses entered so far.

(define (clear)
  (mapc (lambda (x)
          (putprop x nil 'POSITIVE-LITS)
          (putprop x nil 'NEGATIVE-LITS))
        predicates)
  (set! predicates nil))


;;; DEFCLAUSE
;;; The form used to create a clause.  The syntax is
;;;   (defclause {label} <list of variable names> <literal>*)
;;; If the clause has the label "goal", it is considered a goal statement
;;; and is not entered into the database.  If it does have a label, the clause
;;; created will be bound to that label.
;;; Examples:
;;; (defclause c1 (x y) (P x y))
;;; (defclause (x y) (not (P y (f x y))) (not (P (f x y) (f x y))) (Q x y))

(macro defclause 
  (lambda (e)
    (let* ((label (if (symbol? (cadr e)) (begin0 (cadr e) (set! e (cdr e)))))
           (bindings (cadr e))
           (body (cddr e)))
      (if (eq? label 'goal)
          `(define ,label
             (make-clause 'label ',label
                          'bindings ,(length bindings)
                          'var-names ',bindings
                          'literals (parse-clause ',bindings ',body)))
          `(let ((clause 
                   (make-clause 'bindings ,(length bindings)
                                'var-names ',bindings
                                'label ',label
                                'literals (parse-clause ',bindings ',body))))
             (for-each (lambda (x) 
                         (set! (literal-clause x) clause)
                         (insert-literal x))
                       (clause-literals clause))
             clause)))))
             


;;; INSERT-LITERAL
;;; Installs a literal into its proper place in the literal-list of
;;; the predicate.  Installs them in the order that they were declared.

(define (insert-literal lit)
  (let ((pred (car (literal-body lit))))
    (if (not (member pred predicates)) 
        (set! predicates (cons pred predicates)))
    (if (eq? (literal-sign lit) 'POSITIVE)
        (putprop pred 
                 (reverse (cons lit (reverse (getprop pred 'POSITIVE-LITS))))
                 'POSITIVE-LITS)
        (putprop pred 
                 (reverse (cons lit (reverse (getprop pred 'NEGATIVE-LITS))))
                 'NEGATIVE-LITS))))



;;; PARSE-CLAUSE
;;; Parses a clause definition and creates a clause structure.  


(define (parse-clause bindings literals)
  (define (index var) 
    (if (member var bindings)
        (make-var 'name var
                  'index (- (length bindings) (length (member var bindings))))
        var))
  (define (parse-lit-body lit)
    (cond ((atom? lit) (index lit))
          (else (mapcar parse-lit-body lit))))
  (define (parse-literal lit)
    (let* ((sign (if (eq? (car lit) 'not) 
                     (begin0 'NEGATIVE (set! lit (cadr lit)))
                     'POSITIVE)))
      (make-literal 'sign sign
                    'body (mapcar parse-lit-body lit))))
  (mapcar parse-literal literals))






;;;; UNIFICATION FUNCTIONS


;;; LOOKUP
;;; Dereferences a variable X in ENVironment.
 
(define (lookup x env)
  (define (deref ptr)
     (cond ((and (logic-var? ptr) (not (eq? (logic-var-val ptr) '*unbound*)))
            (deref (logic-var-val ptr)))
           (else ptr)))
  (if (var? x)
      (deref (list-ref env (var-index x)))
      x))


;;; MAKE-ENV
;;; Creates an environment of size N.

(define (make-env n) 
  (cond ((zero? n) nil)
        (else (cons (make-logic-var 'val '*unbound*
                                    'id (gensym))
                    (make-env (-1+ n))))))

;;; INSTANTIATE
;;; Instantiate a TERM with respect to ENVironment,

(define (instantiate term env)
  (cond ((null? term) nil)
        ((var? term) 
         (let ((newterm (lookup term env)))
           (if (or (null? env) (logic-var? newterm)) term newterm)))
        ((pair? term) (cons (instantiate (car term) env)
                            (instantiate (cdr term) env)))
        ((literal? term)
         (make-literal 'sign (literal-sign term)
                       'body (instantiate (literal-body term) env)))
        ((atom? term) term)
        (else
          (error "Unknown term in INSTANTIATE: " term))))
  

;;; UNIFY
;;; Tries to unify the first literal in the choices slot of the CHILD frame
;;; with the first literal in the goals slot of the PARENT frame.
;;; Returns #T if the unification is successful, #F otherwise.
;;; Any parent variables that are modified are added to the reset list of
;;; the child.

(define (unify call call-env try)
  (when debug
        (format #t "~%Unifying ~A with ~A" (instantiate call call-env) try))
  (let ((enva call-env)
        (envb (make-env (clause-bindings (literal-clause try))))
        (bindings nil))
    (define (unif a b)
;      (when debug (format #t "~%unif ~a  and  ~a" a b))
      (let ((a (lookup a enva))
            (b (lookup b envb)))
;        (when debug (format #t " => ~a  and  ~a" a b))
        (cond ((eq? a b) #T)
              ((logic-var? a) 
               (set! (logic-var-val a) b)
               (set! bindings (cons a bindings)))
              ((logic-var? b) 
               (set! (logic-var-val b) a)
               (set! bindings (cons b bindings)))
              ((and (pair? a) (pair? b))
               (and (unif (car a) (car b))
                    (unif (cdr a) (cdr b)))))))
    (let ((a call)
          (b try))
      (if (= (length (literal-body a)) (length (literal-body b)))
          (if (unif (literal-body a) (literal-body b))
              (begin0
                #T
                (when debug (format #T "  Success!"))
                (set! new-env envb)
                (set! res-list bindings))
              (begin0
                #F
                (when debug (format #t " Failure..."))
                (undo-bindings bindings)))
          #F))))




;;;; THEOREM PROVER

;;; CREATE-ENV
;;; creates a binding environment for CLAUSE

(define (create-env clause) (make-env (clause-bindings clause)))


;;; FIND-POSSIBLE-LITERALS
;;; Returns a list of the possible resolvents for LIT.

(define (find-possible-literals lit)
  (if (eq? (literal-sign lit) 'POSITIVE)
      (getprop (car (literal-body lit)) 'NEGATIVE-LITS)
      (getprop (car (literal-body lit)) 'POSITIVE-LITS)))
  


;;; PROVE
;;; Search mechanism of the theorem prover. GOAL is a clause to be proved
;;; using the clauses currently in the database.

(define (prove goal)
  (set! *stack* nil)
  (set! curr-call nil)
  (set! curr-proc (cons 'GOAL (clause-literals goal)))
  (set! curr-env (create-env goal))
  (set! curr-frame (make-frame 'id (gensym) 'env curr-env 'skip 'GOAL
                               'proc curr-proc))
  (set! answer curr-frame)
  (push curr-frame)
  (if
    (call/cc
      (lambda (exit)
        (let loop-A ()
          (when debug
                (format #T "~%~%LOOP, depth = ~A"  (length *stack*))
                (print-stack)
                (format #t "~%curr-frame = ~A" curr-frame)
                (format #t "~%curr-call = ~A~%curr-proc = ~A"
                        (instantiate curr-call curr-env)
                        (instantiate curr-proc curr-env)))
          (when (select exit)
                (set! (frame-next-clause curr-frame)
                      (find-possible-literals curr-call))
                (let loop-B ()
                  (if (son)
                      (begin
                        (set! curr-frame new-frame)
                        (push curr-frame)
                        (set! curr-env (frame-env new-frame))
                        (loop-A))
                      (begin
                        (when debug (format #T "~%Backtracking..."))
                        (if (= 1 (length *stack*))
                            (exit #F)
                            (let ((top-frame (stack-top)))
                              (undo-bindings (frame-reset top-frame))
                              (set! curr-frame (frame-father top-frame))
                              (set! curr-env (frame-env curr-frame))
                              (set! curr-call (frame-call top-frame))
                              (set! curr-proc (frame-proc curr-frame))
                              (set! (frame-next-clause curr-frame)
                                    (frame-next-clause top-frame))
                              (pop-stack)
                              (loop-B))))))))))
    (begin (format #T "~%~%Success! The environment is:~%")
           (print-env (frame-env answer)))
    (format #T "~%~%Failure; no proof found~%"))
  #T)



;;; NEXT-CLAUSE
;;; Returns the next possible choice for unification.

(define (next-clause frame)
  (let ((choice (car (frame-next-clause frame))))
    (set! (frame-next-clause frame) (cdr (frame-next-clause frame)))
    choice))

;;; ANY-LOOPING-CLAUSES?
;;; Checks a procedure body for looping clauses.

(define (any-looping-clauses? proc env frame)
  (cond ((null? proc) #F)
        (else
          (let ((lit (instantiate (car proc) env)))
            (set! (literal-clause lit) (literal-clause (car proc)))
            (cond ((clause-loop? lit frame) 
                   (when debug 
                         (format #T "~%LOOPING CLAUSE AVOIDED: ~a" 
                                 (literal-clause (car proc))))
                   #T)
                  ((any-looping-clauses? (cdr proc) env frame)))))))


;;; CLAUSE-LOOP?
;;; Detects if choosing the clause containing LITERAL will cause
;;; an infinite loop in the proof search.

(define (clause-loop? literal frame)
  (define (loop frame)
    (cond ((null? frame) #F)
          ((and (frame-call frame)
                (eq? (literal-sign literal) (literal-sign (frame-call frame)))
                (unify (frame-call frame) (frame-env frame) literal))
           (undo-bindings res-list)
           #T)
          (else
            (loop (frame-father frame)))))
  (let ((dbg debug))
    (set! debug #F)
    (let ((answer (loop frame)))
      (set! debug dbg)
      answer)))


;;; SON
;;; Search for a clause with a literal that matches the current node.
;;; If such a clause is found, the search expands down one level.

(define (son)
  (when debug  (format #T "~%SON: Attempting to prove ~A" 
                       (instantiate curr-call curr-env)))
  (let ((next (next-clause curr-frame)))
    (cond ((null? next)
           (when debug (format #T ",  attempt failed"))
           #F)
          (else
            (set! curr-proc next)
            (cond ((unify curr-call curr-env curr-proc)
                   (let ((skippy curr-proc)
                         (reset-list res-list)
                         (environment new-env))
                     (set! curr-proc 
                           (clause-literals (literal-clause curr-proc)))
                     (if (any-looping-clauses? curr-proc new-env curr-frame)
                         (begin (undo-bindings res-list)
                                (son))
                         (begin
                           (when debug 
                                 (format #T "~%Subgoal: prove clause ~A"
                                         (clause-label 
                                           (literal-clause (car curr-proc)))))
                                                                         
                           (set! new-frame
                                 (make-frame 'id (gensym)
                                             'call curr-call
                                             'proc curr-proc
                                             'skip skippy
                                             'father curr-frame
                                             'env environment
                                             'reset reset-list
                                             'next-clause (frame-next-clause 
                                                            curr-frame)))
                           #T))))
                  (else (son)))))))

;;; FIRST-CALL
;;; Retrieves the first goal to prove from clause.

(define (first-call clause-body)
  (if (eq? (car clause-body) (frame-skip curr-frame))
      (begin
        (when debug (format #t "~%  Skipping goal ~A" (car clause-body)))
        (cadr clause-body))
      (car clause-body)))

;;; NEXT-CALL
;;; Retrieves the next goal to be solved from a clause.

(define (next-call frame)
  (let ((goals (cdr (member (frame-call (stack-top)) (frame-proc frame)))))
    (if (eq? (car goals) (frame-skip curr-frame))
        (begin
          (when debug (format #T "~%Skipping goal ~A" (car goals)))
          (cadr goals))
        (car goals))))
          
;;; SELECT
;;; Selects the next goal to prove.

(define (select exit)
  (when debug (format #T "~%SELECTing next goal"))
  (set! curr-call (first-call curr-proc))
  (let loop ()
    (when (null? curr-call)
          (when debug (format #T "~%Subgoal completed, moving up to parent"))
          (set! curr-frame (frame-father curr-frame))
          (if (null? curr-frame)
              (exit #T)
              (begin
                (set! curr-call (next-call curr-frame))
                (loop)))))
  (set! curr-proc (cdr (frame-proc curr-frame)))
  (set! curr-env (frame-env curr-frame))
  (when debug (format #T " -> ~A" (instantiate curr-call curr-env)))
  #T)



;;; UNDO-BINDINGS

(define (undo-bindings binds)
  (for-each (lambda (x) (set! (logic-var-val x) '*unbound*)) binds))

 
