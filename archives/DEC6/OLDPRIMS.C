/* Primitive Operators for the Lambda Reduction System
/* Mike Hilton, 18 Oct 1989
/*
/* This file contains the implementation details of the builtin
/* primitive operators.
*/

#include <stdio.h>
#include <curses.h>
#include "lrs.h"


#define atomic(ptr) (((ptr)->type != PTR) && ((ptr)->type != CLOSURE))

extern int  argcount;
extern control *aux;
extern int binding_offset;
extern node *env;
extern int debug;
extern char *file_name;
extern unsigned long frozen_redcnt;
extern node *fs;
extern node *inhibit;
extern int line_number;
extern int  mode;
extern node *pc;
extern int  prim_args;
extern node *primitive;
extern unsigned long red_limit;
extern unsigned long reductions;
extern control *stack;
extern node *ws;

extern symbol *true;
extern symbol *false;
symbol *and;
symbol *equal;
symbol *equal_star;
symbol *nil;
symbol *pair;

/* Arithmetic primitives, found in the file ARITH.C */
void prim_add(), prim_sub(), prim_mult(), prim_div(), prim_mod();
void prim_min(), prim_max();
void prim_eq(), prim_neq(), prim_gt(), prim_gte(), prim_lt(), prim_lte();
void prim_abs(), prim_sqrt(), prim_minus(), prim_inc(), prim_dec();
void prim_even(), prim_odd(), prim_pos(), prim_neg();
void prim_atom(), prim_intp(), prim_floatp(), prim_symp(), prim_pairp();
void prim_structp(), prim_struct_tag();

/* Primitives found in this file. */
void prim_if(), prim_y(), prim_and(), prim_or(), prim_not(), prim_equal();
void prim_equal_star();

struct primtab {
   char *name;
   int   type;
   void (*fun) ();
};

struct primtab primtable [] = {
   {"+", PRIM_2, prim_add},
   {"-", PRIM_2, prim_sub},
   {"*", PRIM_2, prim_mult},
   {"/", PRIM_2, prim_div},
   {"modulo", PRIM_2, prim_mod},
   {"max", PRIM_2, prim_max},
   {"min", PRIM_2, prim_min},
   {"=", PRIM_2, prim_eq},
   {"<>", PRIM_2, prim_neq},
   {">", PRIM_2, prim_gt},
   {">=", PRIM_2, prim_gte},
   {"<", PRIM_2, prim_lt},
   {"<=", PRIM_2, prim_lte},
   {"abs", PRIM_1, prim_abs},
#ifdef IBM
   {"sqrt", PRIM_1, prim_sqrt},
#endif
   {"minus", PRIM_1, prim_minus},
   {"1+", PRIM_1, prim_inc},
   {"1-", PRIM_1, prim_dec},
   {"even?", PRIM_1, prim_even},
   {"odd?", PRIM_1, prim_odd},
   {"positive?", PRIM_1, prim_pos},
   {"negative?", PRIM_1, prim_neg},
   {"atom?", PRIM_1, prim_atom},
   {"integer?", PRIM_1, prim_intp},
   {"float?", PRIM_1, prim_floatp},
   {"symbol?", PRIM_1, prim_symp},
   {"pair?", PRIM_1, prim_pairp},
   {"structure?", PRIM_1, prim_structp},
   {"tag", PRIM_1, prim_struct_tag},
   {"if", PRIM_0, prim_if},
   {"Y", PRIM_0, prim_y},
   {"and", PRIM_0, prim_and},
   {"or", PRIM_0, prim_or},   
   {"not", PRIM_1, prim_not},      
   {"equal", PRIM_0, prim_equal},
	{"equal*", PRIM_0, prim_equal_star},
   {"end_of_primtab", 0, NULL}
};


/* INSTALL_PRIMITIVES
/* The primitive operator names and types have to be entered into the
/* symbol table so the compiler will know about them.
*/

