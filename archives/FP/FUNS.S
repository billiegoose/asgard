(ldefine fact (lambda (n) (if (= n 0) 1 (* n (fact (1- n))))))

(ldefine yfact (Y (lambda (fac n) (if (= n 0) 1 (* n (fac (1- n)))))))

(ldefine cons (pack pair 2))
(ldefine car (select pair 1))
(ldefine cdr (select pair 2))

(ldefine bottom (Y a))

(ldefine eval-list 
         (lambda (x)
           (if (equal x nil)
               nil
               (: (car x) (eval-list (cdr x))))))

(ldefine list (cons (fact 0) 
                    (cons (fact 1)
                          (cons (fact 2)
                                nil))))
               
               
