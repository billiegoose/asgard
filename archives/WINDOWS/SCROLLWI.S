;;; SCROLLABLE ITEM DISPLAY WINDOW CLASS
;;; Mike Hilton, 6 June 1989

;;; Scrollable item windows display a one dimensional vector of
;;; items which can be scrolled up, down, and to a specific item.
;;; The items are assumed to allready be in the vector. If the
;;; vector is modified by means other than via scroll window methods,
;;; the item display will not reflect this.

;;; The user can provide an item specific printing routine via the
;;; PRINT-FUN instance variable.  The function should print the item,
;;; preferably with no leading spaces or newlines.  The default print function
;;; is "fprint".

;;; The user can specify a region of the vector for scrolling display.
;;; If this region is larger than the height of the scroll window, then
;;; only part of this region is displayed.

;;; Items can be highlighted so that they are displayed in reverse video.


;;; SCROLLABLE-ITEM-WINDOW

(define-class scrollable-item-window
              (instvars 
                (array               ; vector containing items
                  (active nil nil array-active-set)) 
                (iwidth 1)           ; max printlength of array index
                (print-fun fprint)   ; function for printing items
                (start-region nil)   ; starting index of scrolling region
                (end-region nil)     ; ending index of scrolling region
                (first-displayed-item nil) ; index of first item in window
                (last-displayed-item nil)  ; index of last item in window
                (highlighted nil)    ; list of highlighted items
                )
              (mixins text-window)
              (options (settable-variables array print-fun)
                       inittable-variables ))

;;; ADD-FIRST
;;; Adds a new item onto the front of the current scrollable region
;;; and scrolls up to show the item.

(define-method (scrollable-item-window add-first) ()
               (when (> start-region 0)
                     (set! start-region (-1+ start-region))
                     (scroll-up)))
              

;;; ADD-LAST
;;; Adds a new item onto the end of the current scrollable region
;;; and scrolls down to show the item.

(define-method (scrollable-item-window add-last) ()                     
               (when (< end-region (-1+ (vector-length array)))
                     (set! end-region (1+ end-region))
                     (if (= end-region (1+ last-displayed-item))
                         (scroll-down)
                         (set-viewing-region 
                           (max start-region (- end-region (-1+ height)))
                           end-region))))

;;; ARRAY-ACTIVE-SET
;;; Active value method on ARRAY instance variable that determines the
;;; maximum print width of an index into ARRAY.  This is used in the
;;; printing of items to make the index column look nice.

(define-method (scrollable-item-window array-active-set) (array)
               (set! iwidth (minus (print-length (vector-length array))))
               array)


;;; CLEAR
;;; Clears the contents of the window and sets the display region 
;;; to nil.

(define-method (scrollable-item-window clear) ()
               (window-clear window)
               (set! highlighted nil)
               (set! first-displayed-item nil)
               (set! last-displayed-item nil)
               (set! start-region nil)
               (set! end-region nil))


;;; DISPLAY-ITEMS
;;; Display the items in the vector between START and END, inclusive.
;;; If the window is not high enough to show all of the items, only
;;; the first section is displayed.

(define-method (scrollable-item-window display-items) (start end)
               (when (and start end)
                     (set! start-region start)
                     (set! end-region end)
                     (set-viewing-region 
                       start
                       (min end (+ (-1+ start) height)))))


;;; HIGHLIGHT-ITEM
;;; Highlights the display of ITEM in reverse video.

(define-method (scrollable-item-window highlight-item) (item)
               (if (not (member item highlighted))
                   (set! highlighted (cons item highlighted)))
               (refresh-item item))


;;; INIT&HIDE
;;; Inititialize the scroll window to begin at location N, but suppress
;;; any display.

(define-method (scrollable-item-window init&hide) (n)
               (window-clear window)
               (set! start-region n)
               (set! end-region n)
               (set! first-displayed-item n)
               (set! last-displayed-item (-1+ n)))



;;; PRINT-ITEM
;;; Prints the item number and item in the scroll window, using
;;; the print-fun value to display the item.

(define-method (scrollable-item-window print-item) (index)
               (fprint index iwidth window)
               (display ": " window)
               (if (member index highlighted)
                   (begin 
                     (set-text-attribute! window (cadr colors) (car colors))
                     (print-fun (vector-ref array index) 
                                (+ iwidth (- (right) (left) 2))
                                window)
                     (set-text-attribute! window (car colors) (cadr colors)))
                   (print-fun (vector-ref array index) 
                              (+ iwidth (- (right) (left) 2))
                              window)))


;;; REFRESH
;;; Clear the window and redisplay the contents.

(define-method (scrollable-item-window refresh) ()
               (window-clear window)
               (when (and first-displayed-item last-displayed-item)
                     (set-viewing-region first-displayed-item 
                                         last-displayed-item)))


;;; REFRESH-ITEM
;;; If ITEM is visible in the window, it is redisplayed.