void install_primitives()
{
   symbol *sym;
   struct primtab *index = primtable;   
   
   while (strcmp(index->name, "end_of_primtab") != 0) {
      sym = symbol_lookup(index->name, index->type);
      sym->def.prim = index->fun;
      sym->typ = index->type;
      ++index;
   }
      
   true  = symbol_lookup("true", SYM);
   false = symbol_lookup("false", SYM);
   and = symbol_lookup("and", PRIM_0);
   equal = symbol_lookup("equal", PRIM_0);
	equal_star = symbol_lookup("equal*", PRIM_0);
   nil = symbol_lookup("nil", SYM);
   pair = symbol_lookup("$$pair", SYM);
   
   if (load_file(LISTFILE, line_number, file_name)) {
      /* Mark the Lambda PAIR instruction with a PAIR indicator. */
      node *ptr = ((symbol_lookup("cons", SYM))->def.user) + 2;
      ptr->class = ptr->class | PAIR;
   }
   
}




/* IF
/* The basic conditional for the LRS system.
*/

void prim_if()
{
   switch (mode) {
      case HEADM:  inst_inert();
#ifdef DEBUG
      fprintf(stdout, "\nif primitive in HEAD");
#endif
                  if (argcount >= 3) {
                     primitive = pc + 1;
                     prim_args = 1;
                     /* save corrected argcount for restoration after test */
                     (--aux)->intval = argcount - 3;
                  }
                  break;

      case RESULT:
         argcount = (aux++)->intval;      /* Restore proper argcount */

         if (reductions == red_limit) return;

#ifdef DEBUG
         fprintf(stdout, "\nif primitive ");
#endif
         ++pc;       /* counter-act the decrement in move_backward */                  
         if ((pc->type != SYM) ||
             ((pc->type == SYM) && (pc->op.sym != true) && 
              (pc->op.sym != false))) {
            /* The conditional test did not yield TRUE or FALSE, so  */
            /* inhibit the reduction of the true and false branches. */
#ifdef DEBUG
            fprintf(stdout, " -- INHIBITING!");
#endif            
            frozen_redcnt = reductions;
            reductions = red_limit;
            inhibit = primitive - 4;
            --pc;
            return;
         }


         ws -= 2;    /* ws now points to true branch */
         if (ws->type == PTR) {
            if (pc->op.sym == true)    /* if conditional is true     */ 
               env = (stack--)->ptr;   /*       restore context      */
            else --stack;              /* else  throw context away   */
         }
         --ws;
         if (ws->type == PTR) {
            if (pc->op.sym == false)   /* if conditional is false    */
               env = (stack--)->ptr;   /*       restore context      */
            else --stack;              /* else  throw context away   */
         }
         --ws;

         mode = PROBLEM;               /* start moving forward again */
         if (pc->op.sym == true) {     /* set pc to proper branch    */
            pc = pc - 1;
            if (pc->type == PTR) pc = pc->op.addr;
            else pc->class = HEAD;
#ifdef DEBUG
            fprintf(stdout, " -- true branch taken, pc = %p", pc);
#endif            
         }
         else {
            pc = pc - 2;
            if (pc->type == PTR) pc = pc->op.addr;
            else pc->class = HEAD;
#ifdef DEBUG
            fprintf(stdout, " -- false branch taken, pc = %p", pc);
#endif            
         }
         ++reductions;
         break;
   }
}         




/* Y Recursion primitive
/* The Y operator provides for recursion of one argument.  This is an acyclic
/* copying version, which transforms (Y f) into (f (Y f));  it is not
/* a knot tying version which creates a cyclic graph.
*/

void prim_y()
{
   static node temp;

#ifdef DEBUG
   fprintf(stdout,"\nY primitive -- ");
#endif
      
   if ((argcount < 1) || (reductions == red_limit)) {  
#ifdef DEBUG
      fprintf(stdout, "not firing!");
#endif      
      inst_inert();
      return;
   }
   
   ++reductions;
   temp = *ws;                               /* temp <- f  */
   ws->type = PTR; ws->op.addr = pc - 1;     /* point arg1 to (Y f)  */
   if (temp.type == PTR) 
      pc = temp.op.addr;
   else {
      (++stack)->ptr = env;                  /* push context for (Y f) */
      temp.class = HEAD;
      pc = &temp;
   }
   mode = PROBLEM;                           /* start moving forward again */
   
#ifdef DEBUG
   fprintf(stdout, "new pc = %p,  temp = ", convert(pc));
   print_node(stdout, &temp);
   fprintf(stdout, ", *pc = ");
   print_node(stdout, pc);
#endif    
}
   

   
   
