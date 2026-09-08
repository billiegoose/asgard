
(ldefine append 
         (lambda (x y z)
           (try (and (unify x nil) (unify y z))
                (try (lambda (u v w)
                       (and (unify x (pair u v))
                            (unify z (pair u w))
                            (append v y w)))
                     false))))

(ldefine t1 (lambda (a) (append (pair 1 nil) (pair 2 nil) a) a))
