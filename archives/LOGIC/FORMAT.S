;;; Formatted output facility
;;; Mike Hilton, 1 Feb 1989

;;; DEFINE-PRINTER
;;; Defines a printing function for structures of type STRUCT.  The
;;; print function should take the structure object and return a string
;;; suitable for printing.  In this function, the object should be referred
;;; to as the STRUCT name.
;;; Example:  
;;;   (define-printer foo 
;;;      (string-append "<foo " (object->string (foo-var foo)) ">"))

(macro define-printer
  (lambda (e)
    (let ((struct (cadr e))
          (body (cddr e)))
      `(putprop ',struct
                (eval (compile '(lambda (,struct) ,@body)))
                'object->string))))

;;; GET-PRINTER
;;; Finds a print function for structures, if one exists.

(define (get-printer object)
  (when (structure? object)
        (do ((type (mapcar cdr (vector-ref object 0)) (cdr type)))
            ((or (null? type) (getprop (car type) 'object->string))
             (if (null? type) 
                 nil
                 (getprop (car type) 'object->string))))))
  
;;; FORMAT provides formatted text output to the port of your choice.
;;; A string representing the output is returned by this function.

;;; The format function has the following directives:
;;;  ~numS   which prints a scheme object; the optional number gives
;;;          the minimum print width for the object, any remaining
;;;	     space is padded with blanks, right padded if num is
;;;	     positive, left padded is num is negative
;;;  ~%	     prints a newline
;;;  ~~      prints a tilde

;;; Port is the output destination.  If #T, the current default port
;;; is used; if #F (or nil), there is no destination.

(define (format port dstring . args)
  (do ((start 0)
       (end (string-length dstring))
       (str ""))
      ((>= start end) 
       (cond ((port? port) (display str port))
             ((eq? #T port) (display str)))
       str)
      (let ((index (substring-find-next-char-in-set dstring start end #\~)))
        (set! str 
              (string-append
                str
                (cond ((eq? index #F)
                       (begin0
                         (substring dstring start end)
                         (set! start end)))
                      (else
                        (string-append
                          (begin0 (substring dstring start index)
                                  (set! start (+ index 2)))
                          (case (string-ref dstring (1+ index))
                            (#\~ "~")
                            (#\% (list->string (list #\newline)))
                            ((#\S #\s #\A #\a)
                             (begin0 (object->string (car args))
                                     (set! args (cdr args))))
                            ((#\- #\+ #\0 #\1 #\2 #\3 #\4 #\5 #\6 #\7 #\8 #\9)
                             (begin0
                               (pad-string 
                                 (object->string (car args))
                                 (substring->integer dstring (1+ index))
                                 #\space)
                               (set! args (cdr args))
                               (set! start 
                                     (1+ (substring-find-next-char-in-set 
                                           dstring index end "Ss")))))
                            )))))))))

(define (pad-string str size pad-char)
  (if (< (string-length str) (abs size))
      (let ((pad (make-string (- (abs size) (string-length str)) pad-char)))
        (if (negative? size)
            (string-append pad str)
            (string-append str pad)))
      str))


(define (substring->integer str index)
  (let ((sign (case (string-ref str index)
                (#\- (set! index (1+ index)) -1)
                (#\+ (set! index (1+ index))  1)
                (else 1))))
    (do ((value 0 (+ (* value 10) (- (char->integer char) 
                                     (char->integer #\0))))
         (char (string-ref str index) (string-ref str index)))
        ((not (and (char>=? char #\0) 
                   (char<=? char #\9)))
         (set! index (1+ index))
         (* sign value))
        (set! index (1+ index)))))

(define (object->string object)
  (cond ((boolean? object) (if object "#T" "#F"))
        ((number? object) (number->string object '(heur)))
        ((symbol? object) (symbol->string object))
        ((char? object) (list->string (list object)))
        ((string? object) object)
        ((structure? object) 
         (let ((fun (get-printer object)))
           (if fun 
               (fun object) 
               (string-append "#<struct " (symbol->string (structure? object))
                              ">"))))
        ((pair? object) 
         (do ((object object (cdr object))
              (str "(" ))
             ((null? object) (string-append str ")"))
             (if (null? (cdr object))
                 (set! str (string-append str (object->string (car object))))
                 (set! str (string-append str (object->string (car object))
                                          " ")))))
        ((closure? object) "#<closure>")
        ((continuation? object) "#<continuation>")
        ((procedure? object) "#<engine>")
        ((environment? object) "#<environment>")
        ((stream? object) "#<stream>")
        ((output-port? object) "#<output port>")
        ((input-port? object) "#<input port>")
        ((port? object) "#<port>")
        ((vector? object) "#<vector>")
        (else "#<unknown>")))



;;; FPRINT
;;; Prints OBJECT on PORT, making sure that it has a width of at least
;;; WIDTH by padding the output with blanks.  If WIDTH is positive the
;;; blanks are padded on the right; if negative, the left.
;;; FPRINT truncates any characters beyond width, signalling truncation with
;;; a # character.

(define (fprint object width . port)
  (set! port (car port))
  (let* ((length (fprint-length object))
         (padding (- (abs width) length)))
    (if (> padding 0)
        (begin
          (if (not (negative? width)) (fdisplay object port))
          (do ((i 0 (1+ i)))
              ((>= i padding))
              (write-char #\space port))
          (if (negative? width) (fdisplay object port)))
        (if (<= length (abs width))
            (fdisplay object port)
            (begin
              (fdisplay (substring (object->string object) 0 (-1+ (abs width)))
                       port)
              (write-char #\@ port))))))

;;; FDISPLAY

(define (fdisplay object . port)
  (if (structure? object)
      (display (object->string object) (car port))
      (display object (car port))))


;;; FPRINT-LENGTH
;;; Modified version of print-length that checks to see if the object
;;; is a structure with a special print-function, and if so, uses it.

(define (fprint-length object)
    (if (structure? object)
        (let ((print-fun (get-printer object)))
          (if print-fun
              (string-length (print-fun object))
              (print-length object)))
        (print-length object)))


;;; STRUCTURE?
;;; A predicate for testing if an object is a structure.  This depends on the
;;; current implementation of structures in PC-SCHEME.  It also happens to
;;; return the name of the structure type, if X is a structure.

(define (structure? x)
  (if (vector? x)
      (cdr (assoc '|#!STRUCTURE| (vector-ref x 0)))
      #F))