/* AND
/* Logical Boolean conjunction.  This is an N-ary operator that reduces to
/* false if any of its arguments reduce to false, and it reduces to
/* true if all of its arguments reduces to true.
*/

void prim_and()
{
   switch (mode) {
      case HEADM: inst_inert();
#ifdef DEBUG
                  fprintf(stdout, "\nand primitive -- head");
#endif                  
                  if ((argcount >= 1) && (reductions != red_limit)) {
                     prim_args = 1;
                     primitive = pc + 1;
                     (--aux)->intval = argcount - 1;
                  }
                  break;
                  
      case RESULT:   
         {
            node *arg = pc + 1;
            argcount = (aux++)->intval;
            
            if ((arg->type != SYM) ||  /* not boolean value, end reduction */
                ((arg->op.sym != true) && (arg->op.sym != false)) ||
                (reductions == red_limit)) {
#ifdef DEBUG
               fprintf(stdout, "\nand primitive -- NOT A BOOL!");
#endif
               return;
            }
            
            ++reductions;

            if (argcount == 0) {    /* no more args, so return last arg val */
               arg->class = HEAD;
#ifdef DEBUG
               fprintf(stdout, "\nand primitive -- FINISHED value is ");
               print_node(stdout, arg);
#endif
               ws = arg;
               return;
            }
            
            if (arg->op.sym == false) {   /* pop all args and return false */
#ifdef DEBUG
               fprintf(stdout, "\nand primitive -- EXIT with FALSE");
#endif
               while (argcount > 0) {
                  --arg;
                  if (arg->type == PTR) --stack;  /* pop off unused contxts */
                  --argcount;
               }
               pc = arg - 1;
               arg->class = HEAD; arg->type = SYM; arg->op.sym = false;
               ws = arg;
               return;
            }
            else {      /* arg is true, set up for next invocation */
#ifdef DEBUG
               fprintf(stdout, "\nand primitive -- TRUE, set up for next arg");
#endif
               *arg = *(arg + 1);      /* overwrite with AND */
               ws = arg;
               (--aux)->intval = argcount - 1;
               primitive = arg;
               prim_args = 1;
               return;
            }
         }
   }
}   
               
               

/* OR
/* Logical boolean disjunction.  This is an N-ary operator that reduces to
/* true if any of its arguments reduces to true, false otherwise.
*/

void prim_or()
{
   switch (mode) {
      case HEADM: inst_inert();
#ifdef DEBUG
                  fprintf(stdout, "\nor primitive -- head");
#endif                  
                  if ((argcount >= 1) && (reductions != red_limit)) {
                     prim_args = 1;
                     primitive = pc + 1;
                     (--aux)->intval = argcount - 1;
                  }
                  break;
                  
      case RESULT:   
         {
            node *arg = pc + 1;
            argcount = (aux++)->intval;
            
            if ((arg->type != SYM) ||  /* not boolean value, end reduction */
                ((arg->op.sym != true) && (arg->op.sym != false)) ||
                (reductions == red_limit)) {
#ifdef DEBUG
               fprintf(stdout, "\nor primitive -- NOT A BOOL!");
#endif

               return;
            }
            
            ++reductions;

            if (argcount == 0) {    /* no more args, so return last arg val */
               arg->class = HEAD;
#ifdef DEBUG
               fprintf(stdout, "\nor primitive -- FINISHED value is ");
               print_node(stdout, arg);
#endif
               ws = arg;
               return;
            }
            
            if (arg->op.sym == true) {   /* pop all args and return true*/
#ifdef DEBUG
               fprintf(stdout, "\nor primitive -- EXIT with TRUE");
#endif
               while (argcount > 0) {
                  --arg;
                  if (arg->type == PTR) --stack;  /* pop off unused contxts */
                  --argcount;
               }
               pc = arg - 1;
               arg->class = HEAD; arg->type = SYM; arg->op.sym = true;
               ws = arg;
               return;
            }
            else {      /* arg is false, set up for next invocation */
#ifdef DEBUG
               fprintf(stdout, "\nor primitive -- FALSE, set up for next arg");
#endif
               *arg = *(arg + 1);      /* overwrite with OR */
               ws = arg;
               (--aux)->intval = argcount - 1;
               primitive = arg;
               prim_args = 1;
               return;
            }
         }
   }
}   




