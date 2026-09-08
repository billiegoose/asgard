/* Unification primitive for HORSE.
/* Mike Hilton, 6 Dec 89
*/

#define DEBUG_OCCURS

#include <stdio.h>
#include <curses.h>
#include "lrs.h"

extern node *ws, *pc, *env, *primitive, *fs, *heap, *ex_ptr;
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
	if (!atomic(ws-1)) {
		node *temp, *copy_graph();
		temp = heap + 1;
		build_env_in_heap((stack--)->ptr, binding_offset);
		(++stack)->ptr = temp;
		temp = ++heap;
		heap = copy_graph((ws-1)->op.addr, temp);
   	(ws-1)->op.addr = temp;
		occurs(lookup(ws->op.addr, 0), (ws-1)->op.addr, stack->ptr, 0);
	}
	bind_var(ws, ws-1, ((ws-1)->type == PTR) ? (stack--)->ptr : env);
	make_result(ws-1, neutral);
	--reductions;
	return;
}

	

/* BIND_VAR
/* Bind the variable indicated by VAR to VALUE.  If a closure must
/* be created, it is built on the heap.
*/

void bind_var(var, value, env)
node *var, *value, *env;
{
	var = lookup(var->op.addr, 0);

	if (var->type == EX_VAR) {
		(++reset_ptr)->val = (var+2)->op.index;
		reset_ptr->class = VAR;
		reset_ptr->addr = var;
	}
	else {
		(++reset_ptr)->val = var->op.index;
		reset_ptr->class = UBV;
		reset_ptr->addr = var;
	}
	
	if (value->type == PTR) {
		var->type = CLOSURE;	var->op.addr = ++heap;
		heap->type = CL_PTR; heap->op.addr = value->op.addr;
		(++heap)->type = CL_ENV; heap->op.addr = env;
	}
	else if ((value->type == EP) || (value->type == EX_VAR)) {
		value = lookup(value->op.addr, 0);
		if (value == var) {  /* binding a variable to itself is a no-no */
			--reset_ptr;
			return;
		}
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
	node *spine = ws + pairs + 4;
	node *new_pc;
	reset *resetval = ptr;

	if (debug) {
		foutstring(stdscr, "\n\rinsert_binding_pairs(%p, %p, %p, %d)", ptr, anchor, head, before);
		wrefresh(stdscr);
	}
	if (pairs == 0) return(pc);
	if (debug) {
		foutstring(stdscr, "\n\r  building binding graph from %p to %p", reset_ptr, ptr);
		wrefresh(stdscr);
	}

	spine->class = HEAD; spine->type = PTR; spine->op.addr = head;
	if (before) {
		*(spine-1) = *anchor;
		new_pc = spine - 2;
	}
	else {
		new_pc = spine - 1;
	}

	ws = spine;
	if (before) --spine;

	ptr = reset_ptr;
	while (pairs-- > 0) {
		if ((ptr->class == UBV) && (ptr->val <= binding_offset)) {
			(--spine)->class = APPLY; spine->type = PTR; spine->op.addr = ws+1;
			*(++ws) = *(lookup(ptr->addr, 0));
			ws->class = APPLY;
			(++ws)->class = APPLY; ws->type = INT;
			ws->op.intval = binding_offset - ptr->val;
			(++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = bind;
			(++stack)->ptr = env;
		}
		else if ((ptr->class == VAR) && (ptr->val <= binding_offset)) {
			(--spine)->class = APPLY; spine->type = PTR; spine->op.addr = ws+1;
			*(++ws) = *(lookup(ptr->addr, 0));
			ws->class = APPLY;
			(++ws)->class = APPLY; ws->type = EX_VAR;
			ws->op.addr = ptr->addr;
			(++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = bind;
			(++stack)->ptr = env;
		}	
		else {
			if (debug) {
				foutstring(stdscr, "\n\r      Not doing %p: ", ptr);
				switch (ptr->class) {
					case IP: 		outstring(stdscr, "IP "); break;
					case EX_VAR:	outstring(stdscr, "EX_VAR "); break;
					case VAR:		outstring(stdscr, "VAR "); break;
					default:			outstring(stdscr, "!!unexpected type!!"); break;
				}
				foutstring(stdscr, "val = %d, addr = %p", ptr->val, ptr->addr);
			}
		}
		--ptr;
	}
	if (! before) *(--spine) = *anchor;
	(--spine)->class = CONTROL; spine->type = RESET; spine->op.rptr = resetval;
	(--spine)->class = CONTROL; spine->type = JOIN; spine->op.addr = anchor;
	anchor->class = HEAD; 
	if (debug) print_mem(stdscr, spine, ws);
	return(new_pc);
}








/* UNIFY
/* Unification predicate.  
*/

void prim_unify()
{
  	node *arg2 = pc+1;
  	node *arg1 = pc+2;

  	if (mode == HEADM) {
  		/* make sure there is one empty memory location after primitive	*/
  		/* for the scope to be inserted later.										*/
  		inst_inert();
  		ws++;
		primitive = pc + 1;
		prim_args = 2;
  		return;
  	}
  	
	if (debug) {
   	foutstring(stdscr, "\n\rprim_unify: arg1 (%p) = ", arg1);
      print_node(stdscr, arg1);
      foutstring(stdscr, "  arg2 (%p) = ", arg2);
      print_node(stdscr, arg2);
   }

   if (reductions == red_limit) {
      if (debug) {
         outstring(stdscr, "\n\r  NOT FIRING, red_limit");
         wrefresh(stdscr);
      }
   	return;
   }
         	
   /* convert over to a UNIFY* instruction and invoke. */
   if (debug) {
      outstring(stdscr, "\n\r  converting to a unify*");
      wrefresh(stdscr);
   }
   primitive->class = APPLY; primitive->type = INT;
   primitive->op.intval = binding_offset;
   (++primitive)->class = HEAD; primitive->type = PRIM_0;
   primitive->op.sym = unify_star;
   pc = primitive;
	(--aux)->rptr = reset_ptr;

            
   if (env->class & PAIR) {
   	/* When a lazy structure is forced by unification, the freezing 	*/
   	/* lambda must be thrown away.  This lambda is marked with PAIR.	*/
		++env;
		if (debug) {
			foutstring(stdscr, "\n\rPopping a PAIR UBV off the env; env now = %p", env);
			wrefresh(stdscr);
		}
	}
   if (binding_offset > 0) {
   	node *temp = heap + 1;
		build_env_in_heap(env, binding_offset);
		env = temp;
	}
   return;
}





/* UNIFY_STAR
/* After both args have been reduced, try to unify them.
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
		/* pop off stack entries if necessary */
		if (arg1->type == PTR) --stack;
		if (arg2->type == PTR) --stack;
		/* put a reset list ptr on aux */
		(--aux)->rptr = reset_ptr;
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
      ++aux; 		/* pop reset ptr */
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
      make_result(res, true);
      ++aux;
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
			undo_bindings((aux++)->rptr);
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
	  		++aux;
	  		return;
	  	}
   }

   /* Check to see if both args are EX_VARS */
   if ((arg1->type == EX_VAR) && (arg2->type == EX_VAR)) {
		if ((arg1+2)->op.index < (arg2+2)->op.index) {
			bind_var(arg2, arg1, env);
		}
		else {
			bind_var(arg1, arg2, env);
		}
		make_result(res, true);
		++aux;
		return;
	}
   		


   /* If either arg is a variable, try to bind it to other arg */
   if (arg1->type == EP) {
   	if (arg1->op.addr->op.index > binding_offset) {
   		if (debug) {
   			outstring(stdscr, "\n\r  FAILURE,  attempting to bind an inside var");
   			wrefresh(stdscr);
   		}
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);
   		return;
		}   		
   	if (((arg2->type == PTR) || (arg2->type == CLOSURE)) &&
			 occurs(arg1->op.addr, arg2->op.addr, env, 0)) {
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);   		
   		return;
   	}
   	if (arg2->type == EX_VAR) {
   		bind_var(arg1, arg2, env);
   		if (arg1->op.addr->op.index < (arg2+2)->op.index) {
   			(++reset_ptr)->val = (arg2+2)->op.index;
   			reset_ptr->class = EX_VAR;
				reset_ptr->addr = arg2;
   			(arg2+2)->op.index = arg1->op.addr->op.index;
   		}
   		make_result(res, true);
   		++aux;
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
   		bind_var(arg1, arg2, env);
   		make_result(res, true);
			++aux;
   		return;
   	}
   }


   if (arg2->type == EP) {
		if (arg2->op.addr->op.index > binding_offset) {
   		if (debug) {
   			outstring(stdscr, "\n\r  FAILURE,  attempting to bind an inside var");
   			wrefresh(stdscr);
   		}
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);
   		return;
		}
   	if (((arg1->type == PTR) || (arg1->type == CLOSURE)) &&
			 occurs(arg2->op.addr, arg1->op.addr, env, 0)) {
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);
   		return;
   	}
   	if (arg1->type == EX_VAR) {
   		bind_var(arg2, arg1, env);
   		if (arg2->op.addr->op.index < (arg1+2)->op.index) {
   			(++reset_ptr)->val = (arg1+2)->op.index;
   			reset_ptr->class = EX_VAR;
				reset_ptr->addr = arg1;
   			(arg1+2)->op.index = arg2->op.addr->op.index;
   		}
   		make_result(res, true);
   		++aux;
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
   		bind_var(arg2, arg1, env);
   		make_result(res, true);
   		++aux;
   		return;
   	}
   }

   /* If either arg is an EX_VAR */
   if (arg1->type == EX_VAR) {
   	if (((arg2->type == PTR) || (arg2->type == CLOSURE)) &&
			 occurs(arg1->op.addr, arg2->op.addr, env, 0)) {
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);
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
   		bind_var(arg1, arg2, env);
   		make_result(res, true);
   		++aux;
   		return;
   	}
   }


   if (arg2->type == EX_VAR) {
   	if (((arg1->type == PTR) || (arg1->type == CLOSURE)) &&
			 occurs(arg2->op.addr, arg1->op.addr, env, 0)) {
   		make_result(res, false);
   		undo_bindings((aux++)->rptr);
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
   		bind_var(arg2, arg1, env);
   		make_result(res, true);
   		++aux;
   		return;
   	}
   }
   	




   /* If either arg is a closure, promote it to a pointer 	*/
   /* The closure env is the same as the current env. 		*/
   if (arg1->type == CLOSURE) {
   	arg1->type = PTR; arg1->op.addr = arg1->op.addr->op.addr;
   	if (debug) {
   		outstring(stdscr, "\n\r   promoting arg1 closure to a PTR");
   		wrefresh(stdscr);
   	}
   }
   if (arg2->type == CLOSURE) {
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
      make_result(res, false);
  		undo_bindings((aux++)->rptr);
      return;
   }

   /* split up pointers */
   if ((arg1->op.addr->class == APPLY) && (arg2->op.addr->class == APPLY)) {
		node *start = ws+1;
      if (debug) {
         outstring(stdscr, "\n\r  splitting an ap");
         wrefresh(stdscr);
      }

      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 3;
      pc = ws;
      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 6;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;

      *(++ws) = *(arg1->op.addr);
      *(++ws) = *(arg2->op.addr);
      (++ws)->class = APPLY; ws->type = INT; ws->op.intval = scope;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = unify_star;

      if ((arg1->op.addr+1)->class & HEAD) {
      	*(++ws) = *(arg1->op.addr+1); ws->class = APPLY;
      }
      else {
      	(++ws)->class = APPLY; ws->type = PTR; ws->op.addr = arg1->op.addr + 1;
		}
		if ((arg2->op.addr+1)->class & HEAD) {
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
		++aux;
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
      ++scope;
      
      /* Check if the tags are different */
      if (arg1->op.addr->op.sym != arg2->op.addr->op.sym) {
         if (debug) {
            outstring(stdscr, "\n\r  FIRING FALSE, different tags");
            wrefresh(stdscr);
         }
         make_result(res, false);
   		undo_bindings((aux++)->rptr);
         return;
      }

      /* check the length of both structures */
      for (temp=(arg1->op.addr)+1; !(temp->class & HEAD); temp++, len1++);
      for (temp=(arg2->op.addr)+1; !(temp->class & HEAD); temp++, len2++);
      if (len1 != len2) {
         if (debug) {
            foutstring(stdscr, "\n\r  FIRING FALSE, different lengths - %d and %d", len1, len2);
            wrefresh(stdscr);
         }
			make_result(res, false);
   		undo_bindings((aux++)->rptr);
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
      env->class = HEAD | PAIR; env->type = UBV; env->op.index = scope;
		if (debug) {
			outstring(stdscr, "\n\r top of env looks like:");
			print_mem(stdscr, env, env+3);
		}
      
      jump_subgraph();
      ++reductions;
      mode = PROBLEM;
		++aux;
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
		}
      ++(arg2->op.addr);
      if (arg2->op.addr->class == HEAD) {
			*arg2 = *(arg2->op.addr);
			arg2->class = APPLY;
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
   if (debug) {
      outstring(stdscr, "\n\r  FIRING false, args not same");
      wrefresh(stdscr);
   }
   make_result(res, false);
	undo_bindings((aux++)->rptr);
   return;

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
/* Undo any bindings stored in the reset stack, from reset_ptr to PTR.
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
		reset_ptr->addr->class = HEAD | UNBOUND;
		if ((reset_ptr->class == EX_VAR) || (reset_ptr->class == VAR)) {
			reset_ptr->addr->type = EX_VAR;
			reset_ptr->addr->op.addr = reset_ptr->addr;
			(reset_ptr->addr+2)->op.index = reset_ptr->val;
		}
		else {
			reset_ptr->addr->type = UBV;
			reset_ptr->addr->op.index = reset_ptr->val;
		}
		
		if (debug) {
			foutstring(stdscr, "\n\r   reset cell %p to ", reset_ptr->addr);
			print_node(stdscr, reset_ptr->addr);
		}
		--reset_ptr;
	}
}



/* OCCURS
/* Checks for occurences of VAR in GRAPH, like the usual occur check,
/* but because this is unification of quantified terms, it must also check
/* to see if any scope violations occur.
*/
int occurs(variable, graph, env, lambdas)
int lambdas;
node *variable, *graph, *env;
{
	reset *res = reset_ptr;

	if (occurs1(variable, graph, env, lambdas)) {
		undo_bindings(res);
		if (debug) {
			outstring(stdscr, "\n\rOccurs returning TRUE");
			wrefresh(stdscr);
		}
		return(TRUE);
	}
	else {
		if (debug) {
			outstring(stdscr, "\n\rOccurs returning FALSE");
			wrefresh(stdscr);
		}
		return(FALSE);
	}
}

int occurs1(var, graph, env, lambdas)
int lambdas;
node *graph, *env, *var;
{
#ifdef DEBUG_OCCURS
	if (debug) {
		foutstring(stdscr, "\n\roccurs1(%p, %p, %p, %d),  graph node = ",
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

		if (value->type == EX_VAR) {
			if ((var->type == EX_VAR) && (var->op.addr == value->op.addr)) {
				if (debug) {
					outstring(stdscr, "\n\r     OCCUR CHECK FAILS, EX-var occurs in binding");
					wrefresh(stdscr);
				}
				return(TRUE);
			}
			if ((var->type == UBV) && (var->op.index < (value+2)->op.index)) {
				if (debug || 1) {
					foutstring(stdscr, "\n\r   EX_VAR: scope needs to be RE-lifted from %d to %d",
						(value+2)->op.index, var->op.index);
					wrefresh(stdscr);
				}
				/* put ex_var on reset list so that if binding doesn't work out */
				/* the old index is restored */
				(++reset_ptr)->val = (value+2)->op.index;
				reset_ptr->class = EX_VAR;
				reset_ptr->addr = value;
				(value+2)->op.index = var->op.index;
				add_to_exlist(var, value);
			}
		}
			
		if (value->type == UBV) {
			if ((var->type == UBV) && (var->op.index == value->op.index)) {
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
			if ((var->type == UBV) && (value->op.index  > var->op.index)) {
				if (debug || 1) {
					foutstring(stdscr, "\n\r   EXISTENTIAL VAR: scope needs to be lifted from %d to %d",
						value->op.index, var->op.index);
					wrefresh(stdscr);
				}
				/* Mark the ubv as needing to be lifted and keep track of 	*/
				/* the outermost scope where it should be lifted to.			*/
				(++reset_ptr)->val = value->op.index;
				reset_ptr->class = EX_VAR;
				reset_ptr->addr = value;
				value->type = EX_VAR; value->op.addr = value;
				(value+2)->op.index = var->op.index;
				add_to_exlist(var, value);
			}
		}
		if (atomic(value)) {
			if (graph->class & HEAD) return(FALSE);
			else return(occurs1(var, graph+1, env, lambdas));
		}
		return((occurs1(var, graph+1, env, lambdas) ||
				  occurs1(var, value, env, lambdas)));
	}


	if (graph->type == EX_VAR) {
		if ((var->type == EX_VAR) && (var->op.addr == graph->op.addr)) {
			if (debug) {
				outstring(stdscr, "\n\r     OCCUR CHECK FAILS, EX-var occurs in binding");
				wrefresh(stdscr);
			}
			return(TRUE);
		}
		if ((var->type == UBV) && (var->op.index < (graph->op.addr+2)->op.index)) {
			if (debug || 1) {
				foutstring(stdscr, "\n\r   EX_VAR: scope needs to be RE-lifted from %d to %d",
					(graph->op.addr+2)->op.index, var->op.index);
				wrefresh(stdscr);
			}
			/* put ex_var on reset list so that if binding doesn't work out */
			/* the old index is restored */
			(++reset_ptr)->val = (graph->op.addr+2)->op.index;
			reset_ptr->class = EX_VAR;
			reset_ptr->addr = graph->op.addr;
			(graph->op.addr+2)->op.index = var->op.index;
			add_to_exlist(var, graph->op.addr);
		}
	}

	if (graph->type == PTR) {
		if (graph->class & HEAD)
			return(occurs1(var, graph->op.addr, env, lambdas));
		else
			return((occurs1(var, graph+1, env, lambdas) ||
			  		  occurs1(var, graph->op.addr, env, lambdas)));
	}

	if (graph->type == CLOSURE) {
		if (graph->class & HEAD)
			return(occurs1(var, graph->op.addr, ((graph->op.addr)+1)->op.addr, lambdas));
		else
			return((occurs1(var, graph+1, env, lambdas) ||
					  occurs1(var, graph->op.addr, ((graph->op.addr)+1)->op.addr)), lambdas);
		}

	if (graph->type == CL_PTR)
		return(occurs1(var, graph->op.addr, (graph+1)->op.addr, lambdas));
		
	if (graph->type == LAMBDA)	return(occurs1(var, graph+1, env, ++lambdas));

	if	(atomic(graph)) {
		if (graph->class & HEAD) return(FALSE);
		else return(occurs1(var, graph+1, env, lambdas));
	}

	outstring_ns(stdscr, "\n\r OCCUR CHECK, END OF THE LINE, ERROR!!!");
	wrefresh(stdscr);
	return(TRUE);
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


int add_to_exlist(binder, exvar)
node *binder, *exvar;
{
	if (!(binder->class & EXISTS)) {
		/* binder currently has no ex-vars on its ex-list */
		binder->class = binder->class | EXISTS;
		(--ex_ptr)->type = STOP;
		*(--ex_ptr) = *exvar;
		(binder+2)->type = EX_LIST; (binder+2)->op.addr = ex_ptr;
	}
	else {
		/* add this exvar to the binder's list */
		(--ex_ptr)->type = MARKER; ex_ptr->op.addr = (binder+2)->op.addr;
		*(--ex_ptr) = *exvar;
		(binder+2)->op.addr = ex_ptr;
	}
}



build_env_in_heap(environment, size)
node *environment;
int size;
{
	/* A new environment that will have indefinite lifetime	*/
	/* must now be created for the expression in the heap area.		*/
	int i = size;
	node *eptr = environment;
	if (debug) {
		outstring(stdscr, "\n\r build_env_in_heap(%p, %d)", environment, size);
		wrefresh(stdscr);
	}
	while (i-- > 0) {
		while ((eptr->class & UNBOUND) == 0) {
			if (eptr->type == MARKER) eptr = eptr->op.addr;
/*			else if (eptr->type == IP)	break; */
			else ++eptr;
		}
		*(++heap) = *eptr;
		if (eptr->type == UBV) {
			/* the vars in the original environment should be reset if */
			/* unification happens to fail	*/
			/* these resets don't need to be put in binding pair lists	*/
			(++reset_ptr)->val = eptr->op.index;
			reset_ptr->class = IP;
			reset_ptr->addr = eptr;
			eptr->type = IP; eptr->op.addr = heap;
		}
		if (debug) {
			foutstring(stdscr, "\n\r     heap(%p) = ", heap);
			print_node(stdscr, heap);
			foutstring(stdscr, ",  env(%p) now ", eptr);
			print_node(stdscr, eptr);
		}
		if (heap->type == UBV) {
			(++heap)->class = CONTROL; heap->type = MARKER;
			heap->op.addr = heap + 3;
			(++heap)->class = CONTROL; heap->type = EX_SCOPE;
			heap->op.addr = 0;
			(++heap)->class = CONTROL; heap->type = LAMBDA;
			heap->op.sym = NULL;
		}
		eptr++;
	}
}

