;;; LAMBDA REDUCTION MACHINE
;;; Mike Hilton, 27 June 1989

;;; This simulator of the lambda processor is based on the microprogrammed
;;; reducer on the AMD29C300 Evaluation Board.  This is not a true fidelity
;;; simulation of the AMD29C300 architecture, but it is reasonably close
;;; simulation of the actions taken by the instruction set implemented by
;;; the microprogram.

;;; REGISTERS

(define argcount 0)                   ; argument count
(define argreg (make-d-reg))          ; primitve operator argument register
(define binding-offset 0)             ; variable binding offset
(define env 0)                        ; environment pointer
(define envdr (make-d-reg))           ; environment data 
(define envstack 0)                   ; storage area for the environments
(define inhibit 0)                    ; addr where arg inhibition should stop
(define inhibit1 0)                   ; stores correct red count during inhibit
(define mode nil)                     ; tells if executing PROBLEM or RESULT
(define pgar 0)                       ; problem graph address 
(define pgdr (make-d-reg))            ; problem graph data 
(define primreg (make-d-reg))         ; primitive operator marking register
(define red-limit 0)                  ; maximum reductions allowable
(define reductions 0)                 ; number of reductions so far
(define reset-list nil)               ; trail for logic programming
(define rgar 0)                       ; result graph address 
(define rgdr (make-d-reg))            ; result graph data
(define scratch 0)                    ; temporary scratchpad
(define stack 0)                      ; stack pointer
(define temp 0)                       ; temporary scratchpad



;;; SYSTEM VARIABLES, used by host controller

(define abort-reduction nil)                  ; continuation for aborting
(define env-addr (- memory-size stack-size))  ; start of environment space
(define graphic-display nil)                  ; flag for graphics display
(define next-reduction-step nil)              ; used to implement goto
(define problem-addr 0)                       ; start of problem code area
(define result-addr 0)                        ; start of result code area
(define stack-addr (-1+ memory-size))         ; start of stack space
(define stats nil)                            ; flag for printing statistics
(define %status "")                           ; status of simulator
(define step? nil)                            ; flag for single step execution
(define sucessful-reduction nil)              ; sucess continuation



;;;; MACROS


;;; INSTRUCTION
;;; The microcode sequences that comprise an instruction are defined using
;;; the INSTRUCTION macro.  The instruction macro has two arguments and a 
;;; body composed of microinstructions.  The two arguments are the
;;; instruction's NAME and a CASE designator which is used during instruction
;;; decoding.  An instruction may have several different microsequences, each
;;; one for a special circumstance.  The CASE designator tells which circum-
;;; stance this microsequence is for.  The microsequences are kept on the
;;; property list of the instruction's NAME, keyed by the CASE designator.

