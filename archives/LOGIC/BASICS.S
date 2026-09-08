;;; Logic Programming Data Structures and Common Functions
;;; Mike Hilton, 23 March 1989



(define-structure clause label bindings literals)
(define-structure literal sign body)
(define-structure logic-var val)


(define (empty-clause? x) (null? (clause-literals x)))

(define (first-literal x) (car (clause-literals x)))

(define (negative-clause? x)
  (eq? 'NEGATIVE (literal-sign (car (clause-literals x)))))

(define (positive-clause? x) (not (negative-clause? x)))




;;; DEFCLAUSE
;;; The form used to create a clause.  The syntax is
;;;   (defclause label <list of variable names> <literal>*)
;;; Label is a tag assigned to the clause which may be useful for 
;;; identification purposes.
;;; Examples:
;;; (defclause c1 (x y) (P x y))
;;; (defclause c2 (x y) (not (P y (f x y))) (not (P (f x y) (f x y))) (Q x y))

(macro defclause 
  (lambda (e)
    (let* ((label (if (pair? (cadr e)) 
                      nil 
                      (begin0 (cadr e) (set! e (cdr e)))))
           (bindings (cadr e))
           (body (cddr e)))
      `(make-clause 'label ',label
                    'bindings ,(length bindings)
                    'literals (parse-clause ',bindings ',body)))))
             


;;; EQUAL-CLAUSES?
;;; Predicate two test if two clauses are identical.

(define (equal-clauses? a b)
  (define (equal-bodies? x y)
    (cond ((null? x) #T)
          ((and (eq? (literal-sign (car x)) (literal-sign (car y)))
                (equal? (literal-body (car x)) (literal-body (car y))))
           (equal-bodies? (cdr x) (cdr y)))
          (else #F)))
  (and (= (clause-bindings a) (clause-bindings b))
       (and (= (length (clause-literals a)) (length (clause-literals b)))
            (equal-bodies? (clause-literals a) (clause-literals b)))))



;;; LITERAL<?
;;; A predicate used to compare literals and provide a collating sequence.
;;; The rules used in comparing are:
;;;   negative literals < positive literals
;;;   atoms < functions < variables
;;;   atoms are sorted alphabetically
;;;   variables are sorted by index
;;; Returns #T if less than, 'EQUAL if equal to, or #F if greater than.

(define (literal<? a b)
  (define (symbol<? x y) (string<? (symbol->string x) (symbol->string y)))
  (define (lit<? x y)
    (cond ((and (null? x) (null? y)) 'EQUAL)
          ((or (null? x) (null? y)) (null? x))
          ((and (integer? (car x)) (integer? (car y)))
           (cond ((< (car x) (car y)) #T)
                 ((= (car x) (car y))
                  (lit<? (cdr x) (cdr y)))
                 (else #F)))
          ((and (symbol? (car x)) (symbol? (car y)))
           (if (eq? (car x) (car y))
               (lit<? (cdr x) (cdr y))
               (symbol<? (car x) (car y))))
          ((and (pair? (car x)) (pair? (car y)))
           (if (lit<? (car x) (car y))
               (lit<? (cdr x) (cdr y))
               #F))
          ((and (symbol? (car x)) (pair? (car y))) #T)
          ((and (symbol? (car y)) (pair? (car x))) #F)
          ((and (pair? (car x)) (integer? (car y))) #T)
          ((and (pair? (car y)) (integer? (car x))) #F)
          (else
            (symbol? (car x)))))
  (cond ((not (eq? (literal-sign a) (literal-sign b)))
         (eq? (literal-sign a) 'NEGATIVE))
        (else
          (lit<? (literal-body a) (literal-body b)))))




;;; MEMBER?  
;;; Checks to see if CLAUSE is a member of LIST.

(define (member? clause list)
  (let loop ((pos list))
    (cond ((null? pos) #F)
          ((equal-clauses? clause (car pos)) #T)
          (else (loop (cdr pos))))))



;;; PARSE-CLAUSE
;;; Parses a clause definition and creates a clause structure.  The list 
;;; of literals is sorted according to the predicate LITERAL<?.

(define (parse-clause bindings literals)
  (define (index var) 
    (if (member var bindings)
        (- (length bindings) (length (member var bindings)))
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
  (sort! (mapcar parse-literal literals) literal<?))






;;;; UNIFICATION FUNCTIONS

;;; UNIFY
;;; Tries to unify two literals, A and B.
;;; If the unification is successful, an environment is returned which
;;; contains the mgu.
;;; Returns: an environment list if A unifies with B,
;;;          'LESS if A does not unify with B, and A < B
;;;          'GREATER if A does not unify with B, and B > A.

(define (unify a b enva envb)
  (if (not (= (length (literal-body a)) (length (literal-body b))))
      (if (literal<? a b) 'LESS 'GREATER)
      (unif (literal-body a) (literal-body b) enva envb)))
 

(define (unif a b enva envb)
  (define (symbol<? x y) (string<? (symbol->string x) (symbol->string y)))
  (cond ((null? a) enva)
        ((integer? (car a))
         (unif (cons (lookup (car a) enva) (cdr a)) b enva envb))
        ((integer? (car b))
         (unif a (cons (lookup (car b) envb) (cdr b)) enva envb))
        ((symbol? (car a))
         (cond ((symbol? (car b)) 
                (cond ((eq? (car a) (car b))
                       (unif (cdr a) (cdr b) enva envb))
                      ((symbol<? (car a) (car b)) 'LESS)
                      (else 'GREATER)))
               ((pair? (car b)) 'LESS)
               ((logic-var? (car b))
                (set! (logic-var-val (car b)) (car a))
                (unif (cdr a) (cdr b) enva envb))
               (else 
                 (error "UNIF confused-a" (car a) (car b)))))
        ((symbol? (car b))
         (cond ((symbol? (car a))
                (cond ((eq? (car a) (car b))
                       (unif (cdr a) (cdr b) enva envb))
                      ((symbol<? (car a) (car b)) 'LESS)
                      (else 'GREATER)))
               ((pair? (car a)) 'GREATER)
               ((logic-var? (car a))
                (set! (logic-var-val (car a)) (car b))
                (unif (cdr a) (cdr b) enva envb))
               (else 
                 (error "UNIF confused-b" (car b) (car a)))))
        ((and (pair? (car a)) (pair? (car b)))
         (let ((result (unif (car a) (car b) enva envb)))
           (if (pair? result)
               (unif (cdr a) (cdr b) enva envb)
               result)))
        ((logic-var? (car a)) 
         (set! (logic-var-val (car a)) (car b))
         (unif (cdr a) (cdr b) enva envb))
        ((logic-var? (car b))
         (set! (logic-var-val (car b)) (car a))
         (unif (cdr a) (cdr b) enva envb))
        (else
          (error "UNIF confused " (car a) (car b)))))

        
                      


;;; COMBINE
;;; Combines two clauses, A and B into one, performing mgu substitutions
;;; are according to the environments ENVA and ENVB.  Any duplicate literals
;;; omitted.

(define (combine a b enva envb)
  (define (instantiate-literal x env)
    (make-literal 'sign (literal-sign x)
                  'body (subst (literal-body x) env)))
  (let* ((new-bindings (remap-vars enva))
         (new-a (mapcar (lambda (x) (instantiate-literal x enva)) a))
         (new-b (mapcar (lambda (x) (instantiate-literal x envb)) b)))
    (make-clause 'label (gensym)
                 'bindings new-bindings
                 'literals (sorted-merge new-a new-b literal<?))))



;;; LOOKUP
;;; Dereferences a variable INDEX in ENVironment.

(define (lookup index env)
  (define (follow chain)
    (if (not (atom? (logic-var-val (car chain))))
        (follow (logic-var-val (car chain)))
        (if (integer? (logic-var-val (car chain)))
            (car chain)
            (logic-var-val (car chain)))))
  (follow (list-tail env index)))


;;; MAKE-ENV
;;; Creates an environment of size N.

(define (make-env n) 
  (define (make-env-1 n)
    (if (zero? n) 
        nil 
        (cons (make-logic-var 'val (-1+ n)) (make-env-1 (-1+ n)))))
  (reverse! (make-env-1 n)))


;;; REMAP-VARS
;;; Reassigns variable indexes in an mgu'ed ENVironment.  Each unique
;;; variable will exist only once in the environment, so it is easy to
;;; remap.

(define (remap-vars env)
  (define (var-map env count)
    (cond ((null? env) count)
          ((integer? (logic-var-val (car env)))
           (set! (logic-var-val (car env)) count)
           (var-map (cdr env) (1+ count)))
          (else
            (var-map (cdr env) count))))
  (var-map env 0))



;;; SUBST
;;; Instantiate any variables in X with values in ENVironment.

(define (subst x env)
  (cond ((null? x) nil)
        ((symbol? x) x)
        ((pair? x) (cons (subst (car x) env) (subst (cdr x) env)))
        ((integer? x) (subst (car (list-tail env x)) env))
        ((logic-var? x)
         (if (integer? (logic-var-val x))
             (logic-var-val x)
             (subst (logic-var-val x) env)))))






;;;; GENERIC LIST HANDLING FUNCTIONS


;;; DELETE
;;; Non-destructive deletion of OBJ from LIST.  Returns a copy of list.

(define (delete obj list)
  (cond ((null? list) nil)
        ((equal? obj (car list)) (delete obj (cdr list)))
        (else
          (cons (car list) (delete obj (cdr list))))))
             
      
;;; FILTER
;;; Filters out members of a list that fail PRED.

(define (filter pred list)
  (cond ((null? list) nil)
        ((pred (car list)) (cons (car list) (filter pred (cdr list))))
        (else (filter pred (cdr list)))))

;;; FLATTEN
;;; Flattens a list.

(define (flatten list)
  (cond ((null? list) nil)
        ((pair? (car list)) (append (flatten (car list)) (flatten (cdr list))))
        (else (cons (car list) (flatten (cdr list))))))


;;; SORTED-MERGE
;;; Merges two lists sorted according to a comparison predicate LESS?,
;;; removing any duplicates.
 
(define (sorted-merge a b less?)
  (define (merge a b previous)
    (cond ((and (null? a) (null? b)) nil)
          ((equal? (car a) previous) (merge (cdr a) b previous))
          ((equal? (car b) previous) (merge a (cdr b) previous))
          ((null? a) (cons (car b) (merge a (cdr b) (car b))))
          ((null? b) (cons (car a) (merge (cdr a) b (car a))))
          ((equal? a b) (merge a (cdr b) previous))
          ((less? (car a) (car b))
           (cons (car a) (merge (cdr a) b (car a))))
          (else
            (cons (car b) (merge a (cdr b) (car b))))))
  (merge a b '*&&&*%@*))








;;;; TEST CLAUSE SETS

;;; Example 1 in Robinson's hyper-resolution paper.

(define EX1
  (list (defclause c1 (x y) (P x y))
        (defclause c2 (x y) (not (P y (f x y))) (not (P (f x y) (f x y))) 
                   (Q x y))
        (defclause c3 (x y) (not (P y (f x y))) (not (P (f x y) (f x y)))
                   (not (Q x (f x y))) (not (Q (f x y) (f x y))))))

;;; Example 2 in Robinson's hyper-resolution paper.

(define EX2
  (list (defclause c1 () (P a b c))
        (defclause c2 (x) (P x x e))
        (defclause c3 (x) (P x e x))
        (defclause c4 (x) (P e x x))
        (defclause c5 () (not (P b a c)))
        (defclause c6 (u v w x y z) (not (P x y u)) (not (P y z v))
                   (not (P x v w)) (P u z w))
        (defclause c7 (u v w x y z) (not (P x y u)) (not (P y z v))
                   (not (P u z w)) (P x v w))))


