;;; PRIMITIVE OPERATORS OF THE LAMBDA REDUCTION MACHINE
;;; Mike Hilton, 26 June 1989

(define (type=? type val) (eq? type (d-reg-type val)))
(define (class=? class val) (eq? class (d-reg-class val)))

;;; NUM->NUM->NUM-FUNCTION
;;; Implements binary functions of type NUMxNUM->NUM.
;;; Upon entry, PGAR contains addr of second operand
;;;             PGDR contains operator
;;;             RGDR contains second operand
;;; Upon exit,
;;;             PGDR contains result.
;;;             RGAR has been decremented twice.

(define (num->num->num-function operator)
  (cond ((member (d-reg-type rgdr) '(FLOAT INT))  ; check type of second arg
         (mread (1+ pgar) argreg)                 ; argreg <- first arg
         (cond ((member (d-reg-type argreg) '(FLOAT INT))  ; check type 1st arg
                (let ((result (operator (d-reg-operand argreg) 
                                        (d-reg-operand rgdr))))
                  (set! (d-reg-class pgdr) 'HEAD)
                  (set! (d-reg-type pgdr) (if (integer? result) 'INT 'FLOAT))
                  (set! (d-reg-operand pgdr) result)
                  (transfer pgdr pgdr))
                (transfer (1+ reductions) reductions)
                (transfer (- rgar 2) rgar)     ; pop prim and args off result
                (mwrite rgar pgdr)             ; put result into result graph
                (show (send simulator send-pane 'result 'remove-last)
                      (send simulator send-pane 'result 'remove-last)))
               (else
                 (transfer rgdr pgdr))))
        (else
          (transfer rgdr pgdr)))
  (goto move-backward))

(primitive +  (num->num->num-function +))
(primitive -  (num->num->num-function -))
(primitive *  (num->num->num-function *))
(primitive /  (num->num->num-function /))
(primitive modulo  (num->num->num-function modulo))
(primitive expt  (num->num->num-function expt))
(primitive max  (num->num->num-function max))
(primitive min  (num->num->num-function min))




;;; NUM->NUM->BOOL-FUNCTION
;;; Implements binary functions of type NUMxNUM->BOOLEAN.
;;; Upon entry, PGAR contains addr of second operand
;;;             PGDR contains operator
;;;             RGDR contains second operand
;;; Upon exit,
;;;             PGDR contains result.
;;;             RGAR has been decremented twice.

(define (num->num->bool-function operator)
  (cond ((member (d-reg-type rgdr) '(FLOAT INT))  ; check type of second arg
         (mread (1+ pgar) argreg)                 ; argreg <- first arg
         (cond ((member (d-reg-type argreg) '(FLOAT INT))  ; check type 1st arg
                (let ((result (operator (d-reg-operand argreg) 
                                        (d-reg-operand rgdr))))
                  (set! (d-reg-class pgdr) 'HEAD)
                  (set! (d-reg-type pgdr) 'SYM)
                  (set! (d-reg-operand pgdr) (if result 'TRUE 'FALSE))
                  (transfer pgdr pgdr))
                (transfer (1+ reductions) reductions)
                (transfer (- rgar 2) rgar)      ; pop prim and args off result
                (mwrite rgar pgdr)              ; put result into result graph
                (show (send simulator send-pane 'result 'remove-last)
                      (send simulator send-pane 'result 'remove-last)))
               (else
                 (transfer rgdr pgdr))))
        (else
          (transfer rgdr pgdr)))
  (goto move-backward))

(primitive <  (num->num->bool-function <))
(primitive >  (num->num->bool-function >))
(primitive =  (num->num->bool-function =))
(primitive <=  (num->num->bool-function <=))
(primitive >=  (num->num->bool-function >=))
(primitive <>  (num->num->bool-function <>))





;;; NUM->NUM-FUNCTION
;;; Implements binary functions of type NUM->NUM.
;;; Upon entry, PGAR contains addr of operand
;;;             PGDR contains operator
;;;             RGDR contains operand
;;; Upon exit,
;;;             PGDR contains result.
;;;             RGAR has been decremented once.

(define (num->num-function operator)
  (when (member (d-reg-type rgdr) '(FLOAT INT))  ; check type of arg
        (let ((result (operator (d-reg-operand rgdr))))
          (set! (d-reg-class pgdr) 'HEAD)
          (set! (d-reg-type pgdr) (if (integer? result) 'INT 'FLOAT))
          (set! (d-reg-operand pgdr) result)
          (transfer pgdr pgdr))
        (transfer (1+ reductions) reductions)
        (transfer (-1+ rgar) rgar)         ; pop prim off result
        (mwrite rgar pgdr)                 ; put result into result graph
        (show (send simulator send-pane 'result 'remove-last)))
  (goto move-backward))


(primitive 1+  (num->num-function 1+))
(primitive 1-  (num->num-function -1+))
(primitive 1+  (num->num-function 1+))
(primitive abs  (num->num-function abs))
(primitive minus  (num->num-function minus))





;;; NUM->BOOL-FUNCTION
;;; Implements binary functions of type NUM->BOOLEAN.
;;; Upon entry, PGAR contains addr of operand
;;;             PGDR contains operator
;;;             RGDR contains operand
;;; Upon exit,
;;;             PGDR contains result.
;;;             RGAR has been decremented once.

(define (num->bool-function operator)
  (when (member (d-reg-type rgdr) '(FLOAT INT))  ; check type of arg
        (let ((result (operator (d-reg-operand rgdr))))
          (set! (d-reg-class pgdr) 'HEAD)
          (set! (d-reg-type pgdr) 'SYM)
          (set! (d-reg-operand pgdr) (if result 'TRUE 'FALSE))
          (transfer pgdr pgdr))
        (transfer (1+ reductions) reductions)
        (transfer (-1+ rgar) rgar)         ; pop prim off result
        (mwrite rgar pgdr)                 ; put result into result graph
        (show (send simulator send-pane 'result 'remove-last)))
  (goto move-backward))


(primitive even?  (num->bool-function even?))
(primitive odd?  (num->bool-function odd?))
(primitive negative?  (num->bool-function negative?))
(primitive positive?  (num->bool-function positive?))



;;; IF primitive
;;; The conditional checks to see if its first argument has reduced to either
;;; of the symbols TRUE or FALSE, and reduces either its second or third
;;; argument accordingly.  If the first argument does not reduce to a boolean,
;;; then reduction of both branches is inhibited.

(primitive 
  if
  (transfer (pop-stack) argcount)             ; restore old argcount
  (cond ((and (eq? (d-reg-type rgdr) 'SYM)    ; Boolean conditional, fire IF
              (member (d-reg-operand rgdr) '(TRUE FALSE))
	      (<= 3 argcount))
         (transfer (-1+ pgar) pgar)
         (show (send simulator send-pane 'result 'show-item (-1+ pgar))
               (minor-status "processing true branch"))
         (mread pgar argreg)                  ; ARGREG <- true branch
         (when (member (d-reg-type argreg) '(PTR EP))
               (if (eq? (d-reg-operand rgdr) 'TRUE)
                   (transfer (pop-stack) env) ; restore context for TRUE branch
                   (pop-stack)))              ; throw context away
         (if (eq? (d-reg-operand rgdr) 'TRUE) 
             (transfer argreg pgdr))          ; take true branch upon exit
         (transfer (-1+ pgar) pgar)
         (show (minor-status "processing false branch"))
         (mread pgar argreg)                  ; ARGREG <- false branch
         (when (member (d-reg-type argreg) '(PTR EP))
               (if (eq? (d-reg-operand rgdr) 'FALSE)
                   (transfer (pop-stack) env) ; restore contxt for FALSE branch
                   (pop-stack)))              ; throw context away
         (if (eq? (d-reg-operand rgdr) 'FALSE)
             (transfer argreg pgdr))          ; take false branch upon exit
         (transfer (- rgar 4) rgar)           ; pop IF construct off graph
         (show (send simulator send-pane 'result 'remove-last)
               (send simulator send-pane 'result 'remove-last)
               (send simulator send-pane 'result 'remove-last)
               (send simulator send-pane 'result 'remove-last))
         (transfer (- argcount 3) argcount)
         (mread rgar rgdr)
         (transfer 'PROBLEM mode)            ; begin moving forward again
         (set! (d-reg-class pgdr) 'HEAD)
         (transfer pgdr pgdr)
         (show (minor-status "execute conditional branch"))
         (cond ((eq? (d-reg-type pgdr) 'PTR)
                (transfer (d-reg-operand pgdr) pgar)
                (show (send simulator send-pane 'problem
                            'display-items pgar (next-head pgar)))
                (goto next-instruction))
               (else
                 (goto execute-instruction))))
        (else
          (transfer reductions inhibit1)      ; inhibit the reduction of args
          (transfer red-limit reductions)
          (transfer (- pgar (min 3 argcount)) inhibit)
          (transfer (-1+ pgar) pgar)
          (goto next-instruction))))


;;; Y
;;; Primitive recursion operator.  This is a copying version, not a
;;; knot-tying version.  Transforms (Y f) into (f (Y f)).

(primitive Y
           (transfer (1+ reductions) reductions)
           (set! (d-reg-class rgdr) 'HEAD)       ; make arg a head instruction
           (transfer rgdr pgdr)                  ; PGDR <- arg
           (set! (d-reg-class rgdr) 'AP)         ; RGDR <- pointer to (Y f)
           (set! (d-reg-type rgdr) 'PTR)
           (set! (d-reg-operand rgdr) (-1+ pgar))
           (push-stack env)                      ; env context for (Y f)
           (mwrite rgar rgdr)                    ; write (Y f) to result graph
           (goto execute-instruction))           ; execute f


;;; AND
;;; Boolean conjunction.  The AND is an n-ary operator which fires after
;;; each of its arguments are evaluated.  If the value of any argument is
;;; FALSE, the conjunction returns FALSE, otherwise it returns TRUE.

;;; 26 June -- modified to undo reset list upon failure

(define reset-list)

(primitive 
  AND
  (cond ((eq? mode 'problem)         
         (when (<= 1 argcount)
               (set-primreg 1)
               (writeln "reset-list: " reset-list)
               (push-aux reset-list))
         (goto change-directions))
        (else
          (writeln "reset-list: " reset-list)
          (cond ((and (eq? (d-reg-type rgdr) 'SYM)
                      (eq? (d-reg-operand rgdr) 'FALSE))
                 (set! (d-reg-class pgdr) 'HEAD)  ; put FALSE result in PGDR
                 (set! (d-reg-type pgdr) 'SYM)
                 (set! (d-reg-operand pgdr) 'FALSE)
                 (transfer pgdr pgdr)
                 (transfer (pop-aux) temp) ; old reset list
                 (show (wait "undoing unifications"))
                 (let loop ()              ; undo unifications within AND
                   (when (not (eq? reset-list temp))
                         (let* ((val (pop-reset))
                                (addr (pop-reset)))
                           (mwrite addr val)
                           (loop))))
                 (show (wait "popping off arguments"))
                 (let loop ()                  ; find end of args
                   (transfer (-1+ rgar) rgar)  ;   pop previous arg off graph
                   (show (send simulator send-pane 'result 'remove-last))
                   (transfer (-1+ pgar) pgar)   ;   read next arg
                   (mread pgar rgdr)           
                   (cond ((member (d-reg-class rgdr) '(HEAD CONTROL))
                          (transfer (1+ pgar) pgar)      ; let move-backward
                          (goto move-backward))          ;   handle it
                         (else 
                           (if (member (d-reg-type rgdr) '(PTR EP))
                               (pop-stack))
                           (loop)))))
                 (else
                   (mwrite pgar pgdr)              ; overwrite operand with AND
                   (set! (d-reg-class primreg) #T) ; reset primreg
                   (set! (d-reg-type primreg) 1)
                   (set! (d-reg-operand primreg) 1)
                   (transfer primreg primreg)
		   (set! (d-reg-operand pgdr) 'TRUE) ; set partial result TRUE
                   (set! (d-reg-type pgdr) 'SYM)
                   (transfer pgdr pgdr)
                   (transfer (-1+ rgar) rgar)       ; pop old AND off graph
                   (show (send simulator send-pane 'result 'remove-last))
                   (goto move-backward))))))



;;; OR
;;; Boolean disjunction.  The OR is an n-ary operator which fires after
;;; each of its arguments are evaluated.  If the value of any argument is
;;; TRUE, the disjunction returns TRUE, otherwise it returns FALSE.

(primitive OR
           (cond ((and (eq? (d-reg-type rgdr) 'SYM)
                       (eq? (d-reg-operand rgdr) 'TRUE))
                  (set! (d-reg-class pgdr) 'HEAD)  ; put TRUE result in PGDR
                  (set! (d-reg-type pgdr) 'SYM)
                  (set! (d-reg-operand pgdr) 'TRUE)
                  (transfer pgdr pgdr)
                  (let loop ()                  ; find end of args
                    (transfer (-1+ rgar) rgar)  ;   pop previous arg off graph
                    (show (send simulator send-pane 'result 'remove-last))
                    (transfer (-1+ pgar) pgar)   ;   read next arg
                    (mread pgar rgdr)           
                    (cond ((member (d-reg-class rgdr) '(HEAD CONTROL))
                           (transfer (1+ pgar) pgar)      ; let move-backward
                           (goto move-backward))          ;   handle it
                          (else 
                            (if (member (d-reg-type rgdr) '(PTR EP))
                                (pop-stack))
                            (loop)))))
                 (else
                   (mwrite pgar pgdr)              ; overwrite operand with OR
                   (set! (d-reg-class primreg) #T) ; reset primreg
                   (set! (d-reg-type primreg) 1)
                   (set! (d-reg-operand primreg) 1)
                   (transfer primreg primreg)
		   (set! (d-reg-operand pgdr) 'FALSE) ;set partial result FALSE
                   (set! (d-reg-type pgdr) 'SYM)
                   (transfer pgdr pgdr)
                   (transfer (-1+ rgar) rgar)       ; pop old OR off graph
                   (show (send simulator send-pane 'result 'remove-last))
                   (goto move-backward))))



;;; PACK
;;; Structure creation primitive, with lazy semantics.  The general form is:
;;;    PACK tag n a1...aN
;;; where TAG is the name of the structure type, N is the size of the
;;; structure, and A1...An are the elements of the structure.

(primitive PACK
           (mread (- pgar 2) envdr)                    
           (transfer (d-reg-operand envdr) temp)        ; TEMP <- n
           (cond ((and (>= argcount (+ 2 temp))         ; if enough args
                       (not (= reductions red-limit)))
                  (transfer rgdr pgdr)                  ; PGDR <- tag
                  (transfer temp scratch)               ; SCRATCH <- n
                  (transfer (- rgar 2) rgar)            ; pop tag & size off
                  (show (send simulator send-pane 'result 'remove-last)
                        (send simulator send-pane 'result 'remove-last))
                  (mread rgar rgdr)                     ; prime for push-bind.
                  (let loop ()                          ; push args into env
                    (when (not (zero? temp)) 
                          (push-binding #F)
                          (transfer (-1+ temp) temp)
                          (loop)))
                  (set! (d-reg-class rgdr) 'HEAD)       ; push size
                  (set! (d-reg-type rgdr) 'INT)
                  (set! (d-reg-operand rgdr) scratch)
                  (transfer rgdr rgdr)
                  (push-env rgdr #F)
                  (push-env pgdr #F)                       ; push tag
                  (set! (d-reg-class pgdr) 'HEAD)       ; create STRUCT pointer
                  (set! (d-reg-type pgdr) 'STRUCT)
                  (set! (d-reg-operand pgdr) envstack)
                  (transfer (1+ reductions) reductions)
                  (goto change-directions))
                 (else
                   (transfer reductions inhibit1)       ; inhibit reduction
                   (transfer red-limit reductions)
                   (transfer (- rgar argcount) inhibit)
                   (goto change-directions))))


;;; SELECT
;;; Structure accessing function.  The general form is
;;;    SELECT tag index struct
;;; where TAG is the type of the structure, INDEX is the element to be
;;; accessed, and STRUCT is the structure to be accessed.

(primitive SELECT
           (when (and (>= argcount 3)
                      (not (= reductions red-limit)))
                 (set! (d-reg-class primreg) #T)   ; set to fire in 3 args
                 (set! (d-reg-type primreg) 3)
                 (set! (d-reg-operand primreg) 3)
                 (set! (d-reg-operand pgdr) 'SELECT1)) ; accessing primitive
           (goto change-directions))

(primitive 
  SELECT1
  (let ((failure-action 
          (lambda ()
            (transfer rgdr pgdr)
            (set! (d-reg-class rgdr) 'HEAD)
            (set! (d-reg-type rgdr) 'PRIM)
            (set! (d-reg-operand rgdr) 'SELECT)
            (mwrite (+ 3 pgar) rgdr)
            (goto move-backward))))
    (cond ((eq? (d-reg-type rgdr) 'STRUCT)
           (mread (+ pgar 2) pgdr)              ; PGAR <- type
           (mread (d-reg-operand rgdr) envdr)   ; ENVDR <- struct type
           (cond ((eq? (d-reg-operand envdr)    ; if type is correct
                       (d-reg-operand pgdr))
                  (mread (+ pgar 1) pgdr)       ;   PGDR <- index
                  (mread (1+ (d-reg-operand rgdr)) envdr) ; size
                  (cond ((<= (d-reg-operand pgdr)  ; index < size
                            (d-reg-operand envdr))
                         (transfer (1+ reductions) reductions)
                         (transfer (- rgar 4) rgar)
                         (show (send simulator send-pane 'result 'remove-last)
                               (send simulator send-pane 'result 'remove-last)
                               (send simulator send-pane 'result 'remove-last)
                               (send simulator send-pane 'result 'remove-last))
                         (transfer (- (d-reg-operand envdr)
                                      (d-reg-operand pgdr))
                                   scratch)
                         (transfer (d-reg-operand rgdr) temp)
                         (transfer (+ 2 temp) temp)
                         (transfer 'PROBLEM mode)
                         (lookup-loop)
                         (var-head-action))
                        (else
                          (failure-action))))
                 (else
                   (failure-action))))
          (else
            (failure-action)))))

