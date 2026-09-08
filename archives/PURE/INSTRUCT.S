;;; INSTRUCTION SET IMPLEMENTATION FOR THE LAMBDA PROCESSOR
;;; Mike Hilton, 9 Feb 1989


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


;;; LOOKUP
;;; Looks up a variable reference in the environment.  The variable index
;;; to look up is located in the PGDR operand slot.
(define lrefs 0)
(define (lookup)
  (show (minor-status "LOOKUP"))
  (transfer (d-reg-operand pgdr) scratch)
  (transfer env temp)
  (let loop ()
    (mread temp envdr)
	(setq lrefs (1+ lrefs))
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
;;; This is also the place to handle sharing.

(define (move-backward)
  (show (wait)
        (send simulator unhighlight-all)
        (minor-status "MOVE-BACKWARD"))
  (transfer pgdr rgdr)
  (transfer (-1+ pgar) pgar)                 ; addr of next instruction
  (show (send simulator show-item pgar))
  (mread pgar pgdr)                          ; pgdr <- next instruction
  (if (not (eq? (d-reg-class pgdr) 'HEAD))   ; if not a HEAD instruction
      (goto execute-instruction)             ;    execute
      (begin                                 ; else at end of subgraph, so
        (transfer (pop-stack) temp)          ;    pop return address
        (if (eq? (d-reg-class rgdr) 'HEAD)   ;    if subgraph is single word
            (begin
              (set! (d-reg-class rgdr) 'AP)  ;       make result an AP
              (mwrite temp rgdr)             ;       write result into spine
              (transfer (-1+ rgar) rgar))    ;       pop value off result graph
            (begin                           ;    else
              (set! (d-reg-operand rgdr)     ;       point to the result
                    (1+ pgar))
              (set! (d-reg-class rgdr) 'AP)
              (set! (d-reg-type rgdr) 'PTR)
              (transfer rgdr rgdr)
              (mwrite temp rgdr)))           ;       write pointer into spine
        (transfer temp pgar)                 ; resume traversing parent
        (transfer rgdr pgdr)
        (show (wait)
              (send simulator unhighlight-all))
        (goto move-backward))))


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


;;; PUSH-UNBOUND-VARS
;;; Push the number of unbound variables indicated by the operand of PGDR
;;; in the environment.

(define (push-unbound-vars)
  (show (minor-status "PUSH-UNBOUND-VARS"))
  (set! (d-reg-type envdr) 'VAR)
  (set! (d-reg-class envdr) nil)
  (transfer (d-reg-operand pgdr) scratch)
  (let loop ()
    (when (not (zero? scratch))
          (transfer (1+ binding-offset) binding-offset)
          (set! (d-reg-operand envdr) binding-offset)
          (push-env envdr)
          (transfer (-1+ scratch) scratch)
          (loop))))


;;;; INSTRUCTION SET


;;; EP
;;; Environment pointer.  Points to a closure in the environment.

(instruction 
  ep result
  (transfer (pop-stack) env)             ; cut back env to old size
  (show (send simulator send-pane 'env 'display-items env env-addr))
  (transfer (d-reg-operand pgdr) temp)   ; TEMP <- address of environment entry
  (show (send simulator show-item temp))
  (mread temp pgdr)                      ; PGDR <- environment entry
  (case (d-reg-type pgdr)
    (PTR                                 ; if environment entry is a pointer
      (push-stack pgar)                  ;    push return address onto stack
      (transfer 0 argcount)              ;    argcount <- 0
      (set! (d-reg-class pgdr) 'HEAD)
      (transfer 'PROBLEM mode)
      (show (transfer pgdr pgdr) (wait) (send simulator unhighlight-all))
      (goto execute-instruction))        ;    reduce the subgraph
    (VAR                                 ; else if environment entry is a var
      (pop-stack)
      (set! (d-reg-class pgdr) 'AP)
      (mwrite pgar pgdr)
      (goto move-backward))))

(instruction 
  ep head
  (transfer (d-reg-operand pgdr) temp)   ; TEMP <- address of environment entry
  (show (send simulator show-item temp))
  (mread temp pgdr)                      ; PGDR <- environment entry
  (set! (d-reg-class pgdr) 'HEAD)
  (show (transfer pgdr pgdr)
        (wait)
        (send simulator unhighlight-all))
  (goto execute-instruction))            ; execute the environment entry


;;; MULTI
;;; Multiple lambda bindings.

(instruction 
  multi problem
  (cond 
    ((eq? (d-reg-type rgdr) 'MULTI)  ; if instr on top of result is MULTI
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
     (push-unbound-vars)             ;    push UBV markers into environment
     (goto move-forward))            ;    do next instruction
    (else                            ; else perform beta reduction
      (transfer (1+ reductions) reductions)
      (transfer (-1+ argcount) argcount)
      (case (d-reg-type rgdr)
        (VAR                         ;    if argument is a variable
          (set! (d-reg-operand rgdr) ;       calculate proper binding index
                (- binding-offset (d-reg-operand rgdr)))
          (push-env rgdr))           ;       put variable into environment
        (PTR                         ;    else if argument is a pointer
          (set! (d-reg-operand envdr);       build a closure
                (pop-stack))         ;       get env information
          (set! (d-reg-type envdr) 'ENV)
          (set! (d-reg-class envdr) 'CLOSURE)
          (transfer envdr envdr)
          (push-env envdr)           ;       put env part of closure
          (set! (d-reg-class rgdr) 'CLOSURE)
          (push-env rgdr))           ;       put ptr part of closure
        (EP                          ;    else if argument is an envptr
          (pop-stack)                ;       discard env information
          (push-env rgdr))           ;       put envptr into environment
        )
      (transfer (-1+ rgar) rgar)     ;  pop used argument off result graph
      (show (send simulator send-pane 'result 'remove-last))
      (mread rgar rgdr)              ;  get next argument from result graph
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


;;; PTR
;;; Pointer to another expression.

(instruction 
  ptr head
  (transfer (d-reg-operand pgdr) pgar)   ; PGAR <- address of subgraph
  (transfer (1+ temp) temp)              ; TEMP <- addr of env part of closure
  (mread temp envdr)                     ; ENVDR <- env part of closure
  (set! (d-reg-class envdr) nil)         ; make envdr a marker
  (set! (d-reg-type envdr) 'MARKER)
  (push-env envdr)                       ; put marker into environment
  (show (wait) (send simulator unhighlight-all))
  (goto next-instruction))               ; execute subgraph


(instruction ptr problem
             (push-stack env)
             (transfer (1+ argcount) argcount)
             (goto move-forward))

(instruction ptr result
             (transfer (pop-stack) env)      ; cut back env to old size
             (show (send simulator send-pane 'env
                         'display-items env env-addr))
             (push-stack pgar)               ; save return address
             (transfer (d-reg-operand pgdr)  ; PGAR <- address of subgraph
                       pgar)
             (transfer 0 argcount)           ; set new argcount to zero
             (transfer 'PROBLEM mode)        ; set motion forward
             (show (wait)
                   (send simulator unhighlight-all))
             (goto next-instruction))        ; reduce subgraph


;;; START
;;; The start instruction initializes certain registers and deposits
;;; a STOP instruction.  It only is present in the problem graph.

(instruction start problem
             (transfer 0 argcount)
             (transfer 0 reductions)
             (transfer 0 binding-offset)
             (set! (d-reg-type pgdr) 'STOP)
             (goto move-forward))


;;; STOP
;;; The STOP instruction signals the end of a reduction sequence and
;;; causes certain stacks and registers to be reset.

(instruction stop result
             (sucessful-reduction #T))


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
      (goto move-forward))))


(instruction var result
             (goto move-backward))

(instruction 
  var head
  (lookup)                            ; dereference variable
  (mread temp pgdr)                   ; PGDR <- variable value
  (set! (d-reg-class pgdr) 'HEAD)
  (if (eq? (d-reg-type pgdr) 'VAR)    ; if value is a variable
      (begin
        (set! (d-reg-operand pgdr)    ;    correct binding index
              (- binding-offset (d-reg-operand pgdr)))
        (transfer pgdr pgdr)
        (goto change-directions))     ;    change directions
      (begin                          ; else
        (show (send simulator send-pane 'registers 'refresh-value ''pgdr)
              (wait)
              (send simulator unhighlight-all))
        (goto execute-instruction)))) ;    execute instruction
