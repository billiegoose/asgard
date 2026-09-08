;;; Memory definition file for the lambda processor simulator
;;; Mike Hilton, 27 April 1989

(define-structure memory-element
                  class
                  type
                  operand)

(define-printer memory-element
           (string-append 
             (case (memory-element-class memory-element)
               (AP "A ") (BINDING "B ") (HEAD "H ") (CONTROL "C ") 
               (#F "f ") (#T "t ") (else "? "))
             (object->string (memory-element-type memory-element))
             " "
             (object->string (memory-element-operand memory-element))))


(define (print-memory-element el . port)
  (set! port (car port))
  (display (case (memory-element-class el)
             (AP "A ") (BINDING "B ") (HEAD "H ") (CONTROL "C ") (else "? "))
           port)
  (display (memory-element-type el) port)
  (display " " port)
  (display (memory-element-operand el) port))


(define-structure (d-reg (include memory-element)))

(define memory-size 1000)
(define memory (make-vector memory-size))
(define stack-size 50)
(define memory-reads 0)   ; count of the number of memory reads performed
(define memory-writes 0)  ; count of the number of memory writes performed


;;; MEM-PRINT
;;; prints the contents of the memory locations between START and END,
;;; inclusive.

(define (mem-print start end . port)
  (set! port (car port))
  (let ((fport (if port port #T)))
    (do ((start start (1+ start)))
        ((> start end) (newline port))
        (newline port)
        (fprint start 4 port)
        (let ((el (vector-ref memory start)))
          (if (memory-element? el)
              (print-memory-element el port)
              (display el port))))))


;;; MEM-READ
;;; Read the value in SOURCE from memory and store it in DEST, if
;;; DEST is a memory-element; else return the value.

(define (mem-read source dest)
  (let ((mem (vector-ref memory source)))
    (set! memory-reads (1+ memory-reads))
    (if (and (memory-element? mem) (memory-element? dest))
        (begin
          (set! (memory-element-type dest) (memory-element-type mem))
          (set! (memory-element-class dest) (memory-element-class mem))
          (set! (memory-element-operand dest) (memory-element-operand mem))
          dest)
        mem)))


;;; MEM-WRITE
;;; Write the VALUE to memory at ADDR.

(define (mem-write addr value)
  (set! memory-writes (1+ memory-writes))
  (if (memory-element? value)
      (let ((mem (vector-ref memory addr)))
        (if (memory-element? mem)
            (begin 
              (set! (memory-element-type mem) (memory-element-type value))
              (set! (memory-element-class mem) (memory-element-class value))
              (set! (memory-element-operand mem) 
                    (memory-element-operand value))
              mem)
            (vector-set! 
              memory addr
              (make-memory-element 'type (memory-element-type value)
                                   'class (memory-element-class value)
                                   'operand (memory-element-operand value)))))
      (vector-set! memory addr value)))



