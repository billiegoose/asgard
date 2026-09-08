;;; test file utilizing the full first order logic
;;; This problem is taken from a paper by Vijay Pitchumani

;;; Tony, Mike, and John are members of an alpine club.
(defclause c1 () (member tony))
(defclause c2 () (member mike))
(defclause c3 () (member john))


;;; Tony likes both rain and snow.
(defclause c4 () (likes tony rain))
(defclause c5 () (likes tony snow))

;;; All members of the club are climbers or skiers.
;;; (member X) => (skier X) or (climber X)
(defclause c6 (x) (not (member x)) (skier x) (climber x))

;;; Climbers dislike rain.
;;; (climber X) => ~(likes X rain)
(defclause c7 (x) (not (climber x)) (not (likes x rain)))

;;; Skiers like snow.
;;; (skier X) => (likes X snow)
(defclause c8 (x) (not (skier x)) (likes x snow))

;;; Mike dislikes whatever Tony likes.
;;; (likes tony X) => ~(likes mike X)
(defclause c9 (x) (not (likes tony x)) (not (likes mike x)))

;;; Mike likes whatever Tony dislikes.
;;; ~(likes tony X) => (likes mike X)
(defclause c10 (x) (likes tony x) (likes mike x))



;;; GOAL: Is there a member who is a climber but not a skier?

(defclause goal (x) (not (member x)) (not (climber x)) (skier x))

