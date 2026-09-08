;;; Hyper-Resolution Theorem Prover, Version 4
;;; Mike Hilton, 22 March 1989

(load "basics.s")

;;; Very simple hyper-resolution theorem prover, with suffers from acute
;;; combinatorial explosion.  An exhaustive depth-first search is performed
;;; to find all hyper-resolvents at each level of the proof.  The levels
;;; terminate when either one of the hyper-resolvents is the empty clause 
;;; (success) or no new hyper-resolvents are found (failure).

;;; The negative clauses that are deduced
;;; in each hyper-resolution step are kept on a list, and each new
;;; negative clause that is deduced is checked for membership on this
;;; list.  If it is a member, then this clause has already been explored
;;; and can be abandoned.  This history list is flushed after each hyper-
;;; resolution step.


(define history nil)    ; negative clauses deduced during this H-R step
(define positives nil)  ; clauses with all positive literals
(define negatives nil)  ; clauses with one or more negative literals

(define turn-downs 0)   ; count of the clauses not explored in this H-R step
			; because they were on the history list.



;;; ALLOWABLE?
;;; Checks to see if a positive clause can be added to the list of 
;;; positive clauses.  This check should be modified to be a subsumption
;;; test instead of an equality test.

(define (allowable? clause) (not (member? clause positives)))


;;; HYPER
;;; Attempts to find a hyper-resolution proof of the input set CLAUSES.

(define (hyper clauses)
  (set! positives nil)
  (set! negatives nil)
  (sort-clauses clauses)
  (hyper-step 0))



;;; HYPER-RESOLVE
;;; Continues resolving clause X against the set of positive clauses
;;; until there is no longer any resolutions possible. Returns:
;;;   nil, if there are no hyper-resolvents
;;;   a list of clauses, each of which is a hyper-resolvent.

(define (hyper-resolve x)
  (cond ((null? x) nil)
        ((empty-clause? x) x)
        ((and (positive-clause? x) (allowable? x)) x)
        ((member? x history) 
         (set! turn-downs (1+ turn-downs))
         nil)
        (else
          (set! history (cons x history))
          (filter (lambda (x) (not (null? x)))
                  (flatten 
                    (mapcar hyper-resolve
                            (flatten 
                              (mapcar (lambda (y) (resolve x y))
                                      positives))))))))



;;; HYPER-STEP
;;; Performs a single hyper-resolution step.  Finds all the hyper-resolvents
;;; possible given the current set of clauses.

(define (hyper-step steps)
  (writeln "HYPER-RESOLUTION step " steps)
  (set! turn-downs 0)
  (set! history nil)
  (let ((hyper-resolvents 
          (filter (lambda (x) (not (null? x)))
                  (flatten (mapcar hyper-resolve negatives)))))
    (writeln turn-downs " clauses were turned down.")
    (cond ((null? hyper-resolvents) 
           (writeln "No new hyper-resolvents produced;  proof fails at step "
                    steps))
          ((filter empty-clause? hyper-resolvents)
           (writeln "SOLUTION FOUND! in  " steps " steps. "))
          ((filter positive-clause? hyper-resolvents)
           (let ((not-allowable 0))
             (for-each 
               (lambda (x)
                 (if (allowable? x)
                     (begin (set! positives (cons x positives))
                            (writeln "Hyper-resolvents found: " x))
                     (set! not-allowable (1+ not-allowable))))
             (filter positive-clause? hyper-resolvents))
             (if (not (zero? not-allowable))
                 (writeln not-allowable 
                          " hyper-resolvents were not allowable.")))
           (hyper-step (1+ steps))
           ))))



;;; RESOLVE
;;; Attempts to resolve two sorted clauses together.  NCLAUSE may contain 
;;; negative clauses; PCLAUSE must contain only positive clauses.
;;; Returns a list of all the resolvents found.

(define (resolve nclause pclause)
  (let ((env-size (+ (clause-bindings nclause) (clause-bindings pclause)))
        (envb-start (clause-bindings nclause))
        (resolvents nil))
    (let loop ((a (clause-literals nclause))
               (b (clause-literals pclause)))
      (cond ((or (null? a) (null? b)) resolvents)
            ((eq? 'POSITIVE (literal-sign (car a))) resolvents)
            (else
              (let* ((enva (make-env env-size))
                     (envb (list-tail enva envb-start))
                     (result (unify (car a) (car b) enva envb)))
                (case result
                  (LESS (loop (cdr a) b))
                  (GREATER (loop a (cdr b)))
                  (else
                    (let ((new-nclause
                            (delete (car a) (clause-literals nclause)))
                          (new-pclause
                            (delete (car b) (clause-literals pclause))))
                      (set! resolvents 
                            (cons (combine new-nclause new-pclause enva envb)
                                  resolvents))
                      (loop (cdr a) b))))))))))


;;; SORT-CLAUSES
;;; Sorts the clause database into two groups: the positive clauses and
;;; those which contain at least one negative literal.

(define (sort-clauses x)
  (for-each 
    (lambda (clause)
      (cond ((positive-clause? clause)
             (set! positives (cons clause positives)))
            (else
              (set! negatives (cons clause negatives)))))
    x))

