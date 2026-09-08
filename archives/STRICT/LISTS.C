/* LIST PRIMITIVES FOR HEAD ORDER REDUCTION SYSTEM
/* Mike Hilton, 7 September 1989
*/
 

#include <stdio.h>
#include "lrs.h"

extern int  argcount;
extern union control *aux;
extern int binding_offset;
extern node *env;
extern int  frozen_redcnt;
extern node *fs;
extern node *inhibit;
extern int  mode;
extern node *pc;
extern int  prim_args;
extern node *primitive;
extern int  red_limit;
extern int  reductions;
extern union control *stack;
extern node *ws;

extern symbol *true;
extern symbol *false;
extern symbol *nil;


/* CONS
/* Cons is the lazy list constructor.
*/

void prim_cons()
{
	if ((argcount < 2) || (reductions == red_limit)) {
#ifdef DEBUG
		fprintf(stdout, "\ncons: NOT FIRING -- argcount or redlimit");
#endif
		inst_inert();
		if (argcount == 0) return;
		frozen_redcnt = reductions;
		reductions = red_limit;
		inhibit = pc - argcount;
		return;
	}
	else {
		node *next = fs;
		int i;
#ifdef DEBUG
		fprintf(stdout, "\n cons: FIRING");
#endif
		fs -= 2;		/* allocate space for cons cell in freespace */
		pc = ws;
		
      for(i = 2; i > 0; i--) {
      	--next;
         if (pc->type == PTR) {
         	next->head = TRUE; next->type = SUSPEND;
            next->op.addr = make_suspend(pc->op.addr, (stack--)->ptr,
                                                binding_offset);
         }
         else if (pc->type == CLOSURE) {
         	if (pc->op.addr->type == CL_PTR) {
            	next->head = TRUE; next->type = SUSPEND;
               next->op.addr = make_suspend(pc->op.addr->op.addr,
                                                  (pc->op.addr+1)->op.addr,
                                                  binding_offset);
            }
            else *next = *(pc->op.addr);
         }
         else if (pc->type == UBV) {
         	next->head = TRUE; next->type = VAR;
            next->op.index = binding_offset - pc->op.index;
			}
         else {
         	*next = *pc;
            next->head = TRUE;
         }
         --pc;
      }
		ws = pc + 1;
      ws->head = TRUE; ws->type = CONS; ws->op.addr = next;
      ++reductions;
		mode = RESULT;      
	}
}



/* CAR
/* Select the first element of a cons cell.
*/

void prim_car()
{
	switch (mode) {
		case HEAD:	inst_inert();
						if ((argcount >= 1) && (reductions != red_limit)) {
							primitive = pc + 1;
							prim_args = 1;
							(--aux)->intval = argcount - 1;
						}
						break;

		case RESULT:
			{
				node *cons = pc + 1;
				argcount = (aux++)->intval;
				if ((reductions != red_limit) &&
					 ((cons->type == CONS)) || ((cons->type == SYM) && (cons->op.sym == nil))) {
#ifdef DEBUG
					fprintf(stdout, "\ncar FIRING");
#endif
					ws = pc;		/* prepare to move forward again */
					mode = PROBLEM;
					++reductions;
					
					if (cons->type == CONS) pc = cons->op.addr+1;
					else { cons->head = TRUE; pc = cons; }

	            /* arrange for element to be updated with value if possible */
   	         if ((pc->type == SUSPEND) && (ws->type == JOIN))
      	         *(ws->op.addr) = *pc;

      	   }
      	   else {
#ifdef DEBUG
					fprintf(stdout, "\ncar NOT FIRING, reductions or type");
#endif
				}
				break;
			}
	}
}
					



/* CDR
/* Select the second element of a cons cell.
*/

void prim_cdr()
{
	switch (mode) {
		case HEAD:	inst_inert();
						if ((argcount >= 1) && (reductions != red_limit)) {
							primitive = pc + 1;
							prim_args = 1;
							(--aux)->intval = argcount - 1;
						}
						break;

		case RESULT:
			{
				node *cons = pc + 1;
				argcount = (aux++)->intval;
				if ((reductions != red_limit) &&
					 ((cons->type == CONS)) || ((cons->type == SYM) && (cons->op.sym == nil))) {
#ifdef DEBUG
					fprintf(stdout, "\ncdr FIRING");
#endif
					ws = pc;		/* prepare to move forward again */
					mode = PROBLEM;
					++reductions;

					if (cons->type == CONS) pc = cons->op.addr;
					else { cons->head = TRUE; pc = cons; }
					
	            /* arrange for element to be updated with value if possible */
   	         if ((pc->type == SUSPEND) && (ws->type == JOIN))
      	         *(ws->op.addr) = *pc;

      	   }
      	   else {
#ifdef DEBUG
					fprintf(stdout, "\ncdr NOT FIRING, reductions or type");
#endif
				}
				break;
			}
	}
}
					


/* NULL?
/* Predicate to test if a list is empty, i.e., NIL.
*/

void prim_null()
{
	node *arg = pc + 1;
	
	if ((arg->type == SYM) && (arg->op.sym == nil)) {
		arg->head = TRUE; arg->type = SYM; arg->op.sym = true;
		ws = arg;
		++reductions;
	}
	else if (arg->type == CONS) {
		arg->head = TRUE; arg->type = SYM; arg->op.sym = false;
		ws = arg;
		++reductions;
	}
}
