/* Unification primitive for HORSE.
/* Mike Hilton, 9 Nov 89
*/

#define DEBUG_OCCURS

#include <stdio.h>
#include <curses.h>
#include "lrs.h"

extern node *ws, *pc, *env, *primitive, *fs, *heap;
extern unsigned long reductions, red_limit;
extern int mode, debug, prim_args, argcount, binding_offset;
extern control *aux, *stack;
extern reset *reset_ptr;
extern symbol *true, *false, *unify, *unify_star, *and, *bind, *neutral;
extern symbol *genvar;


/* BIND
/* When there are reductions left, BIND binds the variable in the
/* arg1 position to the expression in the arg2 position.
/* No charge is made for this binding.
*/

void prim_bind()
{
	if (reductions == red_limit) {
		if (debug) {
			outstring(stdscr, "\n\rBIND primitive -- NOT FIRING, red_limit");
			wrefresh(stdscr);
		}
		inst_inert();
		if (pc->type == INT) {
			pc->type = VAR; pc->op.index = pc->op.intval;
			inst_inert();
		}
		return;
	}
	if (argcount < 2) {
		if (debug) {
			outstring_ns(stdscr, "\n\rBIND primitive -- NOT FIRING, argcount!!! SOMETHING'S WRONG");
			wrefresh(stdscr);
		}
		inst_inert();
		return;
	}

	if (debug) {
		outstring(stdscr, "\n\rBIND primitive -- FIRING");
		wrefresh(stdscr);
	}
	bind_var(ws, ws-1, ((ws-1)->type == PTR) ? (stack--)->ptr : env);
	make_result(ws-1, neutral);
	--reductions;
	return;
}

	

/* BIND_VAR
/* Bind the variable indicated by VAR to VALUE.  If a closure must
/* be created, the extra two spaces of the UBV are used.
*/

void bind_var(var, value, env)
node *var, *value, *env;
{
	var = lookup(var->op.addr, 0);
	(++reset_ptr)->val = var->op.index;
	reset_ptr->addr = var;
	if (value->type == PTR) {
		var->type = CLOSURE;	var->op.addr = var+2;
		(var+2)->type = CL_PTR; (var+2)->op.addr = value->op.addr;
		(var+3)->type = CL_ENV; (var+3)->op.addr = env;
	}
	else if (value->type == UBV) {
		value = lookup(value->op.addr, 0);
		var->type = IP;
		var->op.addr = value;
	}
	else {
		var->type = value->type;
		var->op = value->op;
	}
	
	if (debug) {
		foutstring(stdscr, "\n\rbind: binding location %p to (%p) ", var, value);
		print_node(stdscr, value);
	}
}


/* INSERT_BINDING_PAIRS
/* If bindings made by unification will not be used to instantiate an
/* expression because the allowed reductions have run out, these
/* bindings need to be recorded in the graph so that they will not be
/* lost.  This is done by inserting the binding pairs into the graph.
/* The bindings are in the reset_list between the reset_ptr and PTR.
/* The graph segment is created and inserted, and a pointer to where
/* the pc should begin traversing this new graph is returned.
/*
/* PTR is a pointer into the reset_list; the binding pairs to be created
/* lie between reset_ptr and PTR.  ANCHOR is a pointer to where the
/* pairs should be inserted.  HEAD is a pointer to where the head of the
/* new pair subgraph should point.  BEFORE is a boolean flag to tell if
/* the new graph should be inserted before or after the anchor node
/* contents.
*/


