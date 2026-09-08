;;; INSTRUCTION SET IMPLEMENTATION FOR THE LAMBDA PROCESSOR
;;; Includes hooks for primitives
;;; Mike Hilton, 12 May 1989


;;;; HELPER ROUTINES


;;; CHANGE-DIRECTIONS
;;; Change the direction of graph traversal from moving forward towards
;;; the head to moving backwards towards the root.

(define (change-directions)
  (show (minor-status "CHANGE-DIRECTIONS"))
  (transfer pgdr rgdr)
  (transfer (1+ rgar) rgar)
  (transfer rgar pgar)
  (mwrite rgar rgdr)
  (transfer 'RESULT mode)
  (show (send simulator send-pane 'result 'scroll-region-down))
  (goto move-backward))


;;; EXECUTE-INSTRUCTION
;;; Instruction decode unit.  The contents of the PGDR are decoded to 
;;; determine the proper microinstruction
;;; sequence to execute.  The decoding combines information about the
;;; instruction class and type, and the current MODE of the reducer.

(define (execute-instruction)
  (show (minor-status "EXECUTE-INSTRUCTION"))
  (goto (getprop (d-reg-type pgdr) 
                 (if (eq? 'HEAD (d-reg-class pgdr))
                     'HEAD
                     mode))))



;;; EXECUTE-PRIMITIVE
;;; If further reductions are allowed, a primitive operation is attempted.

(define (execute-primitive)
  (show (minor-status "EXECUTE-PRIMITIVE"))
  (set! (d-reg-class primreg) #F)
  (transfer primreg primreg)
  (cond ((not (= reductions red-limit))
         (mread (+ pgar (d-reg-type primreg)) pgdr)
         (goto (getprop (d-reg-operand pgdr) 'PRIMITIVE)))
        (else
          (goto move-backward))))


;;; LOOKUP
;;; Looks up a variable reference in the environment.  The variable index
;;; to look up is located in the PGDR operand slot.

(define (lookup)
  (show (minor-status "LOOKUP"))
  (transfer (d-reg-operand pgdr) scratch)
  (transfer env temp)
  (lookup-loop))
(define lrefs 0)
(define (lookup-loop)
  (let loop ()
(set! lrefs (1+ lrefs))		
    (mread temp envdr)
    (cond ((eq? (d-reg-type envdr) 'MARKER)      ; jump over env marker
           (transfer (d-reg-operand envdr) temp)
           (loop))
          ((zero? scratch)                       ; found it!
           temp)
          ((eq? (d-reg-class envdr) 'CLOSURE)    ; move over closure
           (transfer (+ temp 2) temp)
           (transfer (-1+ scratch) scratch)
           (loop))
          (else                                  ; else move over entry
            (transfer (-1+ scratch) scratch)
            (transfer (1+ temp) temp)
            (loop)))))



;;; MOVE-BACKWARD
;;; Moves one instruction backwards towards the root of the expression.
;;; It is necessary to check if this is the completion of a subexpression,
;;; and if so, patch in the result and continue up the parent.
;;;
;;; This is also the place to handle sharing.  Currently, only atomic values
;;; are shared.
;;;
;;; Argument inhibition:  if arguments are to be inhibited, the address
;;; above the last inhibited arg is stored in the register INHIBIT, the
;;; current reduction count is stored in INHIBIT1, and the REDUCTIONS
;;; register gets the value in REDLIMIT.  When the current address is
;;; equal to the value in INHIBIT, restore the proper reduction count.

(define (move-backward)
  (show (wait)
        (send simulator unhighlight-all)
        (minor-status "MOVE-BACKWARD"))
  (transfer pgdr rgdr)
  (if (and (d-reg-class primreg) (zero? (d-reg-operand primreg)))
      (goto execute-primitive)                     ; fire a primitive
      (begin
        (when (d-reg-class primreg) 
              (set! (d-reg-operand primreg) (-1+ (d-reg-operand primreg)))
              (transfer primreg primreg))
        (transfer (-1+ pgar) pgar)                 ; addr of next instruction
        (show (send simulator show-item pgar))
        (when (= pgar inhibit)                     ; end of argument inhibition
              (transfer inhibit1 reductions))      ;   restore reduction count
        (mread pgar pgdr)                          ; pgdr <- next instruction
        (if (not (eq? (d-reg-class pgdr) 'HEAD))   ; if not a HEAD instruction
            (goto execute-instruction)             ;    execute
            (begin                                 ; else at end of subgraph
	      (show (send simulator send-pane 'result 'show-item temp))
              (transfer (pop-stack) primreg)       ;    pop primreg
              (transfer (pop-stack) temp)          ;    pop return address
              (if (eq? (d-reg-class rgdr) 'HEAD)   ;    if subgraph is one word
                  (begin
                    (mread temp pgdr)              ;       check if sharable
                    (when (eq? (d-reg-type pgdr) 'EP)      ; share
                          (set! (d-reg-class rgdr)'CLOSURE)
                          (mwrite (d-reg-operand pgdr) rgdr)) 
                    (set! (d-reg-class rgdr) 'AP)  ;       make result an AP
                    (mwrite temp rgdr)             ;       write it into spine
                    (transfer (-1+ rgar) rgar)     ;       pop off result graph
                    (show (send simulator send-pane 'result 'remove-last)))
                  (begin                           ;    else
                    (set! (d-reg-operand rgdr)     ;       point to the result
                          (1+ pgar))
                    (set! (d-reg-class rgdr) 'AP)
                    (set! (d-reg-type rgdr) 'PTR)
                    (transfer rgdr rgdr)
                    (mwrite temp rgdr)))           ;       write ptr into spine
              (transfer temp pgar)                 ; resume traversing parent
              (transfer rgdr pgdr)
              (show (send simulator send-pane 'result 'show-item pgar)
                    (wait)
                    (send simulator unhighlight-all))
              (goto move-backward))))))


;;; MOVE-FORWARD
;;; Moves one instruction down towards the head of the spine.

(define (move-forward)
  (transfer (1+ pgar) pgar)
  (transfer (1+ rgar) rgar)
  (transfer pgdr rgdr)
  (mwrite rgar rgdr)
  (show (send simulator send-pane 'result 'scroll-region-down)
        (wait)
        (send simulator unhighlight-all)
        (minor-status "MOVE-FORWARD"))
  (goto next-instruction))


;;; NEXT-INSTRUCTION
;;; Instruction fetch.  The instruction at the PGAR is read and executed. 

(define (next-instruction)
  (show (minor-status "NEXT-INSTRUCTION")
        (send simulator show-item pgar))
  (mread pgar pgdr)
  (goto execute-instruction))


;;; PUSH-BINDING
;;; Push a binding value into the environment.

(define (push-binding . inc-env?)
  (transfer (-1+ argcount) argcount)
  (case (d-reg-type rgdr)
    (VAR                         ;    if argument is a variable
      (set! (d-reg-operand rgdr) ;       calculate proper binding index
            (- binding-offset (d-reg-operand rgdr)))
      (push-env rgdr inc-env?))  ;       put variable into environment
    (PTR                         ;    else if argument is a pointer
      (set! (d-reg-operand envdr);       build a closure
            (pop-stack))         ;       get env information
      (set! (d-reg-type envdr) 'ENV)
      (set! (d-reg-class envdr) 'CLOSURE)
      (transfer envdr envdr)
      (push-env envdr inc-env?)  ;       put env part of closure
      (set! (d-reg-class rgdr) 'CLOSURE)
      (push-env rgdr inc-env?))  ;       put ptr part of closure
    (EP                          ;    else if argument is an envptr
      (pop-stack)                ;       discard env information
      (push-env rgdr inc-env?))  ;       put envptr into environment
    (else                        ;    else if argument is immediate data
      (push-env rgdr inc-env?))  ;       put data into environment
    )
  (transfer (-1+ rgar) rgar)     ;  pop used argument off result graph
  (show (send simulator send-pane 'result 'remove-last))
  (mread rgar rgdr)              ;  get next argument from result graph
  )


;;; PUSH-UNBOUND-VARS
;;; Push the number of unbound variables indicated by the operand of PGDR
;;; in the environment.

(define (push-unbound-vars)
  (show (minor-status "PUSH-UNBOUND-VARS"))
  (set! (d-reg-type envdr) 'VAR)
  (set! (d-reg-class envdr) nil)
  (let loop ()
    (when (not (zero? scratch))
          (transfer (1+ binding-offset) binding-offset)
          (set! (d-reg-operand envdr) binding-offset)
          (push-env envdr #T)
          (transfer (-1+ scratch) scratch)
          (loop))))





;;;; INSTRUCTION SET


;;; EP
;;; Environment pointer.  Points to a closure in the environment.

(instruction 
  ep result
  (transfer (pop-stack) env)             ; get proper binding context
  (show (send simulator send-pane 'env 'scroll-to-item env))
  (transfer (d-reg-operand pgdr) temp)   ; TEMP <- address of environment entry
  (show (send simulator show-item temp))
  (mread temp pgdr)                      ; PGDR <- environment entry
  (case (d-reg-type pgdr)
    (PTR                                 ; if environment entry is a pointer
      (push-stack pgar)                  ;    push return address onto stack
      (push-stack primreg)               ;    save primreg on stack
      (transfer 0 argcount)              ;    argcount <- 0
      (set! (d-reg-class primreg) #F)    ;    turn off primreg
      (transfer primreg primreg)
      (set! (d-reg-class pgdr) 'HEAD)
      (transfer 'PROBLEM mode)
      (mread (1+ temp) envdr)            ; ENVDR <- env part of closure
      (push-stack (d-reg-operand envdr)) ; push env part onto stack
      (show (transfer pgdr pgdr) 
            (wait) 
            (send simulator unhighlight-all))
      (goto execute-instruction))        ;    reduce the subgraph
    (else                                 ; else if environment entry is a var
      (pop-stack)
      (set! (d-reg-class pgdr) 'AP)
      (mwrite pgar pgdr)
      (goto move-backward))))




;;; INTEGER

(instruction int problem
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction int head (goto change-directions))
(instruction int result (goto move-backward))


;;; MULTI
;;; Multiple lambda bindings.

(instruction 
  multi problem
  (cond 
    ((eq? (d-reg-type rgdr) 'MULTI)  ; if instr on top of result is MULTI
     (transfer (d-reg-operand pgdr) scratch)
     (push-unbound-vars)             ;    push UBV markers into environment
     (set! (d-reg-operand rgdr)      ;    combine the var counts
           (+ (d-reg-operand rgdr) (d-reg-operand pgdr)))
     (transfer rgdr rgdr)
     (mwrite rgar rgdr)              ;    write combined MULTI to result
     (transfer (1+ pgar) pgar)       ;    increment to next instruction
     (show (wait)
           (send simulator unhighlight-all))
     (goto next-instruction))
    ((or (zero? argcount)            ; else if no arguments 
         (= reductions red-limit))   ;         or no more reductions left
     (transfer (d-reg-operand pgdr) scratch)
     (push-unbound-vars)             ;    push UBV markers into environment
     (goto move-forward))            ;    do next instruction
    (else                            ; else perform beta reduction
      (transfer (1+ reductions) reductions)
      (push-binding #T)              ;  put binding into environment           
      (set! (d-reg-operand pgdr)     ;  decrement the lambda count in MULTI
            (-1+ (d-reg-operand pgdr)))
      (transfer pgdr pgdr)
      (if (not (zero?                ;  if still lambdas left
                 (d-reg-operand pgdr)))
          (goto execute-instruction) ;     repeat instruction MULTI
          (begin                     ;  else execute next instruction
            (transfer (1+ pgar) pgar)
            (show (wait)
                  (send simulator unhighlight-all))
            (goto next-instruction))))))


(instruction multi result
             (transfer (- binding-offset (d-reg-operand pgdr))
                       binding-offset)
             (goto move-backward))


;;; NAMED
;;; Named lambda bindings.

(instruction 
  named problem
  (cond ((or (zero? argcount) (= reductions red-limit))
         (transfer 1 scratch)
         (push-unbound-vars)
         (goto move-forward))
        (else
          (transfer (1+ reductions) reductions)
          (push-binding)
          (goto next-instruction))))

(instruction named result
             (transfer (-1+ binding-offset) binding-offset)
             (goto move-backward))

;;; PRIM
;;; Non-strict primitive.


(instruction prim problem 
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction prim result (goto move-backward))

(instruction prim head
             (if (= reductions red-limit) 
                 (goto change-directions)
                 (goto (getprop (d-reg-operand pgdr) 'PRIMITIVE))))



;;; PRIM1
;;; Primitive strict in one argument.  Set up primreg for firing later.

(instruction prim1 problem 
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction prim1 result (goto move-backward))

(instruction prim1 head
             (when (<= 1 argcount)
                   (set! (d-reg-class primreg) #T)
                   (set! (d-reg-type primreg) 1)
                   (set! (d-reg-operand primreg) 1)
                   (transfer primreg primreg)
                   (when (eq? (d-reg-operand pgdr) 'IF) ; preserve argcount
                         (cond ((< stack (-1+ memory-size))
                                (transfer (pop-stack) temp)
                                (push-stack argcount)
                                (push-stack temp))
                               (else
                                 (push-stack argcount)))))
             (goto change-directions))



;;; PRIM2
;;; Primitive strict in two arguments.  Set up primreg for firing later.

(instruction prim2 problem 
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction prim2 result (goto move-backward))

(instruction prim2 head
             (when (<= 2 argcount)
                   (set! (d-reg-class primreg) #T)
                   (set! (d-reg-type primreg) 2)
                   (set! (d-reg-operand primreg) 2)
                   (transfer primreg primreg))
             (goto change-directions))

  

;;; PTR
;;; Pointer to another expression.

(instruction 
  ptr head
  (transfer (d-reg-operand pgdr) pgar)   ; PGAR <- address of subgraph
  (set! (d-reg-operand envdr) (pop-stack)) ; make envdr a marker
  (set! (d-reg-class envdr) nil)         
  (set! (d-reg-type envdr) 'MARKER)
  (transfer envdr envdr)
  (push-env envdr #T)                      ; put marker into environment
  (show (wait) 
        (send simulator unhighlight-all)
        (send simulator send-pane 'problem 
              'display-items pgar (next-head pgar)))
  (goto next-instruction))               ; execute subgraph


(instruction ptr problem
             (push-stack env)
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction ptr result
             (transfer (pop-stack) env)      ; get proper binding context
             (show (send simulator send-pane 'env 'scroll-to-item env))
             (push-stack pgar)               ; save return address
             (push-stack primreg)            ; save current primreg
             (transfer 0 argcount)           ; set new argcount to zero
             (transfer (d-reg-operand pgdr)  ; PGAR <- address of subgraph
                       pgar)
             (set! (d-reg-class primreg) #F) ;    turn off primreg
             (transfer primreg primreg)
             (transfer 'PROBLEM mode)        ; set motion forward
             (show (wait)
                   (send simulator unhighlight-all)
                   (send simulator send-pane 'problem 
                         'display-items pgar (next-head pgar)))
             (goto next-instruction))        ; reduce subgraph


;;; START
;;; The start instruction initializes certain registers and deposits
;;; a STOP instruction.  It only is present in the problem graph.

(instruction start problem
             (transfer 0 argcount)
             (transfer 0 reductions)
             (transfer 0 binding-offset)
             (transfer 0 inhibit)
	     (set! (d-reg-operand primreg) 0)
             (set! (d-reg-type primreg) 0)
             (set! (d-reg-class primreg) nil)
             (transfer primreg primreg)
             (set! (d-reg-class argreg) nil)
             (set! (d-reg-class argreg) nil)
             (set! (d-reg-class argreg) nil)
             (transfer argreg argreg)
             (set! (d-reg-type pgdr) 'STOP)
             (goto move-forward))


;;; STOP
;;; The STOP instruction signals the end of a reduction sequence.

(instruction stop result
             (if (and (eq? (d-reg-type rgdr) 'SYM)
                      (member (d-reg-operand rgdr) '(TRUE FALSE)))
                 (mwrite (1+ pgar) rgdr))
             (sucessful-reduction #T))

;;; STRUCT
;;; Structures don't do anything.

(instruction struct head (goto change-directions))
(instruction struct problem (goto move-forward))
(instruction struct result (goto move-backward))

;;; SYMBOL
;;; If a symbol in head position has an associated definition, expand
;;; to the definition if allowed.

(instruction sym problem 
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction 
  sym head 
  (cond ((and (not (= reductions red-limit))
              (getprop (d-reg-operand pgdr) 'LPDEF))
         (transfer (getprop (d-reg-operand pgdr) 'LPDEF) pgar)
         (show (send simulator send-pane 'problem 'display-items pgar 
                     (+ pgar (-1+ (memory-element-operand 
                                     (vector-ref memory (-1+ pgar)))))))
         (goto next-instruction))
        (else
          (goto change-directions))))


(instruction 
  sym result 
  (cond ((and (not (= reductions red-limit))
              (getprop (d-reg-operand pgdr) 'LPDEF))
         (set! (d-reg-type pgdr) 'PTR)
         (set! (d-reg-operand pgdr)
               (getprop (d-reg-operand pgdr) 'LPDEF))
         (transfer pgdr pgdr)
         (transfer (1+ reductions) reductions)
         (push-stack env)
         (goto execute-instruction))
        (else
          (goto move-backward))))



;;; VAR
;;; Variable.

(instruction 
  var problem
  (transfer (1+ argcount) argcount)   ; increment argcount
  (lookup)                            ; dereference variable
  (mread temp pgdr)                   ; PGDR <- variable value
  (case (d-reg-type pgdr)
    (VAR                              ; if value is a variable
      (set! (d-reg-operand pgdr)      ;    correct binding index
            (- binding-offset (d-reg-operand pgdr)))
      (set! (d-reg-class pgdr) 'AP)
      (transfer pgdr pgdr)
      (goto move-forward))
    (PTR                              ; else if value is a pointer
      (set! (d-reg-class pgdr) 'AP)   ;    create an EP
      (set! (d-reg-type pgdr) 'EP) 
      (set! (d-reg-operand pgdr) temp)
      (transfer pgdr pgdr)
      (push-stack env)                ;    push env onto stack
      (goto move-forward))
    (EP                               ; else if value is an EP
      (push-stack env)                ;    push env onto stack
      (set! (d-reg-class pgdr) 'AP)
      (transfer pgdr pgdr)
      (goto move-forward))
    (else                             ; else make an AP and go
      (set! (d-reg-class pgdr) 'AP)
      (transfer pgdr pgdr)
      (goto move-forward))))


(instruction var result
             (goto move-backward))

(instruction 
  var head
  (lookup)                            ; dereference variable
  (var-head-action))

(define (var-head-action)
  (mread temp pgdr)                   ; PGDR <- variable value
  (cond ((eq? (d-reg-type pgdr) 'VAR)  ; if value is a variable
         (set! (d-reg-operand pgdr)    ;    correct binding index
               (- binding-offset (d-reg-operand pgdr)))
         (set! (d-reg-class pgdr) 'HEAD)
         (transfer pgdr pgdr)
         (goto change-directions))     ;    change directions
        ((member (d-reg-type pgdr) '(PTR EP))
         (when (eq? (d-reg-type pgdr) 'EP)
               (transfer (d-reg-operand pgdr) temp)  ; TEMP <- addr env entry
               (mread temp pgdr))                    ; PGDR <- env entry
         (transfer (1+ temp) temp)     ; TEMP <- addr env part of closure
         (mread temp envdr)            ; ENVDR <- env part of closure
         (push-stack (d-reg-operand envdr))  ; push env info
         (set! (d-reg-class pgdr) 'HEAD)
         (transfer pgdr pgdr)
         (show (wait) (send simulator unhighlight-all))
         (goto execute-instruction))

        (else                          ; else
          (set! (d-reg-class pgdr) 'HEAD)
          (show (send simulator send-pane 'registers 'refresh-value ''pgdr)
                (wait)
                (send simulator unhighlight-all))
          (goto execute-instruction)))) ;    execute instruction
