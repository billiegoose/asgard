;;; Compiler from lambda expressions to Lambda Assembly Code (LAC)
;;; Mike Hilton, 6 June 1989


(define *primitives* '(Y PACK SELECT unify))
(define *unary-primitives* '(1+ 1- abs even? odd? minus negative? positive? 
                                if and or))
(define *binary-primitives* '(+ - * / modulo expt = < > <> <= >= max min
                                equal))


;;; COMPILE-EXP
;;; Compile a lambda source expression into a list of LAC instructions.

(define (compile-exp exp)
  (let ((address 0))
    (define (compile-1 exp bindings)
      (cond ((null? exp) nil)
            ((atom? exp)
             (set! address (1+ address))
             (list (cons 'HEAD (instruction-type exp bindings))))
            ((eq? (car exp) 'lambda)
             (let ((args (cadr exp)))
               (set! address (+ address (length args)))
               (append (mapcar (lambda (x) (list 'BINDING 'NAMED x)) args)
                       (compile-1 (cddr exp) (append (reverse args) 
                                                     bindings)))))
            ((eq? (car exp) 'mlambda)
             (set! address (1+ address))
             (let ((args (cadr exp)))
               (cons (list 'BINDING 'MULTI (length args))
                     (compile-1 (cddr exp)
                                (append (reverse args) bindings)))))
            ((atom? (cdr exp))
             (set! address (1+ address))
             (cons (cons 'AP (instruction-type (cdr exp) bindings))
                   (compile-1 (car exp) bindings)))
            (#T
              (set! address (1+ address))
              (let ((old-address address)
                    (operator (compile-1 (car exp) bindings)))
                (cons (list 'AP 'PTR (1+ (- address old-address)))
                      (append operator
                              (compile-1 (cdr exp) bindings)))))))
    (compile-1 (curry exp) nil)))


;;; INSTRUCTION-TYPE
;;; Takes an atom and determines what its instruction type is.

(define (instruction-type x bindings)
  (cond ((integer? x) (list 'INT x))
        ((float? x) (list 'FLOAT x))
        ((symbol? x)
         (cond ((char=? #\$ (string-ref (symbol->string x) 0))
                (let* ((sym (symbol->string x))
                       (dollars 
                         (let loop ((index 0))
                           (cond ((char=? #\$ (string-ref sym index))
                                  (loop (1+ index)))
                                 (else index))))
                       (index 0))
                  (set! sym (string->symbol (substring sym dollars
                                                       (string-length sym))))
                  (let loop ((binds bindings))
                    (cond ((null? binds)
                           (list 'SYM 
                                 (string->symbol
                                   (string-append (make-string dollars #\$)
                                                  (symbol->string sym)))))
                          ((and (eq? (car binds) sym) (= 0 dollars))
                           (list 'VAR index))
                          ((eq? (car binds) sym)
                           (set! index (1+ index))
                           (set! dollars (-1+ dollars))
                           (loop (cdr binds)))
                          (else 
                            (set! index (1+ index))
                            (loop (cdr binds))
                            )))))
               ((member x bindings)
                (list 'VAR (- (length bindings) (length (member x bindings)))))
               ((member x *primitives*) (list 'PRIM x))
               ((member x *unary-primitives*) (list 'PRIM1 x))
               ((member x *binary-primitives*) (list 'PRIM2 x))
               (#T (list 'SYM x))))))


;;; CURRY
;;; Puts an expression into curried form.

(define (curry exp)
  (cond ((null? exp) nil)
        ((atom? exp) exp)
        ((eq? (car exp) 'lambda)
         (cons 'lambda (cons (cadr exp) (curry (cddr exp)))))
        ((eq? (car exp) 'mlambda)
         (cons 'mlambda (cons (cadr exp) (curry (cddr exp)))))
        ((= 1 (length exp)) (curry (car exp)))
        ((= 2 (length exp)) 
         (cons (curry (car exp)) (curry (cadr exp))))
        (#T
          (curry (cons (list (car exp) (cadr exp))
                       (cddr exp))))))


;;; UNCURRY
;;; Uncurries a curried expression.

(define (uncurry exp)
  (define (uncurry-1 exp)
    (cond ((null? exp) nil)
          ((atom? exp) (list exp))
          ((eq? (car exp) 'lambda)
           (let ((body (uncurry-1 (cddr exp))))
             (if (eq? (car body) 'lambda) (set! body (list body)))
             (cons 'lambda (cons (cadr exp) body))))
          ((pair? (cdr exp))
           (let ((operator (uncurry-1 (car exp))))
             (if (eq? (car operator) 'lambda) (set! operator (list operator)))
             (append operator (list (uncurry-1 (cdr exp))))))
          (#T
            (let ((operator (uncurry-1 (car exp)))
                  (operand (uncurry-1 (cdr exp))))
              (if (eq? (car operator) 'lambda) (set! operator (list operator)))
              (if (eq? (car operand) 'lambda) (set! operand (list operand)))
              (append operator operand)))))
  (let ((result (uncurry-1 exp)))
    (if (= (length result) 1)
        (car result)
        result)))



;;; LOAD-LAC
;;; Loads a list of LAC instructions into the memory of the simulator,
;;; starting at address ADDR.  Returns the address of the last location used.

(define (load-lac code addr)
  (let ((mem-el (make-memory-element)))
    (do ((code code (cdr code))
         (addr addr (1+ addr)))
        ((null? code)
         addr)
        (set! (memory-element-class mem-el) (caar code))
        (set! (memory-element-type mem-el) (cadar code))
        (set! (memory-element-operand mem-el) 
              (if (eq? (cadar code) 'PTR)
                  (+ addr (caddar code))
                  (caddar code)))
        (mem-write addr mem-el))))



;;; DECOMPILE-EXP
;;; Decompiles a section of LAC code beginning at location ADDR,
;;; producing a lambda source expression.

(define (decompile-exp addr)
  (uncurry (decomp-1 addr nil)))

(define (decomp-1 addr bindings)
  (let ((el (vector-ref memory addr)))
    (case (memory-element-class el)
      (AP (cons (decomp-1 (1+ addr) bindings)
                (decomp-2 addr bindings)))
      (BINDING (decomp-2 addr bindings))
      (CONTROL
        (case (d-reg-type el)
          (NAMED (decomp-1 (1+ addr) (cons 'control-placeholder bindings)))
          (else (decomp-1 (1+ addr) bindings))))
      (HEAD (decomp-2 addr bindings))
      (else
        (error "Unknown class: " (memory-element-class el)))
      )))

(define (decomp-2 addr bindings)
  (define (new-symbol) (string->symbol (symbol->string (gensym "VAR"))))
  (define (nth i list) (if (zero? i) (car list) (nth (-1+ i) (cdr list))))
  (let ((el (vector-ref memory addr)))
    (case (memory-element-type el)
      ((INT PRIM PRIM1 PRIM2 SYM)
       (memory-element-operand el))
      (PTR (decomp-1 (memory-element-operand el) bindings))
      (STRUCT 
        (let ((structure (memory-element-operand el)))
          (list ;'structure
                (memory-element-operand (vector-ref memory structure))
                '**)))
      (VAR (let* ((index (memory-element-operand el))
                  (name (nth index bindings)))
             (do ((i 0 (1+ i))
                  (new-name (symbol->string name)))
                 ((>= i index) (string->symbol new-name))
                 (if (eq? name (nth i bindings))
                     (set! new-name (string-append "$" new-name))))))
      (MULTI
        (do ((i 0 (1+ i))
             (name (new-symbol) (new-symbol))
             (vars nil (cons name vars))
             (bindings bindings (cons name bindings)))
            ((>= i (memory-element-operand el))
             (list 'lambda (reverse vars) 
                   (decomp-1 (1+ addr) bindings)))))
      (NAMED
        (do ((vars nil vars)
             (word el (vector-ref memory addr)))
            ((not (and (eq? (memory-element-type word) 'NAMED)
                       (eq? (memory-element-class word) 'BINDING)))
             (list 'lambda (reverse vars)
                   (decomp-1 addr bindings)))
            (set! addr (1+ addr))
            (set! vars (cons (memory-element-operand word) vars))
            (set! bindings (cons (memory-element-operand word) bindings))))
      )))