/* NOT
/* Logical boolean negation.  If its argument reduces to true, it reduces
/* to false; if its argument reduces to false, it reduces to true.
*/

void prim_not()
{
   node *arg = pc + 1;
   
   if ((arg->type != SYM) ||  /* not boolean value, end reduction */
       ((arg->op.sym != true) && (arg->op.sym != false)) ||
       (reductions == red_limit)) {
      return;
   }
   ++reductions;
   if (arg->op.sym == true) 
      arg->op.sym = false;
   else 
      arg->op.sym = true;
   arg->class = HEAD;
   ws = arg;
}



     


/* EQUAL
/* Alpha-equality predicate.  
*/

void prim_equal()
{
   node *arg1   = ws;
   node *arg2   = ws - 1;
               
	if (debug) {
   	foutstring(stdscr, "\n\rprim_equal: arg1 (%p) = ", arg1);
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
      arg2->class = HEAD; arg2->type = SYM; arg2->op.sym = true;
      ws = arg2;
      ++reductions;
      pc = ws - 1;
      mode = RESULT;
      return;
   }

   /* If one argument is a UBV, then do not fire. */
   if ((arg1->type == UBV) || (arg2->type == UBV)) {
   	if (debug) {
   		outstring(stdscr, "\n\r  one arg is a UBV, NOT FIRING");
   		wrefresh(stdscr);
   	}
		inst_inert();
		return;
	}

   /* If one argument is atomic and the other points to a lambda,  */
   /* there is no way they can be equal.  */
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
			outstring(stdscr, "\n\r  Nodes cannot be equal, fire FALSE");
			wrefresh(stdscr);
		}
		--stack;  /* pop env off stack */
      arg2->class = HEAD; arg2->type = SYM; arg2->op.sym = false;
      ws = arg2;
      ++reductions;
      pc = ws - 1;
      mode = RESULT;
      return;
   }
	    
	    
	/* If either argument is a PTR or CLOSURE, then reduce the arguments */
	/* and apply EQUAL*	*/	
	if ((arg1->type == PTR) || (arg1->type == CLOSURE) ||
		 (arg2->type == PTR) || (arg2->type == CLOSURE)) {
		if (debug) {
			outstring(stdscr, "\n\r  reducing both arguments first");
			wrefresh(stdscr);
		}
		inst_inert();
		primitive = pc + 1;
		primitive->op.sym = equal_star;
		prim_args = 2;
		return;
   }


	/* If none of the above is true, the two args cannot be equal */
	if (debug) {
		outstring(stdscr, "\n\r  args cannot be equal, firing FALSE");
		wrefresh(stdscr);
	}
   arg2->class = HEAD; arg2->type = SYM; arg2->op.sym = false;
   ws = arg2;
   ++reductions;
   pc = ws - 1;
   mode = RESULT;
   return;
}


/* EQUAL_STAR
/* After both args have been reduced, equal star checks for structural
/* equality.
*/
int structs;
int lambdas;

