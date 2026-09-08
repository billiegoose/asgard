;;; Order(n) Theorem Proving Data Structures and Common Functions
;;; Mike Hilton, 24 April 1989

;;; This file is a collection of basic utilities for creating and using
;;; ordered clauses for theorem proving.

(load "c:\\logic\\format.s")

(define-structure clause label poslits neglits index)
(define-printer
  clause
  (apply string-append 
         (cons "{ "
               (append (mapcar object->string (clause-neglits clause))
                       (mapcar object->string (clause-poslits clause))
                       '("}")))))

(define-structure literal sign body)
(define-printer
  literal
  (let ((string (object->string (literal-body literal))))
    (if (eq? (literal-sign literal) 'POSITIVE)
        (string-append string " ")
        (string-append "-" string " "))))

(define-structure variable id index)
(define-printer
  variable
  (string-append "<" (symbol->string (variable-id variable)) ":"
                 (object->string (variable-index variable)) ">"))



(define bndenv nil)
(define clause-cnt 0)



(define (empty-clause? x) 
  (and (null? (clause-poslits x))
       (null? (clause-neglits x))))

(define (negative-clause? x)
  (and (null? (clause-poslits x))
       (clause-neglits x)))

(define (positive-clause? x)
  (null? (clause-neglits x)))




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
      (define (parse-clause literals)
        (define (parse-lit lit)
          (cond ((and (atom? lit) (member lit bindings))
                 (make-variable 'id lit 'index clause-cnt))
                ((atom? lit) lit)
                (else (mapcar parse-lit lit))))
        (define (parse-literal lit)
          (let ((sign (if (eq? (car lit) 'not) 
                          (begin0 'NEGATIVE (set! lit (cadr lit)))
                          'POSITIVE)))
            (make-literal 'sign sign
                          'body (mapcar parse-lit lit))))
        (sort! (mapcar parse-literal literals) literal<=?))
      (define (filter pred list)
        (cond ((null? list) nil)
              ((pred (car list)) (cons (car list) (filter pred (cdr list))))
              (else (filter pred (cdr list)))))
      
      (set! clause-cnt (1+ clause-cnt))
      (let ((literals (parse-clause body)))
        (make-clause 'label label
                     'index 1
                     'poslits (filter (lambda (x) 
                                        (eq? (literal-sign x) 'positive))
                                      literals)
                     'neglits (filter (lambda (x) 
                                        (eq? (literal-sign x) 'negative))
                                      literals))))))


;;; BIND
;;; Binds the variable X,I to VAL,J in the global binding environment
;;; BNDENV.

(define (bind x i val j) 
  (set! bndenv (cons (cons (cons x i) (cons val j))
                     bndenv)))


;;; COMBINE
;;; Combines two clauses, A and B into one, performing mgu substitutions
;;; according to the values in the global environment BNDENV. The literals
;;; ALIT and BLIT are removed from the clause.

(define (combine a alit b blit)
  (define (subst x xi y yi)
    (cond ((and (null? x) (null? y)) nil)
          ((null? x) (subst y yi nil nil))
          ((or (eq? (car x) alit) (eq? (car x) blit)) 
           (subst (cdr x) xi y yi))
          (else (cons (instantiate (car x) xi) (subst (cdr x) xi y yi)))))
  (set! clause-cnt (1+ clause-cnt))
  (make-clause 'label (gensym)
               'index clause-cnt
               'poslits (sort! (subst (clause-poslits a) (clause-index a)
                                      (clause-poslits b) (clause-index b))
                               literal<=?)
               'neglits (sort! (subst (clause-neglits a) (clause-index a)
                                      (clause-neglits b) (clause-index b))
                               literal<=?)))


;;; GETLIT
;;; Returns the Kth literal in the clause CL.

(define (getlit cl k)
  (if (<= k (length (clause-neglits cl)))
      (list-ref (clause-neglits cl) (-1+ k))
      (list-ref (clause-poslits cl) (- k (length (clause-neglits cl)) 1))))


;;; INSTANTIATE
;;; Instantiate TERM with values in the global environment BNDENV.

(define (instantiate term index)
  (cond ((variable? term) 
         (let ((val (lookup term index)))
           (if val
               (instantiate (car val) (cdr val))
               (make-variable 'id (variable-id term) 
                              'index (+ index (variable-index term))))))
        ((literal? term)
         (make-literal 'sign (literal-sign term)
                       'body (instantiate (literal-body term) index)))
        ((atom? term) term)
        ((pair? term)
         (cons (instantiate (car term) index)
               (instantiate (cdr term) index)))))



;;; LITERAL<=?
;;; A predicate used to compare literals and provide a collating sequence.
;;; The rules used in comparing are:
;;;   negative literals < positive literals
;;;   atoms < functions < variables
;;;   atoms are sorted alphabetically
;;;   variables are considered equal
;;; Returns #T if literal A is less than or equal to literal B, #F otherwise.
;;; SUPRESS-SIGN supresses the comparison of the literals' signs, so that
;;; their bodies can be compared.

(define (literal<=? a b . supress-sign)
  (define (symbol<=? x y) (string<=? (symbol->string x) (symbol->string y)))
  (define (lit<=? x y)
    (cond ((or (null? x) (null? y)) (null? x))
          ((equal? (car x) (car y)) (lit<=? (cdr x) (cdr y)))
          ((symbol? (car x))
           (if (symbol? (car y)) 
               (symbol<=? (car x) (car y))
               #F))
          ((variable? (car x))
           (if (variable? (car y)) 
               (lit<=? (cdr x) (cdr y))
               #F))
          ((pair? (car x))
           (cond ((symbol? (car y)) #F)
                 ((variable? (car y)) #T)
                 ((pair? (car y))
                  (and (lit<=? (car x) (car y)) (lit<=? (cdr x) (cdr y))))))))
  (cond (supress-sign  (lit<=? (literal-body a) (literal-body b)))
        ((eq? (literal-sign a) (literal-sign b))
         (lit<=? (literal-body a) (literal-body b)))
        (else (eq? (literal-sign a) 'NEGATIVE))))
     


;;; LOOKUP
;;; Look up the value of a variable in the global environment BNDENV.

(define (lookup x index)
  (cdr (assoc (cons x index) bndenv)))


;;; OCCUR
;;; Determines whether some variable VAR occurs in the value of the
;;; expression TERM in the context of the global environment BNDENV.

(define (occur var i term j)
  (cond ((null? term) #F)
        ((variable? term)
         (let ((tval (lookup term j)))
           (cond (tval (occur var i (car tval) (cdr tval)))
                 ((and (equal? var term) (= i j)) #T)
                 (else #F))))
        ((pair? term)
         (or (occur var i (car term) j)
             (occur var i (cdr term) j)))))
           

;;; RESOLVE
;;; Resolves the two clauses CL1 and CL2 on their Ith and Jth literals,
;;; respectively.

(define (resolve cl1 i cl2 j)
  (let ((lit1 (getlit cl1 i))
        (lit2 (getlit cl2 j)))
    (set! bndenv nil)
    (cond ((eq? (literal-sign lit1) (literal-sign lit2)) #F)
          ((unify lit1 (clause-index cl1) lit2 (clause-index cl2))
           (combine cl1 lit1 cl2 lit2)))))


;;; SUBSUMES?
;;; Predicate to test if clause A subsumes clause B.

(define (subsumes? a b)
  (define (check xs ys)
    (let ((bindings bndenv))
      (cond ((null? xs) #T)
            ((null? ys) #F)
            (else (case (ordered-unify (car xs) 1 (car ys) 2 #T)
                    (EQUAL (if (check (cdr xs) ys)
                               #T
                               (begin
                                 (set! bndenv bindings)
                                 (check xs (cdr ys)))))
                    (LESS (set! bndenv bindings)
                          (check xs (cdr ys)))
                    (GREATER (set! bndenv bindings)
                             #F))))))
  (set! bndenv nil)
  (and (check (clause-poslits a) (clause-poslits b))
       (check (clause-neglits a) (clause-neglits b))))
          
  

;;; TAUTOLOGY?
;;; Predicate to determine if CLAUSE is a tautology.

(define (tautology? clause)
  (let loop ((pos (clause-poslits clause)) 
             (neg (clause-neglits clause)))
    (cond ((or (null? pos) (null? neg)) #F)
          ((equal? (literal-body (car pos)) (literal-body (car neg))) #T)
          ((literal<=? (car pos) (car neg) #T)
           (loop (cdr pos) neg))
          (else (loop pos (cdr neg))))))


;;; UNIFY  -- (conventional unification)
;;; Tries to unify two literals, A and B. Returns #T if successful (the
;;; proper binding environment is bound to the global variable BNDENV);
;;; returns #F otherwise.

(define (unify a aindex b bindex)
  (define (unif term1 index1 term2 index2)
    (cond ((and (equal? term1 term2) (= index1 index2)) #T)
          ((variable? term1)
           (let ((val1 (lookup term1 index1)))
             (cond (val1
                     (unif (car val1) (cdr val1) term2 index2))
                   ((occur term1 index1 term2 index2) #F)
                   (else (bind term1 index1 term2 index2) #T))))
          ((variable? term2) (unif term2 index2 term1 index1))
          ((and (eq? (car term1) (car term2))
                (= (length term1) (length term2)))
           (let loop ((t1 (cdr term1)) (t2 (cdr term2)))
             (cond ((null? t1) #T)
                   ((unif (car t1) index1 (car t2) index2)
                    (loop (cdr t1) (cdr t2)))
                   (else #F))))
          (else #F)))
  (unif (literal-body a) aindex (literal-body b) bindex))



;;; ORESOLVE
;;; Resolves the two clauses CL1 and CL2 on their Ith and Jth literals,
;;; respectively, using ordered unification.

(define (oresolve cl1 i cl2 j)
  (let ((lit1 (getlit cl1 i))
        (lit2 (getlit cl2 j)))
    (set! bndenv nil)
    (cond ((eq? (literal-sign lit1) (literal-sign lit2)) #F)
          (else
           (case (ordered-unify lit1 (clause-index cl1) 
                                lit2 (clause-index cl2))
             (EQUAL (combine cl1 lit1 cl2 lit2))
             (LESS 'less)
             (GREATER 'greater))))))


;;; ORDERED-UNIFY -- (Ordered Unification)
;;; Tries to unify two literals, A and B.  
;;; Returns 'EQUAL    if successful (the proper binding environment is bound 
;;;                   to the global variable BNDENV); 
;;;         'LESS     if A does not unify with B and A < B; 
;;;         'GREATER  if A does not unify with B and A > B.
;;; SUPRESS-TERM2 is used to "turn off" the variables in term2, so
;;; ordered-unify can be used for subsumption testing.

(define (ordered-unify a aindex b bindex . supress-term2)
  (let ((answer nil))
    (define (symbol<? x y) 
      (cond ((string<? (symbol->string x) (symbol->string y))
             (set! answer 'LESS) #F)
            (else (set! answer 'GREATER) #F)))
    (define (unif term1 index1 term2 index2)
      (cond ((and (equal? term1 term2) (= index1 index2)) #T)
            ((eq? term1 term2) #T)
            ((variable? term1)
             (let ((val1 (lookup term1 index1)))
               (cond (val1  (unif (car val1) (cdr val1) term2 index2))
                     ((occur term1 index1 term2 index2)
                      (set! answer 'GREATER) #F)
                     (else (bind term1 index1 term2 index2) #T))))
            ((and (null? supress-term2) (variable? term2))
             (let ((val2 (lookup term2 index2)))
               (cond (val2  (unif term1 index1 (car val2) (cdr val2)))
                     ((occur term2 index2 term1 index1)
                      (set! answer 'LESS) #F)
                     (else (bind term2 index2 term1 index1) #T))))
            ((symbol? term1)
             (cond ((symbol? term2) (symbol<? term1 term2))
                   (else (set! answer 'LESS) #F)))
            ((symbol? term2)
             (set! answer 'GREATER) #F)
            ((unif (car term1) index1 (car term2) index2)
             (unif (cdr term1) index1 (cdr term2) index2))))
    (if (unif (literal-body a) aindex (literal-body b) bindex)
        'EQUAL
        answer)))

          