node *insert_binding_pairs(ptr, anchor, head, before)
reset *ptr;
node *anchor, *head;
int before;
{
	int pairs = reset_ptr - ptr;
	node *root = ws + 1;
	node *spine = ws + pairs + 2;
	node *new_pc;

	if (debug) {
		foutstring(stdscr, "\n\rinsert_binding_pairs:  from %p to %p", reset_ptr, ptr);
		wrefresh(stdscr);
	}
	if (pairs == 0) return(pc);
	spine->class = HEAD; spine->type = PTR; spine->op.addr = head;
	if (before) {
		*(spine-1) = *anchor;
		new_pc = spine - 2;
	}
	else {
		*(++ws) = *anchor;
		new_pc = spine - 1;
	}
	anchor->class = HEAD; 
	ws = spine;
	if (before) --spine;
	ptr = reset_ptr;
	while (pairs-- > 0) {
		(--spine)->class = APPLY; spine->type = PTR; spine->op.addr = ws+1;
		*(++ws) = *(ptr->addr);	ws->class = APPLY;
		(++ws)->class = APPLY; ws->type = INT;
		ws->op.intval = binding_offset - ptr->val;
		(++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = bind;
		--ptr;
		(++stack)->ptr = env;
	}
	if (debug) {
		foutstring(stdscr, "\n\rinsert_binding_pairs(%p, %p, %d)", ptr, anchor, before);
		outstring(stdscr, "\n\r  building binding graph");
		print_mem(stdscr, root-1, ws);
	}
	return(new_pc);
}








/* UNIFY
/* Unification predicate.  
*/

void prim_unify()
{
   switch (mode) {
      case HEADM:
         {
            node *arg1   = ws;
            node *arg2   = ws - 1;
               
            if (debug) {
               foutstring(stdscr, "\n\rprim_unify: arg1 (%p) = ", arg1);
               print_node(stdscr, arg1);
               foutstring(stdscr, "  arg2 (%p) = ", arg2);
               print_node(stdscr, arg2);
            }

            if ((argcount < 2) || (reductions == red_limit)) {
               if (debug) {
                  outstring(stdscr, "\n\r  NOT FIRING, red_limit or argcount");
                  wrefresh(stdscr);
               }
               inst_inert();
               return;
            }

            
            /* Dereference EP's */
            if (arg1->type == EP) {
            	node *value = lookup(arg1->op.addr, 0);
					if (value->type != UBV) {
	            	arg1->type = value->type;
   	         	arg1->op = value->op;
      	      	if (debug) {
         	   		outstring(stdscr, "\n\r  dereferencing arg1 to ");
            			print_node(stdscr, arg1);
            		}
            	}
            }
            if (arg2->type == EP) {
            	node *value = lookup(arg2->op.addr, 0);
            	if (value->type != UBV) {
	            	arg2->type = value->type;
   	         	arg2->op = value->op;
      	      	if (debug) {
         	   		outstring(stdscr, "\n\r  dereferencing arg2 to ");
            			print_node(stdscr, arg2);
            		}
            	}
            }

            /* Dereference symbols down to a base object */
            while (arg2->type == SYM) {
               node *def = arg2->op.sym->def.user;
               if (def != NULL) {
                  if (def->class & HEAD) {
                     arg2->type = def->type;
                     arg2->op = def->op;
                  }
                  else {
                     arg2->type = PTR;
                     arg2->op.addr = def;
                     if (arg1->type == PTR) {
                        *(stack+1) = *stack;
                        (stack++)->ptr = env;
                     }
                     else (++stack)->ptr = env;
                  }
                  if (debug) {
                     outstring(stdscr, "\n\r  dereferencing arg2 to ");
                     print_node(stdscr, arg2);
                  }
               }
               else break;
            }
            while (arg1->type == SYM) {
               node *def = arg1->op.sym->def.user;
               if (def != NULL) {
                  if (def->class & HEAD) {
                     arg1->type = def->type;
                     arg1->op = def->op;
                  }
                  else {
                     arg1->type = PTR;
                     arg1->op.addr = def;
                     (++stack)->ptr = env;
                  }
                  if (debug) {
                     outstring(stdscr, "\n\r  dereferencing arg1 to ");
                     print_node(stdscr, arg1);
                  }
               }
               else break;
            }
         
            /* If the two arguments are identical, return TRUE */
            if (nodes_equal(&arg1, &arg2, FALSE)) {
               if (debug) {
                  outstring(stdscr, "\n\r  Nodes are identical, fire TRUE");
                  wrefresh(stdscr);
               }
               make_result(arg2, true);
					return;
            }

            /* If both arguments are UBVs, bind latest to earliest */
            /* UBV's are represented by EP's at this point   */
            if ((arg1->type == EP) && (arg2->type == EP)) {
            	if (debug) {
            		outstring(stdscr, "\n\r binding vars to each other, FIRE TRUE");
            		wrefresh(stdscr);
            	}
					if (arg1->op.addr->op.index > arg2->op.addr->op.index)
						bind_var(arg2, arg1, env);
            	else
						bind_var(arg1, arg2, env);
            	make_result(arg2, true);
            	return;
            }
         
            /* If one argument is a UBV, then bind it to the other. */
            if (arg1->type == EP) {
			   	if (((arg2->type == PTR) || (arg2->type == CLOSURE)) &&
						 lazy_occurs(arg1->op.addr->op.index, arg2->op.addr, env, 0)) {
						if (arg2->type == PTR) --stack;
			   		make_result(arg2, false);
   					return;
			   	}
            	if (debug) {
            		outstring(stdscr, "\n\r  binding arg1 to arg2, FIRE TRUE");
            		wrefresh(stdscr);
            	}
            	bind_var(arg1, arg2, (arg2->type == PTR) ? (stack--)->ptr : env);
					make_result(arg2, true);
					return;
				}
				if (arg2->type == EP) {
			   	if (((arg1->type == PTR) || (arg1->type == CLOSURE)) &&
						 lazy_occurs(arg2->op.addr->op.index, arg1->op.addr, env, 0)) {
						if (arg1->type == PTR) --stack;
			   		make_result(arg2, false);
			   		return;
			   	}
            	if (debug) {
            		outstring(stdscr, "\n\r  binding arg2 to arg1, FIRE TRUE");
            		wrefresh(stdscr);
            	}
            	bind_var(arg2, arg1, (arg1->type == PTR) ? (stack--)->ptr : env);
					make_result(arg2, true);
					return;
				}

         
            /* If one argument is atomic and the other points to a lambda,  */
            /* there is no way they can be unified.  */
            if ((atomic(arg1) &&
                 (((arg2->type == PTR) && (arg2->op.addr->type == LAMBDA)) ||
                  ((arg2->type == CLOSURE) && (arg2->op.addr->type == CL_PTR) &&
                   (arg2->op.addr->op.addr->type == LAMBDA))))
                   ||
                ((atomic(arg2) &&
                 (((arg1->type == PTR) && (arg1->op.addr->type == LAMBDA)) ||
                  ((arg1->type == CLOSURE) && (arg1->op.addr->type == CL_PTR) &&
                   (arg1->op.addr->op.addr->type == LAMBDA)))))) {
               if (debug) {
                  outstring(stdscr, "\n\r  atomic Vs. lambda, fire FALSE");
                  wrefresh(stdscr);
               }
               if ((atomic(arg1) && (arg2->type == PTR)) ||
                   (atomic(arg2) && (arg1->type == PTR))) {
                  --stack;  /* pop env off stack */
                   }
					make_result(arg2, false);
               return;
            }
       
            /* If either argument is a PTR or CLOSURE, then reduce the arguments */
            /* and apply UNIFY*  */ 
            if ((arg1->type == PTR) || (arg1->type == CLOSURE) ||
                (arg2->type == PTR) || (arg2->type == CLOSURE)) {
               if (debug) {
                  outstring(stdscr, "\n\r  reducing both arguments first");
                  wrefresh(stdscr);
               }
               inst_inert();
               ++ws;       /* leave a space for extra unify* arg later */
               primitive = pc + 1;
               prim_args = 2;
               return;
            }
         
         
            /* If none of the above is true, the two args cannot be unified */
            if (debug) {
               outstring(stdscr, "\n\r  args cannot be unified, firing FALSE");
               wrefresh(stdscr);
            }
				make_result(arg2, false);
            return;
         }

      case RESULT:
         {
         	node *arg2 = pc+1;
         	node *arg1 = pc+2;
         	
            /* convert over to a UNIFY* instruction and invoke. */
            if (reductions == red_limit) return;
            if (debug) {
               outstring(stdscr, "\n\r  converting to a unify*");
               wrefresh(stdscr);
            }
            primitive->class = APPLY; primitive->type = INT;
            primitive->op.intval = binding_offset;
            (++primitive)->class = HEAD; primitive->type = PRIM_0;
            primitive->op.sym = unify_star;
            pc = primitive;
            if (binding_offset > 0) {
					/* A new environment that will have indefinite lifetime	*/
					/* must now be created for the args in the heap area.		*/
					int i = binding_offset;
					node *eptr = env, *hptr = heap + 1;

					if (debug) {
						outstring(stdscr, "\n\r    Building new environment:");
						wrefresh(stdscr);
					}
					while (i-- > 0) {
						(++heap)->class = HEAD; heap->type = IP;
						while (eptr->type != UBV) {
							if (eptr->type == MARKER) eptr = eptr->op.addr;
							else if ((eptr->type == IP) &&
										(eptr->op.addr->type == UBV))
								break;
							else ++eptr;
						}
						heap->op.addr = eptr++;
					}
					if (arg1->type == PTR) (++stack)->ptr = hptr;
					if (arg2->type == PTR) (++stack)->ptr = hptr;
					env = hptr;
					if (debug) { print_mem(stdscr, hptr, heap); }
				}
				else {				
					if (arg1->type == PTR) (++stack)->ptr = env;
					if (arg2->type == PTR) (++stack)->ptr = env;
				}
            return;
         }
   }
}





/* UNIFY_STAR
/* After both args have been reduced, try to unify them.
/* There will always be env pointers on the stack for each PTR arg.
*/

void prim_unify_star()
{
   node *arg1, *arg2, *res, *uwrap_lambdas();
   int scope;

   if (debug) {
   	outstring(stdscr, "\n\rprim_unify_star: ");
   	wrefresh(stdscr);
   }

   if (mode == HEADM) {
      inst_inert();
      pc = pc+1;
      primitive = pc;
   }

   scope = (--pc)->op.intval;
   arg1 = (--pc);
   arg2 = (--pc);
   res = pc;

   if (debug) {
      foutstring(stdscr, "scope = %d, arg1 (%p) = ", scope, arg1);
      print_node(stdscr, arg1);
      foutstring(stdscr, ",  arg2 (%p) = ", arg2);
      print_node(stdscr, arg2);
   }
   

   if (reductions == red_limit) {
      if (debug) {
         outstring(stdscr, "\n\r  NOT FIRING, red_limit");
         wrefresh(stdscr);
      }
      if (arg1->type == PTR) --stack;
      if (arg2->type == PTR) --stack;
      /* Undo any EP's that may have formed */
      if (arg1->type == EP) {
      	arg1->type = VAR; arg1->op.index = scope - arg1->op.addr->op.index;
      }
      if (arg2->type == EP) {
      	arg2->type = VAR; arg2->op.index = scope - arg2->op.addr->op.index;
      }
		/* Wrap args in lambdas if neccessary */
		if (scope > binding_offset) {
	      arg1->op.addr = uwrap_lambdas(scope - binding_offset, arg1);
   	   arg1->type = PTR;
      	arg2->op.addr = uwrap_lambdas(scope - binding_offset, arg2);
	      arg2->type = PTR;
	   }
		/* change back to a UNIFY instruction */
		(arg1+1)->class = HEAD; (arg1+1)->type = PRIM_0; (arg1+1)->op.sym = unify;
      pc = res - 1;
      return;
   }

   /* Dereference any variables */
   if (arg1->type == VAR) {
   	node *value = lookup(env, arg1->op.index);
   	if (value->type == UBV) {
   		arg1->type = EP; arg1->op.addr = value;
   	}
   	else {
   		arg1->type = value->type; arg1->op = value->op;
   	}
   	if (debug) {
   		outstring(stdscr, "\n\r  dereferencing arg1 to ");
   		print_node(stdscr, arg1);
   	}
   }
   if (arg2->type == VAR) {
   	node *value = lookup(env, arg2->op.index);
   	if (value->type == UBV) {
   		arg2->type = EP; arg2->op.addr = value;
   	}
   	else {
   		arg2->type = value->type; arg2->op = value->op;
   	}
   	if (debug) {
   		outstring(stdscr, "\n\r  dereferencing arg2 to ");
   		print_node(stdscr, arg2);
   	}
   }

   /* check if args are identical */
   if (nodes_equal(&arg1, &arg2, TRUE)) {
      if (debug) {
         outstring(stdscr, "\n\r  FIRING true, identical args");
         wrefresh(stdscr);
      }
      if (arg1->type == PTR) --stack;
      if (arg2->type == PTR) --stack;
      make_result(res, true);
      return;
   }

   /* check to see if both args are variables */
   if ((arg1->type == EP) && (arg2->type == EP)) {
   	int index1 = binding_offset - arg1->op.addr->op.index;
   	int index2 = binding_offset - arg2->op.addr->op.index;
		if ((index1 < 0) || (index2 < 0)) {
			if (debug) {
				outstring(stdscr, "\n\r  FAILURE, scope violation");
				wrefresh(stdscr);
			}
			make_result(res, false);
			return;
	  	}
	  	else {
	  		if (debug) {
	  			outstring(stdscr, "\n\r  SUCCESS, binding vars to each other");
	  			wrefresh(stdscr);
	  		}
	  		if (index1 > index2) bind_var(arg2, arg1, env);
	  		else bind_var(arg1, arg2, env);
	  		make_result(res, true);
	  		return;
	  	}
   }

   /* If either arg is a variable, try to bind it to other arg */
   if (arg1->type == EP) {
   	if (arg1->op.addr->op.index > binding_offset) {
   		if (debug) {
   			outstring(stdscr, "\n\r  FAILURE,  attempting to bind an inside var");
   			wrefresh(stdscr);
   		}
			if (arg2->type == PTR) --stack;
   		make_result(res, false);
   		return;
		}   		
   	if (((arg2->type == PTR) || (arg2->type == CLOSURE)) &&
			 lazy_occurs(arg1->op.addr->op.index, arg2->op.addr, env, 0)) {
			if (arg2->type == PTR) --stack;
   		make_result(res, false);
   		return;
   	}
   	else {
   		node *temp = ++heap;
   		node *copy_graph();
   		if (arg2->type == PTR) {
   			if (debug) {
   				foutstring(stdscr, "\n\r   copying arg2 (%p) to (%p)", arg2->op.addr, heap);
   				wrefresh(stdscr);
   			}
   			heap = copy_graph(arg2->op.addr, temp);
   			arg2->op.addr = temp;
   			if (debug) { print_mem(stdscr, temp, heap); }
   		}
   		bind_var(arg1, arg2, (arg2->type == PTR) ? (stack--)->ptr : env);
   		make_result(res, true);
   		return;
   	}
   }
   if (arg2->type == EP) {
		if (arg2->op.addr->op.index > binding_offset) {
   		if (debug) {
   			outstring(stdscr, "\n\r  FAILURE,  attempting to bind an inside var");
   			wrefresh(stdscr);
   		}
			if (arg1->type == PTR) --stack;
   		make_result(res, false);
   		return;
		}
   	if (((arg1->type == PTR) || (arg1->type == CLOSURE)) &&
			 lazy_occurs(arg2->op.addr->op.index, arg1->op.addr, env, 0)) {
			if (arg1->type == PTR) --stack;
   		make_result(res, false);
   		return;
   	}
   	else {
   		node *temp = ++heap;
   		node *copy_graph();
   		if (arg1->type == PTR) {
   			if (debug) {
   				foutstring(stdscr, "\n\r   copying arg1 (%p) to (%p)", arg1->op.addr, heap);
   				wrefresh(stdscr);
   			}
   			heap = copy_graph(arg1->op.addr, temp);
   			arg1->op.addr = temp;
   			if (debug) { print_mem(stdscr, temp, heap); }
   		}
   		bind_var(arg2, arg1, (arg1->type == PTR) ? (stack--)->ptr : env);
   		make_result(res, true);
   		return;
   	}
   }

   /* If either arg is a closure, promote it to a pointer 	*/
   /* The closure env is the same as the current env. 		*/
   if (arg1->type == CLOSURE) {
   	(++stack)->ptr = (arg1->op.addr+1)->op.addr;   	
   	arg1->type = PTR; arg1->op.addr = arg1->op.addr->op.addr;
   	if (debug) {
   		outstring(stdscr, "\n\r   promoting arg1 closure to a PTR");
   		wrefresh(stdscr);
   	}
   }
   if (arg2->type == CLOSURE) {
   	(++stack)->ptr = (arg2->op.addr+1)->op.addr;
   	arg2->type = PTR; arg2->op.addr = arg2->op.addr->op.addr;
   	if (debug) {
   		outstring(stdscr, "\n\r   promoting arg2 closure to PTR");
   		wrefresh(stdscr);
   	}
   }
   
   
   /* if args not pointers, then they cannot be unified */
   if ((arg1->type != PTR) || (arg2->type != PTR)) {
      if (debug) {
         outstring(stdscr, "\n\r  FIRING false, args not same");
         wrefresh(stdscr);
      }
		if (arg1->type == PTR) --stack;
		if (arg2->type == PTR) --stack;
      make_result(res, false);
      return;
   }

   /* split up pointers */
   if ((arg1->op.addr->class == APPLY) && (arg2->op.addr->class == APPLY)) {
		node *start = ws+1;
      if (debug) {
         outstring(stdscr, "\n\r  splitting an ap");
         wrefresh(stdscr);
      }
      stack -= 2;
      
      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 3;
      pc = ws;
      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 6;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;

      *(++ws) = *(arg1->op.addr);
      *(++ws) = *(arg2->op.addr);
      (++ws)->class = APPLY; ws->type = INT; ws->op.intval = scope;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = unify_star;

      if ((arg1->op.addr+1)->class == HEAD) {
      	*(++ws) = *(arg1->op.addr+1); ws->class = APPLY;
      }
      else {
      	(++ws)->class = APPLY; ws->type = PTR; ws->op.addr = arg1->op.addr + 1;
		}
		if ((arg2->op.addr+1)->class == HEAD) {
			*(++ws) = *(arg2->op.addr+1); ws->class = APPLY;
		}
		else {
      	(++ws)->class = APPLY; ws->type = PTR; ws->op.addr = arg2->op.addr + 1;
      }
      (++ws)->class = APPLY; ws->type = INT; ws->op.intval = scope;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = unify_star;

      (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = res;
      res->class = HEAD;

		if (debug) print_mem(stdscr, start, ws);
			      
      jump_subgraph();
      mode = PROBLEM;
		++reductions;
      return;
   }     

   /* Both args are lazy structures */
   if ((arg1->op.addr->type == LAMBDA) && (arg1->op.addr->class & PAIR) &&
       (arg2->op.addr->type == LAMBDA) && (arg2->op.addr->class & PAIR)) {
      int len1 = 0, len2 = 0;
      node *temp;
      if (debug) {
         outstring(stdscr, "\n\r  both args are lazy structures");
         wrefresh(stdscr);
      }
      stack -= 2;
      ++scope;
      
      /* Check if the tags are different */
      if (arg1->op.addr->op.sym != arg2->op.addr->op.sym) {
         if (debug) {
            outstring(stdscr, "\n\r  FIRING FALSE, different tags");
            wrefresh(stdscr);
         }
         make_result(res, false);
         return;
      }

      /* check the length of both structures */
      for (temp=(arg1->op.addr)+1; temp->class != HEAD; temp++, len1++);
      for (temp=(arg2->op.addr)+1; temp->class != HEAD; temp++, len2++);
      if (len1 != len2) {
         if (debug) {
            foutstring(stdscr, "\n\r  FIRING FALSE, different lengths - %d and %d", len1, len2);
            wrefresh(stdscr);
         }
			make_result(res, false);
         return;
      }

      /* build new unification graph */
      if (debug) {
         outstring(stdscr, "\n\r  building new unification graph");
         wrefresh(stdscr);
      }
      pc = ws + 1;
      arg1 = arg1->op.addr;
      arg2 = arg2->op.addr;
      ws += len1;
      temp = pc;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;
      while (len1-- > 0) {
         /* put in pointer to unification graph */
         temp->class = APPLY; temp->type = PTR; temp->op.addr = ws + 1;
         ++temp;
         /* build new unification graph */
         *(++ws) = *(++arg2); ws->class = APPLY; 
         *(++ws) = *(++arg1); ws->class = APPLY; 
         (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = unify;
      }
      (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = res;
      res->class = HEAD;
      if (debug) print_mem(stdscr, temp-len2, ws);
      push_marker();
/*      env->class = HEAD; env->type = UBV; env->op.index = scope; */
		if (debug) {
			outstring(stdscr, "\n\r top of env looks like:");
			print_mem(stdscr, env, env+3);
		}
      
      jump_subgraph();
      ++reductions;
      mode = PROBLEM;
      return;

   }


   /* Both args are lambdas */
   if ((arg1->op.addr->type == LAMBDA) && (arg2->op.addr->type == LAMBDA)) {
      if (debug) {
         outstring(stdscr, "\n\r  both args lambdas, updating in place");
         wrefresh(stdscr);
      }
      push_marker();
      env->class = HEAD; env->type = UBV; env->op.index = ++scope;
      (primitive-1)->op.index = scope;
      ++(arg1->op.addr);
      if (arg1->op.addr->class == HEAD) {
			*arg1 = *(arg1->op.addr);
			arg1->class = APPLY;
			--stack;
		}
      ++(arg2->op.addr);
      if (arg2->op.addr->class == HEAD) {
			*arg2 = *(arg2->op.addr);
			arg2->class = APPLY;
			--stack;
		}
      pc = primitive;
		if (debug) {
			foutstring(stdscr, "\n\r pc = (%p) ", pc);
			print_node(stdscr, pc);
		}
      return;
   }

   if (debug) {
      outstring(stdscr, "\n\r  unify* -- NOT HANDLED");
      wrefresh(stdscr);
   }
}




/* MAKE_RESULT
/* Make the RESult node into a VAL head symbol, clean up for exit of
/* primitive.
*/

void make_result(res, val)
node *res;
symbol *val;
{
	res->class = HEAD; res->type = SYM; res->op.sym = val;
	ws = res;
   ++reductions;
   pc = ws - 1;
   mode = RESULT;
}


/* UNDO_BINDINGS
/* Undo any bindings stred in the reset stack, from reset_ptr to PTR.
*/

void undo_bindings(ptr)
reset *ptr;
{
	if (debug) {
		foutstring(stdscr, "\n\rundo_bindings: from reset_ptr (%p) to ptr (%p)",
				reset_ptr, ptr);
		wrefresh(stdscr);
	}
	while (reset_ptr != ptr) {
		reset_ptr->addr->class = HEAD;
		reset_ptr->addr->type = UBV;
		reset_ptr->addr->op.index = reset_ptr->val;
		if (debug) {
			foutstring(stdscr, "\n\r   reset cell %p to ", reset_ptr->addr);
			print_node(stdscr, reset_ptr->addr);
		}
		--reset_ptr;
	}
}



/* OCCURS
/* Checks for occurences of VAR in GRAPH, like the usual occur check,
/* but because this is unification of quantified terms, it must check
/* to see if any scope violations occur.
*/

int lazy_occurs(var, graph, env, lambdas)
int var, lambdas;
node *graph, *env;
{
#ifdef DEBUG_OCCURS
	if (debug) {
		foutstring(stdscr, "\n\rlazy_occurs(%d, %p, %p, %d),  graph node = ",
			var, graph, env, lambdas);
		print_node(stdscr, graph);
	}
#endif

	if (graph->type == VAR) {
		node *value;
		if (graph->op.index >= lambdas)
			value = lookup(env, graph->op.index - lambdas);
		else
			value = graph;
			
		if (value->type == UBV) {
			if (var == value->op.index) {
				if (debug) {
					outstring(stdscr, "\n\r     OCCUR CHECK FAILS, var occurs in binding");
					wrefresh(stdscr);
				}
				return(TRUE);
			}
			if (value->op.index > binding_offset) {
				if (debug) {
					outstring(stdscr, "\n\r   OCCUR CHECK FAILS, scope mismatch");
					wrefresh(stdscr);
				}
				return(TRUE);
			}
		}
		if (atomic(value)) {
			if (graph->class == HEAD) return(FALSE);
			else return(lazy_occurs(var, graph+1, env, lambdas));
		}
		return((lazy_occurs(var, graph+1, env, lambdas) ||
				  lazy_occurs(var, value, env, lambdas)));
	}


	if (graph->type == PTR) {
		if (graph->class == HEAD)
			return(lazy_occurs(var, graph->op.addr, env, lambdas));
		else
			return((lazy_occurs(var, graph+1, env, lambdas) ||
			  		  lazy_occurs(var, graph->op.addr, env, lambdas)));
	}

	if (graph->type == CLOSURE) {
		if (graph->class == HEAD)
			return(lazy_occurs(var, graph->op.addr, ((graph->op.addr)+1)->op.addr, lambdas));
		else
			return((lazy_occurs(var, graph+1, env, lambdas) ||
					  lazy_occurs(var, graph->op.addr, ((graph->op.addr)+1)->op.addr)), lambdas);
		}

	if (graph->type == CL_PTR)
		return(lazy_occurs(var, graph->op.addr, (graph+1)->op.addr, lambdas));
		
	if (graph->type == LAMBDA)	return(lazy_occurs(var, graph+1, env, ++lambdas));

	if	(atomic(graph)) {
		if (graph->class == HEAD) return(FALSE);
		else return(lazy_occurs(var, graph+1, env, lambdas));
	}

	outstring_ns(stdscr, "\n\r LAZY OCCUR CHECK, END OF LINE, ERROR!!!");
	wrefresh(stdscr);
}



/* UWRAP_LAMBDAS
/* Wrap an expression in N lambda bindings.
*/

node *uwrap_lambdas(n, exp)
int n;
node *exp;
{
   node *new_exp = ws + 1;
   
   while (n-- > 0) {
      (++ws)->class = BINDER; ws->type = LAMBDA; ws->op.sym = genvar;
   }
   *(++ws) = *exp;
   ws->class = HEAD;
	return(new_exp);
}

