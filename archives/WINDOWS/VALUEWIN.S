;;; VARIABLE VALUE DISPLAY WINDOW CLASS
;;; Mike Hilton, 6 Feb 1989

;;; The variable value display class of windows provides a tabular display
;;; of the value of prescribed variables defined in the global scheme 
;;; environment.

;;; The print function used to print the value of variables is in the
;;; instance variable PRINT-FUN.  This print function must accept three
;;; arguments: the object, a suggested maximum print width, and a port.
;;; The default print function is FPRINT, which truncates output longer
;;; than the max print width.

(define-class variable-value-window
              (instvars (variables nil)    ; list of the variables to display
                        (placement nil)    ; placement list
                        (print-fun fprint) ; print function for values
                        (maxwidth 15))     ; max print width of a var name
              (mixins text-window)
              (options inittable-variables))


;;; REFRESH
;;; Draws the variable-value pair display in the window.

(define-method (variable-value-window refresh) ()
               (clear)
               (for-each 
                 (lambda (x)
                   (let ((var (car x))
                         (row (cadr x))
                         (col (caddr x))
                         (varwidth (cadddr x)))
                     (window-set-cursor! window row col)
                     (fprint var (minus varwidth) window)
                     (display ": " window)
                     (print-fun (eval var) 
                                (min maxwidth (- width (+ 2 (+ col varwidth))))
                                window)))
                  placement))


;;; REFRESH-VALUE
;;; Redisplays the value of VARiable.

(define-method (variable-value-window refresh-value) (var)
               (let ((place (assoc var placement)))
                 (if place
                     (let ((row (cadr place))
                           (col (+ 2 (+ (caddr place) (cadddr place)))))
                       (window-set-cursor! window row col)
                       (print-fun (eval var) 
                                  (min maxwidth (- width col))
                                  window)))))
                     
                 


;;; SETUP-DISPLAY
;;; Compute the placement of each variable-value pair in the window.

(define-method 
  (variable-value-window setup-display) ()
  (let* ((n (length variables))
         (cols (max 1 (truncate (/ n height))))
         (rows (min n height))
         (part (partition variables rows))
         (specs nil)
         (col 0))
    (set! placement
          (dolist (group part specs)
                  (let ((width (min maxwidth
                                    (apply max
                                           (mapcar print-length group))))
                        (row 0))
                    (dolist (var group)
                            (set! specs (cons (list var row col width) 
                                              specs))
                            (set! row (1+ row)))
                    (set! col (+ col (+ width (+ 3 maxwidth)))))))))