(macro instruction
  (lambda (e)
    (let ((name (cadr e))
          (designator (caddr e))
          (microsequence (cdddr e)))
      `(putprop ',name
                (eval (compile '(lambda () 
                                 (show (major-status 
                                         ,(string-append 
                                            (symbol->string name) ", "
                                            (symbol->string designator)
                                            " mode ")))
                                 ,@microsequence)))
               ',designator))))


;;; LDEFINE
;;; Associate an expression with a symbol.  The EXPression is compiled
;;; and stored in code memory, and the address of the code is stored as
;;; the property LPDEF on the symbol's property list.

(macro ldefine
  (lambda (e)
    (let ((name (cadr e))
          (exp (caddr e)))
      `(let ((code (cons (list 'CONTROL 'DEF ',name)
                         (cons (list 'CONTROL 'SIZE 0)
                               (compile-exp ',exp))))
             (old-prob-addr problem-addr))
         (set! problem-addr (load-lac code problem-addr))
         (putprop ',name (+ 2 old-prob-addr) 'LPDEF)
         (set! (memory-element-operand (vector-ref memory (1+ old-prob-addr)))
               (- problem-addr (+ 2 old-prob-addr)))))))

         

;;; MREAD
;;; Read the contents of the memory location ADDR, storing a copy
;;; of the contents in DESTination.

(macro mread
  (lambda (e)
    (let ((addr (cadr e))
          (dest (caddr e))
          (sym (gensym)))
      `(let ((,sym (mem-read ,addr ,dest)))
         (show (send simulator highlight-read ,addr)
               (send simulator send-pane 'registers 
                     'refresh-value '',dest))
         ,sym))))

;;; MWRITE
;;; Write the contents of SOURCE into the memory location ADDR.

(macro mwrite
  (lambda (e)
    (let ((addr (cadr e))
          (dest (caddr e)))
      `(begin (mem-write ,addr ,dest)
              (show (send simulator highlight-write ,addr)
                    (send simulator send-pane 'registers 
                          'refresh-value '',dest))))))


;;; PRIMITVE
;;; Defines the microcode sequence that implements a primitive operation.
;;; The primitive macro has one argument, the primitive name, and a body
;;; composed of microinstructions.  The microsequences are kept on the
;;; property list of the primitive's NAME, keyed by the atom "primitive".

(macro primitive
  (lambda (e)
    (let ((name (cadr e))
          (microsequence (cddr e)))
      `(putprop ',name
                (eval (compile '(lambda ()
                                  (show (major-status
                                          ,(string-append
                                             (symbol->string name) 
                                             " primitive ")))
                                  ,@microsequence)))
                'primitive))))




;;; SHOW
;;; The show macro conditionally executes its body, if the graphics
;;; display of the simulation is enabled.

(macro show
  (lambda (e)
    `(when graphic-display ,@(cdr e))))


;;; TRANSFER
;;; Copies the value in SOURCE to DEST.  Is able to handle both memory
;;; registers and general registers.

(macro transfer
  (lambda (e)
    (let ((source (cadr e))
          (dest (caddr e))
          (val (gensym)))
      (if (memory-element? (eval dest))
          `(begin 
             (let ((,val ,source))
               (set! (memory-element-class ,dest) (memory-element-class ,val))
               (set! (memory-element-type ,dest) (memory-element-type ,val))
               (set! (memory-element-operand ,dest) 
                     (memory-element-operand ,val))
               (show (send simulator send-pane 'registers 
                           'refresh-value '',dest))
               ,dest))
          `(begin
             (set! ,dest ,source)
             (show (send simulator send-pane 'registers 
                         'refresh-value '',dest))
             ,dest)))))





;;;; FUNCTIONS


;;; INIT-DISPLAY
;;; Initialize the graphics display windows.

(define (init-display)
  (send simulator unhighlight-all)
  (send simulator send-pane 'registers 'refresh)
  (send simulator send-pane 'problem 'display-items
        problem-addr (-1+ result-addr))
  (send simulator send-pane 'result 'init&hide (1+ result-addr))
  (send simulator send-pane 'env 'display-items
        env env)
  (send simulator send-pane 'stack 'display-items
        stack stack))



;;; POP-STACK
;;; Pop the stack, returning the value popped off.

(define (pop-stack)
  (let ((val (mread stack nil)))
    (when (< stack (-1+ memory-size))
          (transfer (1+ stack) stack)
          (show (send simulator send-pane 'stack 'remove-first)))
    val))

;;; PUSH-ENV
;;; Push VAL onto the environment.

(define (push-env val . inc-env?)
  (set! envstack (-1+ envstack))
  (mwrite envstack val)
  (show (send simulator send-pane 'env 'add-first))
  (when (eq? (car inc-env?) #T) (transfer envstack env)))

;;; PUSH-STACK
;;; Push VAL onto the stack.

(define (push-stack val)
  (transfer (-1+ stack) stack)
  (mwrite stack val)
  (show (send simulator send-pane 'stack 'add-first)))


;;; PREP-REDUCER
;;; Prepare the machine for reduction of EXP.

(define (prep-reducer exp)
  (let ((code (compile-exp exp)))
    (set! reset-list nil)
    (set! pgar problem-addr)
    (set! rgar (load-lac (cons '(CONTROL START NIL) code) problem-addr))
    (set! result-addr rgar)
    (set! stack stack-addr)
    (set! envstack env-addr)
    (set! env env-addr)
    (set! mode 'PROBLEM)
    (set! memory-reads 0)
    (set! memory-writes 0)
    (show (init-display))))

;;; REDUCE
;;; Takes an EXPression in lambda calculus and compiles, loads, and reduces it,
;;; then decompiles the result to form another lambda expression.  The 
;;; optional LIMIT argument sets an upper limit on the number of reductions
;;; that are performed.  If not supplied, there is no limit.

(define (reduce exp . limit)
  (set! red-limit (if limit (car limit) -1))
  (prep-reducer exp)
  (let ((result (red)))
    (when stats
          (writeln "reductions: " reductions)
          (writeln "memory cycles: " (+ memory-reads memory-writes)
                   "  reads: " memory-reads
                   "  writes: " memory-writes)
          (let ((graph (- rgar result-addr))
                (env (- env-addr envstack)))
            (writeln "space: " (+ graph env)
                     "  graph space: " graph
                     "  env space: " env)))
    result))

(define (red)
  (call/cc
    (lambda (k)
      (set! abort-reduction k)
      (set! next-reduction-step next-instruction) ; kick-start reducer
      (call/cc
        (lambda (k)
          (set! sucessful-reduction k)
          (reduction-loop)))      ; reduce
      (decompile-exp (1+ result-addr)))))

            

;;; REDUCTION-LOOP  &  GOTO
;;; The reduction loop is a device used for eliminating deep recursion stack
;;; stack buildup by implementing global goto's.  The function in the variable
;;; NEXT-REDUCTION-STEP is executed.

(define (reduction-loop)
  (do ()
      (#F)
      (next-reduction-step)))

(define (goto function) (set! next-reduction-step function))


;;; MAJOR-STATUS
;;; Sets the status variable to a new string and redisplays the value.

(define (major-status string)
  (set! %status string)
  (let ((win (send simulator send-pane 'status 'get-window)))
    (newline win)
    (display %status win)))


;;; MINOR-STATUS
(define (minor-status string)
  (let ((win (send simulator send-pane 'status 'get-window)))
    (newline win)
    (display %status win)
    (display " -- " win)
    (display string win)))


;;; NEXT-HEAD
;;; Searches a code sequence for the next head instruction.  Returns its
;;; address.

(define (next-head addr)
  (cond ((= addr memory-size) (-1+ addr))
        ((eq? (memory-element-class (vector-ref memory addr)) 'HEAD) addr)
        (else (next-head (1+ addr)))))

     
;;; WAIT
;;; The wait loop waits for the user to strike a key.

(define (wait . msg)
  (if step?
      (if msg
          (show (minor-status (string-append (car msg) " >>press key<<")))
          (show (minor-status
                  "  >>Press Any Key To Continue, ESC to Abort<<")))
      (if msg (show (minor-status (car msg)))))
  (do ()
      ((or (char-ready?) (not step?))
       (when (char-ready?)
             (let ((char (read-char)))
               (if msg (show (minor-status (car msg))))
               (cond ((char-ci=? char #\escape)
                      (abort-reduction #F))
                     ((zero? (char->integer char))
                      (read-char)
                      (set! step? (not step?)))))))
      ()))

