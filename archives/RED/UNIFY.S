;;; Unification primitive
;;; 22 June 1989, Mike Hilton


;;; UNIFY
;;; Tests two normal forms to see if they unify.  If so, a most general
;;; unifier has been created in the environment, and the TRAIL has been
;;; augmented with a reset list for the unification.
;;; Upon entry, PGAR has addr of second operand
;;;             RGDR contains second operand


(define depth 0)

(define env1 0)  ; environment for first arg
(define env2 0)  ; environment for second arg

(define aux nil) ; auxilliary stack
(define (push-aux x) (set! aux (cons x aux)))
(define (pop-aux) (begin0 (car aux) (set! aux (cdr aux))))

(define reset-list nil) ; reset list
(define (push-reset x) (set! reset-list (cons x reset-list)))
(define (pop-reset) (begin0 (car reset-list) 
                            (set! reset-list (cdr reset-list))))

(define oldvalue (make-d-reg))

(define (write-inst class type op)
  (transfer (1+ rgar) rgar)
  (mwrite rgar (make-d-reg 'class class 'type type 'operand op))
  (show (send simulator send-pane 'result 'add-last)))

(primitive 
  unify
  (cond ((eq? mode 'PROBLEM)
         (when (<= 2 argcount)
               (set! (d-reg-class primreg) #T)
               (set! (d-reg-type primreg) 2)
               (set! (d-reg-operand primreg) 2)
               (transfer primreg primreg)
               (push-aux env1)
               (push-aux env2)
               (let* ((temp1 (pop-stack))
                      (temp2 (pop-stack)))
                 (push-stack temp2)
                 (push-stack temp1)
                 (push-aux (if (integer? temp2) temp2 env))
                 (push-aux (if (integer? temp1) temp1 env))))
         (goto change-directions))
        (else
          (transfer (pop-aux) env2)
          (transfer (pop-aux) env1)
          (mread (1+ pgar) argreg)  ; ARGREG <- first operand
          (cond ((equal? rgdr argreg)
                 (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'TRUE)
                           pgdr)
                 (goto unify-finish))
                ((and (type=? 'PTR rgdr) (type=? 'PTR argreg))
                 (push-stack reset-list) ; reset list
                 (push-stack depth)
                 (push-stack pgar)  ; address where result goes
                 (transfer (d-reg-operand rgdr) temp)
                 (transfer (d-reg-operand argreg) pgar)
                 (transfer 0 depth)
                 (transfer 0 argcount) ; counts lambdas passed over
                 (push-stack (-1+ temp)) ; marks end of traversal
                 (goto unify-down))
                ((or (type=? 'VAR rgdr) (type=? 'VAR argreg))
                 (transfer argreg pgdr)
                 (transfer (1+ pgar) temp)
                 (push-stack reset-list)
                 (push-stack depth)
                 (push-stack pgar)
                 (transfer 0 depth)
                 (transfer 0 argcount)
                 (push-stack pgar)
                 (goto unify-vars))
                (else
                  (transfer 
                    (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'FALSE)
                    pgdr)
                  (goto unify-finish))))))

(define (unify-succeed)
  (show (minor-status "unify-succeed")
        (send simulator unhighlight-all))
  (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'TRUE) pgdr)
  (transfer (pop-stack) pgar)
  (transfer (pop-stack) depth)
  (pop-stack) ; reset list
  (goto unify-finish))

(define (unify-finish)
  (transfer (1+ reductions) reductions)
  (mwrite pgar pgdr)
  (transfer (pop-aux) env2)
  (transfer (pop-aux) env1)
  (transfer pgar rgar)
  (show (send simulator send-pane 'result 'display-items
              (1+ result-addr) rgar)
        (send simulator send-pane 'result 'show-item rgar))
  (goto move-backward))

(define (unify-fail)
  (show (minor-status "unify-fail")
        (send simulator unhighlight-all))
  (let loop ()
    (when (not (zero? depth))
          (transfer (-1+ depth) depth)
          (pop-stack)
          (pop-stack)
          (loop)))
  (pop-stack)
  (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'FALSE) pgdr)
  (transfer (pop-stack) pgar)
  (transfer (pop-stack) depth)
  (transfer (pop-stack) temp) ; old reset list
  (let loop ()
    (when (not (eq? reset-list temp))
          (let* ((val (pop-reset))
                 (addr (pop-reset)))
            (mwrite addr val)
            (loop))))
  (goto unify-finish))




;;; unify-down walks down the spine of two graphs and tests them for
;;; unifiability.  TEMP and PGAR are the addresses of the graphs.  



(define (unify-down)
  (show (wait "unify-down")
        (send simulator unhighlight-all))
  (mread pgar pgdr)
  (mread temp rgdr)
  (cond ((and (class=? 'HEAD pgdr) (class=? 'HEAD rgdr))
         (cond ((or (type=? 'VAR pgdr) (type=? 'VAR rgdr))
                (goto unify-vars))
               ((equal? pgdr rgdr)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               ((and (type=? 'STRUCT pgdr) (type=? 'STRUCT rgdr))
                (push-stack (-1+ temp))
                (push-stack (-1+ pgar))
                (transfer (1+ depth) depth)
                (goto unify-struct))
               (else
                 (goto unify-fail))))
        ((or (class=? 'HEAD pgdr) (class=? 'HEAD rgdr))
         (goto unify-fail))
        ((and (type=? 'NAMED pgdr) (type=? 'NAMED rgdr))
         (transfer (1+ argcount) argcount)
         (transfer (1+ temp) temp)
         (transfer (1+ pgar) pgar)
         (goto unify-down))
        ((and (type=? 'VAR pgdr) (type=? 'VAR rgdr))
         (cond ((or (and (< (d-reg-operand pgdr) argcount)
                         (< (d-reg-operand rgdr) argcount))
                    (and (>= (d-reg-operand pgdr) argcount)
                         (>= (d-reg-operand rgdr) argcount)))
                (transfer (1+ temp) temp)
                (transfer (1+ pgar) pgar)
                (goto unify-down))
               (else
                 (goto unify-fail))))
        ((or (and (type=? 'VAR pgdr) (>= (d-reg-operand pgdr) argcount))
             (and (type=? 'VAR rgdr) (>= (d-reg-operand rgdr) argcount)))
         (transfer (1+ temp) temp)
         (transfer (1+ pgar) pgar)
         (goto unify-down))
        ((or (equal? pgdr rgdr)
             (and (type=? 'PTR pgdr) (type=? 'PTR rgdr)))
         (transfer (1+ temp) temp)
         (transfer (1+ pgar) pgar)
         (goto unify-down))
        (else
          (goto unify-fail))))

;;; unify-up coordinates the checking of subgraphs for unifiability.
;;; The number of subgraphs to check is in SCRATCH; the addresses for
;;; these graphs have been pushed onto the stack. 

(define (unify-up)
  (show (wait "unify-up")
        (send simulator unhighlight-all))
  (mread pgar pgdr)
  (mread temp rgdr)
  (transfer (pop-stack) scratch)  ; finishing address
  (if (= temp scratch)
      (goto unify-succeed)
      (cond ((class=? 'HEAD pgdr)
             (transfer scratch temp)
             (transfer (pop-stack) pgar)
             (transfer (-1+ depth) depth)
             (goto unify-up))
            ((and (type=? 'NAMED pgdr) (type=? 'NAMED rgdr))
             (push-stack scratch)
             (transfer (-1+ argcount) argcount)
             (transfer (-1+ temp) temp)
             (transfer (-1+ pgar) pgar)
             (goto unify-up))
            ((and (type=? 'VAR pgdr) (type=? 'VAR rgdr)
                  (< (d-reg-operand pgdr) argcount)
                  (< (d-reg-operand rgdr) argcount))
             (push-stack scratch)
             (if (not (equal? pgdr rgdr))
                 (goto unify-fail)
                 (begin
                   (transfer (-1+ temp) temp)
                   (transfer (-1+ pgar) pgar)
                   (goto unify-up))))
            ((or (type=? 'VAR pgdr) (type=? 'VAR rgdr))
             (push-stack scratch)
             (goto unify-vars))
            ((type=? 'PTR pgdr)
             (push-stack scratch)
             (push-stack (-1+ pgar))
             (push-stack (-1+ temp))
             (transfer (1+ depth) depth)
             (transfer (d-reg-operand pgdr) pgar)
             (transfer (d-reg-operand rgdr) temp)
             (goto unify-down))
            ((equal? pgdr rgdr)
             (push-stack scratch)
             (transfer (-1+ temp) temp)
             (transfer (-1+ pgar) pgar)
             (goto unify-up))
            (else
              (push-stack scratch)
              (goto unify-fail))
            )))





(define (unify-vars)
  (show (wait "unify-vars")
        (send simulator unhighlight-all))
  (cond ((and (type=? 'VAR pgdr) (type=? 'VAR rgdr))
         ;; look up the value of both vars
         (push-stack temp)   ; addr of var2 in graph
         (transfer (- (d-reg-operand pgdr) argcount) scratch)
         (transfer env1 temp)
         (lookup-loop)
         (let loop ()
           (mread temp pgdr) ; value of var1
           (when (type=? 'EP pgdr)
                 (transfer (d-reg-operand pgdr) temp)
                 (loop)))
         (push-stack temp) ; save addr of var1 for a moment
         (transfer (- (d-reg-operand rgdr) argcount) scratch)
         (transfer env2 temp) ; temp <- addr of var2
         (lookup-loop)
         (let loop ()
           (mread temp rgdr) ; value of var2
           (when (type=? 'EP rgdr)
                 (transfer (d-reg-operand rgdr) temp)
                 (loop)))
         (transfer (pop-stack) scratch)  ; scratch <- addr of var1
         (cond ((= temp scratch)
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               ((and (type=? 'VAR rgdr) (type=? 'VAR pgdr))
                ;; make younger var point to older var
                (cond ((> scratch temp) ; pgdr older than rgdr
                       (set! oldvalue (make-d-reg))
                       (transfer rgdr oldvalue)
                       (mwrite temp
                               (make-d-reg 'type 'EP 'operand scratch))
                       (push-reset temp)
                       (push-reset oldvalue))
                      (else
                        (set! oldvalue (make-d-reg))
                        (transfer pgdr oldvalue)
                        (mwrite scratch
                                (make-d-reg 'type 'EP 'operand temp))
                        (push-reset scratch)
                        (push-reset oldvalue)))
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               ((type=? 'VAR pgdr)
                (when (not (and (type=? 'EP rgdr) 
                                (= scratch (d-reg-operand rgdr))))
                      ;; make var1 point to value of var2
                      (mwrite scratch (make-d-reg 'type 'EP 'operand temp))
                      (set! oldvalue (make-d-reg))
                      (transfer pgdr oldvalue)
                      (push-reset scratch)
                      (push-reset oldvalue))
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               ((type=? 'VAR rgdr)
                (when (not (and (type=? 'EP pgdr) 
                                (= temp (d-reg-operand pgdr))))
                      ;; make var2 point to value of var1
                      (mwrite temp (make-d-reg 'type 'EP 'operand scratch))
                      (set! oldvalue (make-d-reg))
                      (transfer rgdr oldvalue)
                      (push-reset temp)
                      (push-reset oldvalue))
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               (else
                 ;; continue unifying the two values
                 (transfer (pop-stack) temp)
                 (cond ((and (type=? 'PTR pgdr) (type=? 'PTR rgdr))
                        (set! (d-reg-class pgdr) 'AP)
                        (set! (d-reg-class rgdr) 'AP)
                        (mwrite pgar pgdr)
                        (mwrite temp rgdr)
                        (goto unify-up))
                       ((and (eq? (d-reg-type pgdr) (d-reg-type rgdr))
                             (eq? (d-reg-operand pgdr) (d-reg-operand rgdr)))
                        (transfer (-1+ temp) temp)
                        (transfer (-1+ pgar) pgar)
                        (goto unify-up))
                       (else 
                         (goto unify-fail))))))
        (else
          (goto unify-vars-1))))

(define (unify-vars-1)
  (cond ((type=? 'VAR pgdr)
         ;; look up the value and unify
         (push-stack temp) ; save addr2
         (transfer (- (d-reg-operand pgdr) argcount) scratch)
         (transfer env1 temp)
         (lookup-loop)  ; temp <- var address
         (let loop ()
           (mread temp pgdr) ; pgdr <- var value
           (when (type=? 'EP pgdr)
                 (transfer (d-reg-operand pgdr) temp)
                 (loop)))
         (cond ((type=? 'VAR pgdr)
                (mwrite temp rgdr) ; we may need to put a closure here if PTR
                (set! oldvalue (make-d-reg))
                (transfer pgdr oldvalue)
                (push-reset temp)
                (push-reset oldvalue)
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               (else
                 (transfer (pop-stack) temp)
                 (set! (d-reg-class pgdr) 'AP)
                 (mwrite pgar pgdr)
                 (goto unify-up))))
        ((type=? 'VAR rgdr)
         ;; look up the value and unify
         (push-stack temp) ; save addr2
         (transfer (- (d-reg-operand rgdr) argcount) scratch)
         (transfer env2 temp)
         (lookup-loop)  ; temp <- var address
         (let loop ()
           (mread temp rgdr) ; rgdr <- var value
           (when (type=? 'EP rgdr)
                 (transfer (d-reg-operand rgdr) temp)
                 (loop)))
         (cond ((type=? 'VAR rgdr)
                (mwrite temp pgdr) ; we may need to put a closure here if PTR
                (set! oldvalue (make-d-reg))
                (transfer rgdr oldvalue)
                (push-reset temp)
                (push-reset oldvalue)
                (transfer (pop-stack) temp)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto unify-up))
               (else
                 (transfer (pop-stack) temp)
                 (set! (d-reg-class rgdr) 'AP)
                 (mwrite temp rgdr)
                 (goto unify-up))))
        ))

;;; Check two structures to see if they are unifiable.  The
;;; elements of the structure will need to be forced (reduced),
;;; before they are tested.

(define (unify-struct)
  (show (wait) (minor-status "unify-struct"))
  (transfer (d-reg-operand pgdr) pgar)
  (transfer (d-reg-operand rgdr) temp)
  (mread pgar pgdr)      ; check the tags to see if they are identical
  (mread temp rgdr)
  (if (not (equal? pgdr rgdr))
      (goto unify-fail)
      (begin
        (mread (1+ pgar) pgdr) ; check the sizes to see if they are identical
        (mread (1+ temp) rgdr)
        (if (not (equal? pgdr rgdr))
            (goto unify-fail)
            (begin
              (push-stack (+ pgar 2))    ; addr of structure A
              (push-stack (+ temp 2))    ; addr of structure B
              (push-stack (d-reg-operand pgdr))  ; size of structures
              (set! (d-reg-operand rgdr) 'TRUE)
              (goto unify-s-loop))))))

;;; loops through the elements of a structure and tests for unifiability.

(define (unify-s-loop)
  (show (wait)
        (minor-status "unify-s-loop")
        (send simulator unhighlight-all))
  (transfer (pop-stack) scratch)  ; size of structures
  (transfer (pop-stack) temp) ; addr of structure B
  (transfer (pop-stack) pgar) ; addr of structure A
  (cond ((not (eq? (d-reg-operand rgdr) 'TRUE))
         (goto unify-fail))
        ((zero? scratch)
         (transfer (pop-stack) pgar)
         (transfer (pop-stack) temp)
         (transfer (-1+ depth) depth)
         (goto unify-up))
        (else
          (transfer (-1+ scratch) scratch)
          (push-stack pgar)
          (push-stack temp)
          (push-stack scratch)
          ;; create a graph to reduce args & check for equality
          (lookup-loop)
          (write-inst 'AP 'EP temp)
          (transfer (pop-stack) scratch)
          (push-stack scratch)
          (transfer pgar temp)
          (lookup-loop)
          (write-inst 'AP 'EP temp)
          (write-inst 'HEAD 'PRIM 'UNIFY)
          (transfer (- rgar 2) pgar)
          (write-inst 'CONTROL 'JUMP 'unify-s-loop)
          (transfer 'problem mode)
          (show
            (send simulator unhighlight-all)
            (send simulator send-pane 'problem 'display-items
                  pgar (next-head pgar)))
          (goto next-instruction))))
