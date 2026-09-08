;;; GRAPHIC INTERFACE FOR THE LAMBDA PROCESSOR SIMULATOR
;;; Mike Hilton, 2 Feb 1989

;;; The graphic interface for the lambda processor simulation system 
;;; is a set of windows which show the state of the processor's
;;; registers and memory, and highlight operations taking place.
;;; The interface lets a person step through the execution of LAC
;;; code.

;;; The interface is built on top of SCOOPS, the Scheme object-oriented
;;; programming system.


;;; LAMBDA-SIMULATOR
;;; The class which manages the organization and action of the simulator
;;; as a whole.

(define-class lambda-simulator
              (instvars 
                (registers
                  (make-instance variable-value-window
                                 'label "REGISTERS" 'edges '(1 1 79 6)
                                 'colors '(black white red white)
                                 'variables '(pgar pgdr rgar rgdr envdr
                                                   argcount binding-offset 
                                                   mode reductions red-limit
                                                   scratch temp primreg
                                                   argreg inhibit)))
                (problem 
                  (make-instance scrollable-item-window 
                                 'label "PROBLEM" 'edges '(1 7 21 15)
                                 'colors '(black cyan red cyan)))
                (result
                  (make-instance scrollable-item-window 
                                 'label "RESULT" 'edges '(22 7 42 15)
                                 'colors '(black cyan red cyan)))
                (env
                  (make-instance scrollable-item-window 
                                 'label "ENVIRONMENT" 'edges '(43 7 63 15)
                                 'colors '(black cyan red cyan)))
                (stack
                  (make-instance scrollable-item-window 
                                 'label "STACK" 'edges '(64 7 79 15)
                                 'colors '(black cyan red cyan)))
                (interaction
                  (make-instance text-window 'edges '(1 16 79 22)
                                 'colors '(intense-white blue 
                                                         red blue)))
                (status
                  (make-instance text-window 'edges '(1 23 79 24)
                                 'colors '(grey white white white)))
                (highlighted nil))
              (options gettable-variables 
                       inittable-variables))




;;; ALL-PANES
;;; Returns a list of all the panes in the simulator.

(define-method (lambda-simulator all-panes) ()
               (list status registers interaction problem result env stack))

;;; CLEAR
;;; Clears all the panes in the simulator.

(define-method (lambda-simulator clear) ()
               (mapc (lambda (x) (send x clear)) (all-panes)))


;;; HIGHLIGHT-ITEM
;;; Send all panes a message to highlight ITEM.

(define-method (lambda-simulator highlight-item) (item)
               (mapc (lambda (x) (send-if-handles x highlight-item item)) 
                     (all-panes))
               (if (not (member item highlighted))
                   (set! highlighted (cons item highlighted))))


;;; HIGHLIGHT-READ
;;; Highlights the reading of memory location ADDR.

(define-method (lambda-simulator highlight-read) (addr)
               (highlight-item addr))

;;; HIGHLIGHT-WRITE
;;; Highlihgts the writing of memory location ADDR.

(define-method (lambda-simulator highlight-write) (addr)
               (highlight-item addr))


;;; INIT
;;; Initializes each of the panes in the simulator.

(define-method (lambda-simulator init) ()
               (mapc (lambda (x) (send x init)) (all-panes))
               (send registers setup-display))

;;; REFRESH
;;; Refreshes each of the panes in the simulator.

(define-method (lambda-simulator refresh) ()
               (mapc (lambda (x) (send x refresh)) (all-panes)))


;;; SEND-PANE
;;; Redirects a message pass to one of its instance variables.

