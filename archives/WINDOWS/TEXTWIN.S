;;; WINDOW UTILITIES
;;; Mike Hilton, 2 Feb 1989

;;; MAKE-TEXT-WINDOW
;;; Makes a text window.
;;; (make-text-window label left top right bottom [text border background])

(define (make-text-window label left top right bottom . args)
  (let ((window 
          (if (or (null? label) (string-null? label))
              (make-window #F)
              (make-window label #T)))
        (text (car args))
        (border (cadr args))
        (text-bkgnd (caddr args))
        (border-bkgnd (cadddr args)))
    (window-set-position! window top left)
    (window-set-size! window (- bottom top) (- right left))
    (if text (set-text-attribute! window text text-bkgnd))
    (if border (set-border-attribute! window border border-bkgnd))
    ))


;;; COLOR-ALIST
;;; This alist contains the values for the color codes used in the
;;; CGA attribute bits.

(define color-alist
  '((black 0) (blue 1) (green 2) (cyan 3) (red 4) (magenta 5) (brown 6)
    (white 7) (grey 8) (light-blue 9) (light-green 10) (light-cyan 11)
    (light-red 12) (light-magenta 13) (yellow 14) (intense-white 15)))


;;; SET-BORDER-ATTRIBUTE!
;;; Sets the WINDOW's border attribute to so that the border text is in
;;; color BORDER and the border background has color BACKGROUND.  If a
;;; background color is not specified, the current background color is
;;; used.

(define (set-border-attribute! window border . background)
  (window-set-attribute! window 'border-attributes
                         (+ (cadr (assoc border color-alist))
                            (if (car background)
                                (* (cadr (assoc (car background) color-alist))
                                   16)
                                (* (truncate 
                                     (/ (window-get-attribute 
                                          window 'border-attributes)
                                      16))
                                   16)))))


;;; SET-TEXT-ATTRIBUTE!
;;; Sets the WINDOW's text attribute so that text has color TEXT and
;;; the background has color BACKGROUND.  If a background color is not
;;; specified, the current background color is used.

(define (set-text-attribute! window text . background)
  (window-set-attribute! window 'text-attributes
                         (+ (cadr (assoc text color-alist))
                            (if (car background)
                                (* (cadr (assoc (car background) color-alist))
                                   16)
                                (* (truncate 
                                     (/ (window-get-attribute 
                                          window 'text-attributes)
                                      16))
                                   16)))))
  

;;; SET-WINDOW-WRAP!
;;; If ON? is #T, then the WINDOW is set to wrap output lines around;
;;; else the output is truncated when a line exceeds the window width.

(define (set-window-wrap! window on?)
  (let ((current-flags  (window-get-attribute window 'window-flags)))
    (if on?
        (if (even? current-flags)
            (window-set-attribute! window 'window-flags (1+ current-flags)))
        (if (odd? current-flags)
            (window-set-attribute! window 'window-flags (-1+ current-flags))))
    ))






;;; SCOOPS TEXT WINDOW CLASS


;;; TEXT-WINDOW
;;; A (possibly) labelled, bordered text window.

(define-class text-window
              (instvars window   ; scheme window object
                        edges    ; list: (left top right bottom)
                        height   ; inside height of window
                        width    ; inside width of window
                        (label nil)   
                        (colors  ; color attr: (txt txtbkgd brder brderbkgd)
                          '(white black red black))
                        )
              (options (gettable-variables window)
                       (inittable-variables edges label colors)))


;;; CLEAR
;;; Clears all output from window.

(define-method (text-window clear) () (window-clear window))

;;; INIT
;;; Creates the scheme window object and sets height and width.

(define-method (text-window init) ()
               (let ((left (car edges))
                     (top (cadr edges))
                     (right (caddr edges))
                     (bottom (cadddr edges)))
                 (set! window (make-text-window 
                                label left top right bottom 
                                (car colors) (caddr colors) 
                                (cadr colors) (cadddr colors)))
                 (set! height (- bottom top))
                 (set! width (- right left))))


                
(define-method (text-window refresh) ()
               (let ((cursor (window-get-cursor window)))
                 (save-contents)
                 (clear)
                 (restore-contents)
                 (window-set-cursor! window (car cursor) (cdr cursor))))

(define-method (text-window restore-contents) ()
               (window-restore-contents window (car label))
               (set! label (cdr label)))

(define-method (text-window save-contents) ()
               (set! label (cons (window-save-contents window) label)))

(define-method (text-window set-cursor) (x y)
               (window-set-cursor! window x y))

(define-method (text-window set-position) (x y)
               (let ((temp (window-save-contents window)))
                 (window-set-position! window x y)
                 (window-set-size! window height width)
                 (set! edges (list x y (+ x width) (+ y height)))
                 (clear)
                 (window-restore-contents window temp)))

(define-method (text-window left) () (car edges))
(define-method (text-window top) () (cadr edges))
(define-method (text-window right) () (caddr edges))
(define-method (text-window bottom) () (cadddr edges))

(define-method (text-window text-color) () (car colors))
(define-method (text-window text-background-color) () (cadr colors))
(define-method (text-window border-color) () (caddr colors))
(define-method (text-window border-background-color) () (cadddr colors))
