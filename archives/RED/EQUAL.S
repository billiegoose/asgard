;;; Alpha equality predicate.
;;; 22 June 1989, Mike Hilton


(define depth 0)

;;; EQUAL
;;; Tests two normal forms for alpha convertibility.
;;; Upon entry, PGAR has addr of second operand
;;;             RGDR contains second operand

(primitive 
  equal
  (mread (1+ pgar) argreg)  ; ARGREG <- first operand
  (cond ((equal? rgdr argreg)
         (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'TRUE) pgdr)
         (goto alpha-finish))
        ((and (type=? 'PTR rgdr) (type=? 'PTR argreg))
         (push-stack depth)
         (push-stack pgar)         ; address where result will go
         (transfer 0 depth)   ; counts the depth of subgraph
         (transfer (d-reg-operand rgdr) temp)
         (transfer (d-reg-operand argreg) pgar)
         (push-stack (-1+ temp)) ; marks the end of traversal
         (goto alpha-down))
        (else
          (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'FALSE) pgdr)
          (goto alpha-finish))))

(define (alpha-succeed)
  (show (minor-status "alpha-succeed")
        (send simulator unhighlight-all))
  (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'TRUE) pgdr)
  (transfer (pop-stack) pgar)
  (transfer (pop-stack) depth)
  (goto alpha-finish))

(define (alpha-finish)
  (transfer (1+ reductions) reductions)
  (goto move-backward))

(define (alpha-fail)
  (show (minor-status "alpha-fail")
        (send simulator unhighlight-all))
  (let loop ()
    (cond ((not (zero? depth))
           (transfer (-1+ depth) depth)
           (pop-stack)
           (pop-stack)
           (loop))))
  (pop-stack) ; throw away end of traversal marker
  (transfer (make-d-reg 'class 'HEAD 'type 'SYM 'operand 'FALSE) pgdr)
  (transfer (pop-stack) pgar)
  (transfer (pop-stack) depth)
  (goto alpha-finish))




;;; alpha-down walks down the spine of two graphs and tests them for
;;; alpha equality.  TEMP and PGAR are the addresses of the graphs.  

(define (alpha-down)
  (show (wait) (minor-status "alpha-down")
        (send simulator unhighlight-all))
  (mread pgar pgdr)
  (mread temp rgdr)
  (cond ((and (class=? 'HEAD pgdr) (class=? 'HEAD rgdr))
         (cond ((equal? pgdr rgdr)
                (transfer (-1+ temp) temp)
                (transfer (-1+ pgar) pgar)
                (goto alpha-up))
               ((and (type=? 'STRUCT pgdr) (type=? 'STRUCT rgdr))
                (push-stack (-1+ temp))
                (push-stack (-1+ pgar))
                (transfer (1+ depth) depth)
                (goto alpha-struct))
               (else
                 (goto alpha-fail))))
        ((or (class=? 'HEAD pgdr) (class=? 'HEAD rgdr))
         (goto alpha-fail))
        ((or (and (type=? 'NAMED pgdr) (type=? 'NAMED rgdr))
             (equal? pgdr rgdr))
         (transfer (1+ temp) temp)
         (transfer (1+ pgar) pgar)
         (goto alpha-down))
        ((and (type=? 'PTR pgdr) (type=? 'PTR rgdr))
         (transfer (1+ temp) temp)
         (transfer (1+ pgar) pgar)
         (goto alpha-down))
        (else
          (goto alpha-fail))))

;;; alpha-up coordinates the checking of subgraphs for alpha equality.


(define (alpha-up)
  (show (wait)
        (minor-status "alpha-up")
        (send simulator unhighlight-all))
  (mread pgar pgdr)
  (cond ((class=? 'HEAD pgdr)
         (transfer (pop-stack) scratch)
         (if (= temp scratch)
             (goto alpha-succeed)
             (begin
               (transfer scratch temp)
               (transfer (pop-stack) pgar)
               (transfer (-1+ depth) depth)
               (goto alpha-up))))
        ((type=? 'PTR pgdr)
         (push-stack (-1+ pgar))
         (push-stack (-1+ temp))
         (transfer (1+ depth) depth)
         (mread temp rgdr)
         (transfer (d-reg-operand pgdr) pgar)
         (transfer (d-reg-operand rgdr) temp)
         (goto alpha-down))
        (else
          (transfer (-1+ pgar) pgar)
          (transfer (-1+ temp) temp)
          (goto alpha-up))))

;;; Check two structures to see if they are alpha convertible.  The
;;; elements of the structure will need to be forced (reduced),
;;; before they are tested.

(define (alpha-struct)
  (show (wait) (minor-status "alpha-struct"))
  (transfer (d-reg-operand pgdr) pgar)
  (transfer (d-reg-operand rgdr) temp)
  (mread pgar pgdr)      ; check the tags to see if they are identical
  (mread temp rgdr)
  (if (not (equal? pgdr rgdr))
      (goto alpha-fail)
      (begin
        (mread (1+ pgar) pgdr) ; check the sizes to see if they are identical
        (mread (1+ temp) rgdr)
        (if (not (equal? pgdr rgdr))
            (goto alpha-fail)
            (begin
              (push-stack (+ pgar 2))    ; addr of structure A
              (push-stack (+ temp 2))    ; addr of structure B
              (push-stack (d-reg-operand pgdr))  ; size of structures
              (set! (d-reg-operand rgdr) 'TRUE)
              (goto alpha-s-loop))))))

;;; loops through the elements of a structure and tests for alpha equality.

(define (alpha-s-loop)
  (show (wait)
        (minor-status "alpha-s-loop")
        (send simulator unhighlight-all))
  (transfer (pop-stack) scratch)  ; size of structures
  (transfer (pop-stack) temp) ; addr of structure B
  (transfer (pop-stack) pgar) ; addr of structure A
  (cond ((not (eq? (d-reg-operand rgdr) 'TRUE))
         (goto alpha-fail))
        ((zero? scratch)
         (transfer (pop-stack) pgar)
         (transfer (pop-stack) temp)
         (transfer (-1+ depth) depth)
         (goto alpha-up))
        (else
          (transfer (-1+ scratch) scratch)
          (push-stack pgar)
          (push-stack temp)
          (push-stack scratch)
          ;; create a graph to reduce args & check for equality
          (lookup-loop)
          (write-inst 'AP 'EP temp)
          (transfer (pop-stack) scratch)
          (push-stack scratch)
          (transfer pgar temp)
          (lookup-loop)
          (write-inst 'AP 'EP temp)
          (write-inst 'HEAD 'PRIM2 'EQUAL)
          (transfer (- rgar 2) pgar)
          (write-inst 'CONTROL 'JUMP 'alpha-s-loop)
          (transfer 'problem mode)
          (show
            (send simulator unhighlight-all)
            (send simulator send-pane 'problem 'display-items
                  pgar (next-head pgar)))
          (goto next-instruction))))
          