(define-method (lambda-simulator send-pane) (pane message . args)
               (eval `(send ,pane ,message ,@args)))

;;; SET-MEMORY
;;; Sets the array variable in the code windows.

(define-method (lambda-simulator set-memory) (mem)
               (mapc (lambda (x) (send-if-handles x set-array mem))
                     (all-panes))
               #T)

;;; SHOW-ITEM
;;; Makes sure that ITEM is visible in any code window that includes it.

(define-method (lambda-simulator show-item) (item)
               (mapc (lambda (x) (send-if-handles x show-item item))
                     (all-panes)))

;;; UNHIGHLIGHT-ALL
;;; Unhighlights all the highlighted items.

(define-method (lambda-simulator unhighlight-all) ()
               (mapc unhighlight-item (copy highlighted)))


;;; UNHIGHLIGHT-ITEM
;;; Sends all of its panes a message to unhighlight ITEM.

(define-method (lambda-simulator unhighlight-item) (item)
               (mapc (lambda (x) (send-if-handles x unhighlight-item item)) 
                     (all-panes))
               (set! highlighted (delq! item highlighted)))







(define simulator (make-instance lambda-simulator))
(define focus nil)   ; current expression of focus in simulator


;;; REDUCER
;;; Invokes the lambda simulator.

(define (reducer)
  (window-clear 'console)
  (send simulator init)
  (send simulator clear)
  (send simulator set-memory memory)
  (send simulator refresh)
  (let ((window (send (send simulator get-interaction) get-window)))
    (set! (fluid output-port) window)
    (set! (fluid input-port) window))
  (putprop '%reducer-history (list '()) '%reducer-history)
  (set! graphic-display #T)
  (set! step? #T)
  (reducer-top-level)
  (set! graphic-display #F)
  (set! step? #F)
  (set! (fluid output-port) standard-output)
  (set! (fluid input-port) standard-input)
  (window-clear 'console)
  )



;;; REDUCER-TOP-LEVEL
;;; The read-reduce-print loop of the lambda simulation system.

(define (reducer-top-level) ()
  (fresh-line)
  (display "[")
  (display (length (getprop '%reducer-history '%reducer-history)))
  (display "]:- ")
  (let ((problem (read)))
    (flush-input)
    (if (or (eof-object? problem) (eq? problem 'exit))
        (display "[End of file read by REDUCER-TOP-LEVEL]")
        (begin
          (cond ((pair? problem)
                 (case (car problem)
                   (%C (set! problem (reducer-%c (cadr problem))))
                   (%D (set! problem (reducer-%d (cadr problem))))
                   (%E (set! problem (reducer-%e (cadr problem))))
                   (LDEFINE (eval problem) 
                            (set! problem nil)
                            (set! focus (caddr problem))))
                 (when problem
                       (set! focus problem)
                       (putprop '%reducer-history 
                                (cons (list problem) 
                                      (getprop '%reducer-history
                                               '%reducer-history))
                                '%reducer-history)
                       (prep-reducer problem)))
                ((or (integer? problem) (eq? problem '*))
                 (if (integer? problem)
                     (transfer problem red-limit)
                     (transfer -1 red-limit))
                 (when (null? focus) 
                       (set! focus (cdar (getprop '%reducer-history 
                                                  '%reducer-history)))
                       (prep-reducer focus))
                 (let ((answer (red)))
                   (write answer)
                   (putprop '%reducer-history 
                            (cons (cons focus answer)
                                  (cdr (getprop '%reducer-history 
                                                '%reducer-history)))
                            '%reducer-history)
                   (set! focus nil)))
                ((symbol? problem)
                 (case problem
                   (STEP (set! step? #T))
                   (NOSTEP (set! step? #F))
                   (TRACE (set! graphic-display #T))
                   (NOTRACE (set! graphic-display #F))
                   (else
                     (writeln "Unknown command ignored.")))))
          (reducer-top-level)))))



;;; REDUCER-%C accesses the nth user command
;;; REDUCER-%D accesses the result of the nth user command
;;; REDUCER-%E evaluates a scheme expression and returns the result

(define (reducer-%c n)
  (let ((history (getprop '%reducer-history '%reducer-history)))
    (and (positive? n)
         (< n (length history))
         (car (list-ref (reverse history) n)))))

(define (reducer-%d n)
  (let ((history (getprop '%reducer-history '%reducer-history)))
    (and (positive? n)
         (< n (length history))
         (cdr (list-ref (reverse history) n)))))
          
(define (reducer-%e exp) (eval exp))
  
  
  