(define-method 
  (scrollable-item-window refresh-item) (item)
  (when (and (<= first-displayed-item item)
             (<= item last-displayed-item))
        (let ((cursor (window-get-cursor window)))
          (window-set-cursor! window (- item first-displayed-item) 0)
          (print-item item)
          (do ((i (cdr (window-get-cursor window)) (1+ i)))
              ((>= i width))
              (write-char #\space window))
          (window-set-cursor! window (car cursor) (cdr cursor)))))


;;; REMOVE-FIRST
;;; Removes the first item in the scrolling region.

(define-method (scrollable-item-window remove-first) ()
               (set! start-region (1+ start-region))
               (when (> start-region first-displayed-item)
                     (display-items start-region end-region)))
               
;;; REMOVE-LAST
;;; Removes the last item in the scrolling region.

(define-method (scrollable-item-window remove-last) ()
               (set! end-region (-1+ end-region))
               (when (< end-region first-displayed-item)
                     (scroll-to-item end-region))
               (when (>= last-displayed-item end-region)
                     (set-viewing-region first-displayed-item end-region)))

;;; SCROLL-RELATIVE
;;; Scrolls the window X items.  If X is positive, the window is scrolled
;;; down; if X is negative, the window is scrolled up.

(define-method
  (scrollable-item-window scroll-relative) (x)
  (let* ((s (if (negative? x) 
                (max start-region (+ first-displayed-item x))
                (min end-region (+ first-displayed-item x))))
         (e (min end-region (+ s (-1+ height)))))
    (set-viewing-region s e)))

                                           
;;; SCROLL-TO-ITEM
;;; Scrolls ITEM to the top of the window, if it is in the current 
;;; scrolling region.

(define-method (scrollable-item-window scroll-to-item) (item)
               (when (and (<= start-region item) (<= item end-region))
                     (set-viewing-region 
                       item
                       (min (+ (-1+ item) height) end-region))))

                          
;;; SCROLL-DOWN
;;; Scroll the viewing region down one item, if that item is in the
;;; scrolling region.

(define-method
  (scrollable-item-window scroll-down) ()
  (cond ((and (= last-displayed-item end-region) 
              (not (= last-displayed-item first-displayed-item)))
         (set! first-displayed-item (1+ first-displayed-item))
         (set-viewing-region first-displayed-item last-displayed-item))
        ((< last-displayed-item end-region)
         (set! last-displayed-item (1+ last-displayed-item))
         (if (> (1+ (- last-displayed-item first-displayed-item)) 
                height)
             (set! first-displayed-item (1+ first-displayed-item)))
         (if (> last-displayed-item first-displayed-item)
             (newline window))
         (print-item last-displayed-item))))


;;; SCROLL-REGION-DOWN
;;; Scrolls down one item, and extends the scrolling region if necessary.

(define-method (scrollable-item-window scroll-region-down) ()
               (if (< last-displayed-item end-region)
                   (scroll-down)
                   (add-last)))


;;; SCROLL-REGION-UP
;;; Scrolls the veiwing region up one item, and extends the viewing region
;;; if necessary.

(define-method (scrollable-item-window scroll-region-up) ()
               (if (> first-displayed-item start-region)
                   (scroll-up)
                   (add-front)))

;;; SCROLL-UP
;;; Scroll the viewing region up one item, if the item is included in the
;;; scrolling region.

(define-method (scrollable-item-window scroll-up) ()
               (when (> first-displayed-item start-region)
                     (set! first-displayed-item (-1+ first-displayed-item))
                     (if (>= last-displayed-item 
                             (+ first-displayed-item height))
                         (set! last-displayed-item (-1+ last-displayed-item)))
                     (set-viewing-region first-displayed-item
                                         last-displayed-item)))


;;; SET-VIEWING-REGION
;;; Sets the region displayed in the window to be from START to END.  
;;; Calling routines should ensure that only items in the current 
;;; scrolling region and capable of fitting completely in the window 
;;; are passed.

(define-method (scrollable-item-window set-viewing-region) (start end)
               (set! first-displayed-item start)
               (set! last-displayed-item end)
               (window-clear window)
               (do ((i first-displayed-item (1+ i)))
                   ((= i last-displayed-item) (print-item i) #T)
                   (print-item i)
                   (newline window)))


;;; SHOW-ITEM
;;; Ensures that ITEM is in the viewing-region, if it is in the scrolling
;;; region.

(define-method (scrollable-item-window show-item) (item)
               (when (and (not (and (<= first-displayed-item item)
                                    (<= item last-displayed-item)))
                          (<= start-region item)
                          (<= item end-region))
                     (cond ((< last-displayed-item item)
                            (scroll-relative (- item last-displayed-item)))
                           (else
                             (scroll-to-item item)))))

;;; UNHIGHLIGHT-ITEM
;;; Unhighlights ITEM so that it is printed normally.

(define-method (scrollable-item-window unhighlight-item) (item)
               (when (member item highlighted)
                     (set! highlighted (delq! item highlighted))
                     (refresh-item item)))