void prim_equal_star()
{
   node *arg1 = primitive - 1;
   node *arg2 = primitive - 2;
	node *res  = arg2;
   int  first = TRUE;
   control *stack_orig = stack;
   control *aux_orig = aux;
               
	if (debug) {
   	foutstring(stdscr, "\n\rprim_equal_star: arg1 (%p) = ", arg1);
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

   structs = 0;               
   lambdas = 0;
   
   /* walk down the args and compare elements */
   Down:

		if (debug) {
	   	foutstring(stdscr, "\n\r  equal* loop: arg1 (%p) = ", arg1);
			print_node(stdscr, arg1);
			foutstring(stdscr, "  arg2 (%p) = ", arg2);
			print_node(stdscr, arg2);
		}

      if (nodes_equal(&arg1, &arg2, TRUE) == FALSE) {
	      stack = stack_orig;
  			aux = aux_orig;
			if ((arg1->type == VAR) && (arg2->type == VAR) &&
				 ((arg1->op.index < lambdas) || (arg2->op.index < lambdas))) {
				 	goto Fail;
				 }
         if (((arg1->type == VAR) && (arg1->op.index >= lambdas)) ||
             ((arg2->type == VAR) && (arg2->op.index >= lambdas))) {
            	if (debug) {
						outstring(stdscr, "\n\r one arg is a VAR, not firing");
						wrefresh(stdscr);
					}
		   	   return;
				 }
         else {
         	goto Fail;
			}         	
      }
      if (first == TRUE && stack_orig == stack && aux_orig == aux)
         goto Succeed;

      if ((first == FALSE) && (arg1->class != HEAD)) {
         ++arg1;
         ++arg2;
         goto Down;
      }
      first = FALSE;
      
      /* If there are any more subgraphs to do, get pointer to them and */
      /* loop back to label Down. */
      if (stack_orig != stack) {
			if (debug) {
         	outstring(stdscr, "\n\r  popping pointers");
         	wrefresh(stdscr);
         }
         arg1 = (stack--)->ptr;
         arg2 = (stack--)->ptr;
         lambdas = (stack--)->intval;
         goto Down;
      }

      
   /* The two arguments are now known to be equal except for possible */
   /* frozen expressions inside lazy structures */

   if (structs == 0) goto Succeed;
   else {
      /* Build a graph that checks frozen expressions for equality */
      node *base, *argptr;
		if (debug) {
			outstring(stdscr, "\n\r  creating new equality graph");
			wrefresh(stdscr);
		}      
      base = fs - (structs * 3) - 1;
      base->class = HEAD; base->type = PRIM_0; base->op.sym = and;
      argptr = base;
      for (; structs > 0; structs--) {
			if (debug) {
				outstring(stdscr, "\n\r     new arg pair");
				wrefresh(stdscr);
			}
         ++argptr;
         --base;
         base->class = APPLY; base->type = PTR; base->op.addr = argptr;
         *argptr = *((aux++)->ptr); argptr->class = APPLY;
			if (debug) {
				outstring(stdscr, "  arg1 = ");
				print_node(stdscr, argptr);
			}
         ++argptr;
         *argptr = *((aux++)->ptr); argptr->class = APPLY;
         if (debug) {
				outstring(stdscr, "  arg2 = ");
				print_node(stdscr, argptr);
			}
         ++argptr;
         argptr->class = HEAD; argptr->type = PRIM_0; argptr->op.sym = equal;
      }
		if (debug) {
      	outstring(stdscr, "\n\r   new equality graph created");
      	print_mem(stdscr, base, fs);
      }
		(++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = res;
		res->class = HEAD;  /* controversial move */
      fs = base;
      pc = base;
		jump_subgraph();
		++reductions;
      return;
   }
            
   Succeed:
		if (debug) {
      	outstring(stdscr, "\n\r  equal* primitive -- firing TRUE");
			wrefresh(stdscr);
		}
      res->class = HEAD; res->type = SYM; res->op.sym = true;
      ws = res;
      ++reductions;
      return;

	Fail:
		if (debug) {
			outstring(stdscr, "\n\r  args cannot be equal, firing FALSE");
			wrefresh(stdscr);
		}
		res->class = HEAD; res->type = SYM; res->op.sym = false;
   	ws = res;
   	++reductions;
		return;
}




/* NODES_EQUAL
/* Predicate to test if two nodes are equal.  To be used in conjunction with
/* the PRIM_EQUAL and PRIM_EQUAL*.  ARG1 and ARG2 are pointers to the nodes
/* to be tested; REDUCED is a boolean flag that tells if the nodes have
/* been reduced.
*/

int nodes_equal(arg1, arg2, reduced)
node **arg1, **arg2;
int reduced;
{
	if (debug) {
      foutstring(stdscr, "\n\r  nodes_equal -- arg1 %p = ", *arg1);
      print_node(stdscr, *arg1);
      foutstring(stdscr, "  arg2 %p = ", *arg2);
      print_node(stdscr, *arg2);
   }

   if ((*arg1)->type != (*arg2)->type) return(FALSE);
   switch ((*arg1)->type) {
      case FLOAT:    return(((*arg1)->op.floval == (*arg2)->op.floval));
      case INT:      return(((*arg1)->op.intval == (*arg2)->op.intval));

		case LAMBDA:	++lambdas;
							(--fs)->type = UBV; fs->op.index = lambdas;
							if (((*arg1)->class & PAIR) && ((*arg2)->class & PAIR)) {
								/* frozen objects, push on aux stack for later */
								for (;;) {
									++(*arg1); ++(*arg2);
									/* At the end of structures? */
									if (((*arg1)->class & HEAD) && ((*arg2)->class & HEAD)) {
										if (nodes_equal(arg1, arg2, FALSE))	return(TRUE);
										else return(FALSE);
									}
									/* Structures not the same size? */
									if (((*arg1)->class & HEAD) || ((*arg2)->class & HEAD))
										return(FALSE);
									/* Is entry an uninstantiated lambda variable? */
									if (((*arg1)->type == VAR) &&
										 ((*arg1)->op.index < lambdas) &&
										 (!nodes_equal(arg1, arg2, FALSE)))
										 return(FALSE);
									if (((*arg2)->type == VAR) &&
										 ((*arg2)->op.index < lambdas) &&
										 (!nodes_equal(arg1, arg2, FALSE)))
										 return(FALSE);
									/* check out atomic args */
									if (atomic(*arg1) && atomic(*arg2)) {
									   if (nodes_equal(arg1, arg2, FALSE))
											continue;
										else if ((*arg1)->type != VAR && (*arg2)->type != VAR)
											return(FALSE);
									}

									/* Push args onto aux */
									++structs;
									if (debug) {
										outstring(stdscr, "\n\r      pushing struct, ");
									}
									if (((*arg1)->type == VAR) &&
									    ((*arg1)->op.index >= lambdas)) {
									    	(--fs)->class = HEAD; fs->type = VAR;
									    	fs->op.index = (*arg1)->op.index - lambdas;
									    	(--aux)->ptr = fs;
									    }
									else if (atomic(*arg1)) {
										*(--fs) = **arg1; fs->class = HEAD;
										(--aux)->ptr = fs;
									}
									else (--aux)->ptr = *arg1;
									if (debug) {
										outstring(stdscr, "arg1 = ");
										print_node(stdscr, aux->ptr);
									}
									if (((*arg2)->type == VAR) &&
										 ((*arg2)->op.index >= lambdas)) {
									    	(--fs)->class = HEAD; fs->type = VAR;
									    	fs->op.index = (*arg2)->op.index - lambdas;
									    	(--aux)->ptr = fs;
									    }
									else if (atomic(*arg2)) {
										*(--fs) = **arg2; fs->class = HEAD;
										(--aux)->ptr = fs;
									}
									else (--aux)->ptr = *arg2;
									if (debug) {
										outstring(stdscr, ", arg2 = ");
										print_node(stdscr, aux->ptr);
									}
								}
							}
							return(TRUE);

      case SYM:
      case PRIM_0:
      case PRIM_1:
      case PRIM_2:   return(((*arg1)->op.sym == (*arg2)->op.sym));

		case UBV:
      case VAR:      return(((*arg1)->op.index == (*arg2)->op.index));

      case PTR:      if (!reduced) {
								if (((*arg1)->op.addr == (*arg2)->op.addr) &&
                         	 (stack->ptr == (stack-1)->ptr)) {
									/* pop the env pointers off the stack */
                         	stack -= 2;
                         	return(TRUE);
                     	}
                     	else return (FALSE);
      					}
							else {
								if ((*arg1)->op.addr != (*arg2)->op.addr) {      
                           (++stack)->intval = lambdas;
                           (++stack)->ptr = (*arg1)->op.addr;   
                           (++stack)->ptr = (*arg2)->op.addr;
                        }
                        return(TRUE);
                     }


		case CLOSURE:  if (((*arg1)->op.addr == (*arg2)->op.addr) ||
								 (((*arg1)->op.addr->type == CL_PTR) &&
								  ((*arg2)->op.addr->type == CL_PTR) &&
								  ((*arg1)->op.addr->op.addr == (*arg2)->op.addr->op.addr) &&
								  ((((*arg1)->op.addr)+1)->op.addr ==
								   (((*arg2)->op.addr)+1)->op.addr)))
								   return(TRUE);
							else return(FALSE);

   }
}


