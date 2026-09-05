node |= value next
build-node == (lambda (n)
  (if (= n 0)
      NIL
      (make-node n (build-node (1- n)))))
sum-node == (lambda (node n acc)
  (if (= n 0)
      acc
      (sum-node (node-next node) (1- n) (+ acc (node-value node)))))
(sum-node (build-node 24) 24 0)
