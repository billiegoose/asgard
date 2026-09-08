;;; Implementation of Boyer-Moore structure sharing for theorem proving
;;; as described in their paper in Machine Intelligence 7.
;;; Mike Hilton, 19 April 1989

(load "c:\\logic\\format.s")

(define-structure input-record
		  label
                  literals
                  num-literals-in)

(define-printer
  input-record
  (apply string-append 
         (cons "{ " (append (mapcar object->string 
                                   (input-record-literals input-record))
                           '("}")))))

(define-structure resolvent-record
                  left-parent
                  left-literal-number
                  right-parent
                  right-literal-number
                  num-literals-in
                  max-index
                  bindings)

(define-printer
  resolvent-record
  (apply string-append 
         (cons "{ "  
               (append (mapcar object->string (reconstruct resolvent-record))
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

(define litg nil)
(define indexg nil)
(define termb nil)
(define indexb nil)
(define bndev nil)



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
      (define (parse-literal lit)
        (define (parse-lit x)
          (cond ((and (atom? x) (member x bindings))
                 (make-variable 'id x 'index label))
                ((atom? x) x)
                (else (mapcar parse-lit x))))
        (let ((sign (if (eq? (car lit) 'not) 
                        (begin0 'NEGATIVE (set! lit (cadr lit)))
                        'POSITIVE)))
          (make-literal 'sign sign 'body (mapcar parse-lit lit))))
      (make-input-record 
        'label label
        'literals (mapcar parse-literal body)
        'num-literals-in (length body)))))
             




;;; BIND
;;; Add a binding, (V,I . T,J) to BNDEV.

(define (bind v i term j bndev)
  (set! (resolvent-record-bindings bndev)
        (cons (cons (cons v i) (cons term j)) 
              (resolvent-record-bindings bndev))))


;;; GETLIT
;;; Sets the global variable LITG to the input literal and the global
;;; variable INDEXG to the index such that the expression LITG,INDEXG
;;; represents the Kth literal of CL (in the binding envrionment of CL).

(define (getlit cl k)
  (cond ((input-record? cl)
         (set! litg (list-ref (input-record-literals cl) (-1+ k)))
         (set! indexg 1))
        ((< k (resolvent-record-left-literal-number cl))
         (getlit (resolvent-record-left-parent cl) k))
        ((< k (number-of-literals-in (resolvent-record-left-parent cl)))
         (getlit (resolvent-record-left-parent cl) (1+ k)))
        ((< k (+ (number-of-literals-in (resolvent-record-left-parent cl))
                 -1
                 (resolvent-record-right-literal-number cl)))
         (getlit (resolvent-record-right-parent cl)
                 (1+ (- k (number-of-literals-in 
                            (resolvent-record-left-parent cl)))))
         (set! indexg (+ indexg (maximum-index 
                                  (resolvent-record-left-parent cl)))))
        (else
          (getlit (resolvent-record-right-parent cl)
                  (+ 2 (- k (number-of-literals-in
                              (resolvent-record-left-parent cl)))))
          (set! indexg (+ indexg (maximum-index
                                   (resolvent-record-left-parent cl)))))))



;;; INSTANTIATE
;;; Instantiates a term TERM,INDEX in the context of ENV.

(define (instantiate term index env)
  (cond ((and (variable? term) (isbound term index env))
         (instantiate termb indexb env))
        ((variable? term) 
         (make-variable 'id (variable-id term) 'index index))
        ((literal? term)
         (make-literal 'sign (literal-sign term)
                       'body (instantiate (literal-body term) index env)))
        ((atom? term) term)
        ((pair? term)
         (cons (instantiate (car term) index env)
               (instantiate (cdr term) index env)))))


;;; ISBOUND
;;; Returns true if VAR,INDEX is bound in BNDEV; otherwise, it returns false.
;;; If the call returns true, then isbound sets the global variables TERMB
;;; to the term and INDEXB to the index that VAR,INDEX is bound to.

(define (isbound var index bndev)
  (let ((val nil))
    (cond ((input-record? bndev) #F)
          ((set! val (assoc (cons var index) 
                            (resolvent-record-bindings bndev)))
           (set! termb (cadr val))
           (set! indexb (cddr val))
           #T)
          ((<= index (maximum-index (resolvent-record-left-parent bndev)))
           (isbound var index (resolvent-record-left-parent bndev)))
          ((isbound var 
                    (- index (maximum-index
                               (resolvent-record-left-parent bndev)))
                    (resolvent-record-right-parent bndev))
           (set! indexb (+ indexb (maximum-index 
                                    (resolvent-record-left-parent bndev))))
           #T)
          (else #F))))


;;; MAXIMUM-INDEX
;;; Returns the maximum index for a clause CL.

(define (maximum-index cl)
  (if (input-record? cl)
      1
      (resolvent-record-max-index cl)))


;;; NUMBER-OF-LITERALS-IN
;;; Returns the number of literals in a clause CL.

(define (number-of-literals-in cl)
  (cond ((input-record? cl) (input-record-num-literals-in cl))
        ((resolvent-record? cl) (resolvent-record-num-literals-in cl))))


;;; OCCUR
;;; Determines whether some variable V,I occurs in the value of the expression
;;; TERM,J in the binding environment BNDEV.

(define (occur v i term j)
  (cond ((null? term) #F)
        ((variable? term)
         (cond ((isbound term j bndev) (occur v i termb indexb))
               ((and (equal? v term) (= i j)) #T)
               (else #F)))
        ((pair? term)
         (or (occur v i (car term) j)
             (occur v i (cdr term) j)))))


;;; RECONSTRUCT
;;; Reconstructs a fully instantiated clause from a resolvent-record.

(define (reconstruct cl)
  (let loop ((k 1))
    (cond ((> k (number-of-literals-in cl)) nil)
          (else
            (getlit cl k)
            (cons (instantiate litg indexg cl) 
                  (loop (1+ k)))))))


;;; RESOLVE
;;; Resolves two clause records CL1 and CL2 on their Ith and Jth literals
;;; respectively.

(define (resolve cl1 i cl2 j)
  (let ((leftlit nil)
        (leftindex nil)
        (rightlit nil)
        (rightindex nil))
    (getlit cl1 i)
    (set! leftlit litg)
    (set! leftindex indexg)
    (getlit cl2 j)
    (set! rightlit litg)
    (set! rightindex (+ indexg (maximum-index cl1)))
    (cond ((eq? (literal-sign leftlit) (literal-sign rightlit))
           #F)
          (else
            (set! bndev
                  (make-resolvent-record
                    'left-parent cl1
                    'left-literal-number i
                    'right-parent cl2
                    'right-literal-number j
                    'num-literals-in (- (+ (number-of-literals-in cl1)
                                           (number-of-literals-in cl2))
                                        2)
                    'max-index (+ (maximum-index cl1) (maximum-index cl2))
                    'bindings nil))
            (if (unify (literal-body leftlit) leftindex
                       (literal-body rightlit) rightindex)
                bndev
                #F)))))


;;; UNIFY
;;; Checks to see if TERM1,INDEX1 and TERM2,INDEX2 unify in the context of 
;;; BNDEV. Returns true or false.  BNDEV is altered during the call to contain
;;; the mgu.

(define (unify term1 index1 term2 index2)
  (cond ((and (equal? term1 term2) (= index1 index2)) #T)
        ((variable? term1)
         (cond ((isbound term1 index1 bndev)
                (unify termb indexb term2 index2))
               ((occur term1 index1 term2 index2) #F)
               (else (bind term1 index1 term2 index2 bndev) #T)))
        ((variable? term2) (unify term2 index2 term1 index1))
        ((and (eq? (car term1) (car term2))
              (= (length term1) (length term2)))
         (let loop ((t1 (cdr term1)) (t2 (cdr term2)))
           (cond ((null? t1) #T)
                 ((unify (car t1) index1 (car t2) index2)
                  (loop (cdr t1) (cdr t2)))
                 (else #F))))
        (else #F)))

