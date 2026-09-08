;;; Attempt at adding logic programming to red2

(set! *primitives* (cons 'try *primitives*))



(define (inhibit-args number)
  (transfer reductions inhibit1)
  (transfer red-limit reductions)
  (transfer (- pgar number) inhibit))
  
(define (set-primreg arity)
  (set! (d-reg-class primreg) #T)
  (set! (d-reg-type primreg) arity)
  (set! (d-reg-operand primreg) arity))

(primitive 
  try
  (cond ((eq? mode 'problem)
         (cond ((and (<= 2 argcount) (not (= reductions red-limit)))
                (push-reset 'mark)
                (set-primreg 1)
                (goto change-directions))
               (else
                 (inhibit-args (min argcount 2))
                 (goto change-directions))))
        (else
          (cond ((eq? (d-reg-operand rgdr) 'TRUE)
                 (transfer (-1+ pgar) pgar)
                 (mread pgar argreg)
                 (pop-stack) ; discard context
                 (push-reset env)
                 (push-reset (d-reg-operand argreg)) ; push closure
                 (transfer (- rgar 2) rgar)   ; pop TRY off graph
                 (show (send simulator send-pane 'result 'remove-last)
                       (send simulator send-pane 'result 'remove-last))
                 (transfer rgdr pgdr)
                 (set! (d-reg-class pgdr) 'HEAD)
                 (mwrite rgar pgdr)
                 (show (send simulator send-pane 'result 'refresh-item rgar))
                 (goto move-backward))
                (else
                  (let loop ()   ; reset any variables set by unification
                    (cond ((not (eq? (car reset-list) 'MARK))
                           (let ((addr (pop-reset))
                                 (value (pop-reset)))
                             (mwrite addr value))  ; reset value
                           (loop))
                          (else (pop-reset))))  ; remove MARK
                  (transfer (-1+ pgar) pgar)
                  ;; I think this may be a potential problem area,
                  ;; because if a symbol is used as the second arg to
                  ;; try, a proper env context will not be saved
                  ;; then if the symbol expands in the head, a proper
                  ;; context will not exist.
                  (mread pgar pgdr)
                  (when (member (d-reg-type pgdr) '(PTR EP))
                        (transfer (pop-stack) temp)          ; restore context
                        (when (not (= temp env))
                              (set! (d-reg-class envdr) nil)
                              (set! (d-reg-type envdr) 'MARKER)
                              (set! (d-reg-operand envdr) temp) ; proper context
                              (transfer envdr envdr)
                              (push-env envdr #T))
                        (transfer temp env))
                  (transfer (d-reg-operand pgdr) pgar)
                  (transfer 'PROBLEM mode)            ; move forward
                  (transfer (- rgar 3) rgar)          ; pop TRY off graph
                  (show (send simulator send-pane 'result 'remove-last)
                        (send simulator send-pane 'result 'remove-last)
                        (send simulator send-pane 'result 'remove-last)
                        (send simulator send-pane 'problem 'display-items
                              pgar (next-head pgar)))
                  (goto next-instruction))))))

