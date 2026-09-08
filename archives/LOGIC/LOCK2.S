;;; Lock Resolution Theorem Prover, Version 2
;;; Mike Hilton, 23 March 1989

; (load "basics.s")

(define positives nil)  ; clauses with all positive literals
(define negatives nil)  ; clauses with one or more negative literals

(define resolutions 0)  ; count of the number of attempted resolutions
(define resolvents nil) ; list of resolvents formed in a current lock-step
(define flag #f) ; boolean flag to signal at least one positive resolution

;;; ALLOWABLE?
;;; Checks to see if a positive clause can be added to the list of 
;;; positive clauses.  This check should be modified to be a subsumption
;;; test instead of an equality test.

(define (allowable? clause) (not (member? clause positives)))


;;; LOCK
;;; Attempts to find a lock-resolution proof of the input set CLAUSES.

(define (lock clauses)
  (set! resolutions 0)
  (set! positives nil)
  (set! negatives nil)
  (sort-clauses clauses)
  (call/cc 
    (lambda (exit)
      (let ((iter 0))
        (let loop ()
          (set! iter (1+ iter))
          (writeln "LOCK-RESOLUTION, step " iter)
          (set! flag #F)
          (lock-1 0 exit negatives)
          (if flag
              (loop)
              (writeln "FAILURE; no new positive clauses generated.  "
                       resolutions
                       " resolutions attempted.")))))))

(define (lock-1 step exit negs)
  (writeln "LOCK-1 depth " step)
  (let ((resolves (lock-step step exit negs)))
    (when resolves
          (let ((count 0)
                (new-negs  (filter negative-clause? resolves)))
            (writeln (length new-negs) " negative clauses generated.")
            (for-each (lambda (x) 
                        (when (allowable? x)
                              (set! flag #T)
                              (set! count (1+ count))
                              (set! positives (insert x positives))))
                      (filter positive-clause? resolves))
            (writeln count " new positive clauses added.")
            (when new-negs
                  (let ((n nil))
                    (for-each (lambda (x) (set! n (insert x n))) 
                              new-negs)
                    (lock-1 (1+ step) exit n)))))))

  

      
;;; LOCK-STEP

(define (lock-step step exit negs)
  (set! resolvents nil)
  (let loop ((nclauses negs) (pclauses positives))
    (if (or (null? nclauses) (null? pclauses))
        resolvents
        (let ((resolvent (lock-resolve (car nclauses) (car pclauses))))
          (case resolvent
            (LESS (loop (cdr nclauses) pclauses))
            (GREATER (loop nclauses (cdr pclauses)))
            (else
              (classify-resolvent resolvent exit)
              (explore (car nclauses) (cdr pclauses) exit)
              (loop (cdr nclauses) pclauses)))))))
    
    
    
;;; EXPLORE
;;; Continue exploring the positive clauses for more possible resolvents.

(define (explore clause pclauses exit)
  (when pclauses
        (let ((resolvent (lock-resolve clause (car pclauses))))
          (when (clause? resolvent)
                (classify-resolvent resolvent exit)
                (explore clause (cdr pclauses) exit)))))    
    
    
    
;;; CLASSIFY-RESOLVENT
;;; Decides what to do with a resolvent.
    
(define (classify-resolvent resolvent exit)
  (cond ((empty-clause? resolvent)
         (writeln "EMPTY RESOLVENT! Success with " resolutions
                  " resolution attempts")
         (exit #T))
        ((positive-clause? resolvent)
         (set! resolvents (cons resolvent resolvents)))
        ((and (negative-clause? resolvent)
              (not (member? resolvent negatives)))
         (set! resolvents (cons resolvent resolvents)))))




;;; LOCK-RESOLVE
;;; Attempts to resolve the first literals of two sorted clauses together.  
;;; Returns the resolvent, if found; 
;;;         LESS, if a < b;
;;;         GREATER, if a > b;                             

(define (lock-resolve a b)
  (set! resolutions (1+ resolutions))
  (let* ((env-size (+ (clause-bindings a) (clause-bindings b)))
         (envb-start (clause-bindings a))
         (enva (make-env env-size))
         (envb (list-tail enva envb-start))
         (result (unify (first-literal a) (first-literal b) enva envb)))
    (case result
      (LESS 'LESS)
      (GREATER 'GREATER)
      (else
        (let ((new-a (delete (first-literal a) (clause-literals a)))
              (new-b (delete (first-literal b) (clause-literals b))))
          (combine new-a new-b enva envb))))))


;;; SORT-CLAUSES
;;; Sorts the clause database into two groups: the positive clauses and
;;; those which contain at least one negative literal.

(define (sort-clauses x)
  (for-each 
    (lambda (clause)
      (cond ((positive-clause? clause)
             (set! positives (insert clause positives)))
            (else
              (set! negatives (insert clause negatives)))))
    x))



;;; INSERT
;;; Inserts a CLAUSE into LST using LITERAL<? as the collating sequence
;;; function.  The clauses are sorted according to their first literal.

(define (insert clause lst)
  (define (insert-1 literal lst)
    (cond ((literal<? literal (first-literal (car lst)))
           (set-cdr! lst (cons (car lst) (cdr lst)))
           (set-car! lst clause))
          ((null? (cdr lst))
           (set-cdr! lst (cons clause nil)))
          (else
            (insert-1 literal (cdr lst)))))
  (cond ((null? lst) (list clause))
        (else 
          (insert-1 (first-literal clause) lst)
          lst)))
