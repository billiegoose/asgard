/* Primitive Operators for the Lambda Reduction System
/* Mike Hilton, 13 Nov 1989
/*
/* This file contains the implementation details of the builtin
/* primitive operators.
*/

#include <stdio.h>
#include <curses.h>
#include "lrs.h"


extern int  argcount;
extern control *aux;
extern int binding_offset;
extern node *env;
extern int debug;
extern char *file_name;
extern unsigned long frozen_redcnt;
extern node *fs;
extern node *heap;
extern node *inhibit;
extern int line_number;
extern int  mode;
extern node *pc;
extern int  prim_args;
extern node *primitive;
extern unsigned long red_limit;
extern unsigned long reductions;
extern reset *reset_ptr;
extern control *stack;
extern node *ws;

extern symbol *true;
extern symbol *false;
symbol *neutral;
symbol *and;
symbol *equal;
symbol *equal_star;
symbol *nil;
symbol *pair;
symbol *unify;
symbol *unify_star;
symbol *bind;
symbol *var_out_of_scope;
symbol *genvar;

/* Arithmetic primitives, found in the file ARITH.C */
void prim_add(), prim_sub(), prim_mult(), prim_div(), prim_mod();
void prim_min(), prim_max(), prim_expt();
void prim_eq(), prim_neq(), prim_gt(), prim_gte(), prim_lt(), prim_lte();
void prim_abs(), prim_sqrt(), prim_minus(), prim_inc(), prim_dec();
void prim_floor(), prim_ceiling();
void prim_even(), prim_odd(), prim_pos(), prim_neg();
void prim_atom(), prim_intp(), prim_floatp(), prim_symp(), prim_pairp();
void prim_structp(), prim_struct_tag();

/* Primitives found in this file. */
void prim_if(), prim_y(), prim_and(), prim_or(), prim_not(), prim_equal();
void prim_equal_star();
void prim_unify(), prim_unify_star(), prim_bind();

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
	{"expt", PRIM_2, prim_expt},
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
	{"floor", PRIM_1, prim_floor},
	{"ceiling", PRIM_1, prim_ceiling},
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
   {"not", PRIM_0, prim_not},      
   {"equal", PRIM_0, prim_equal},
   {"equal*", PRIM_0, prim_equal_star},
   {"unify", PRIM_0, prim_unify},
   {"unify*", PRIM_0, prim_unify_star},
   {"bind", PRIM_0, prim_bind},
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
   neutral = symbol_lookup("|neutral|", SYM);
   and = symbol_lookup("and", PRIM_0);
   equal = symbol_lookup("equal", PRIM_0);
   equal_star = symbol_lookup("equal*", PRIM_0);
   nil = symbol_lookup("nil", SYM);
   pair = symbol_lookup("$$pair", SYM);
   unify = symbol_lookup("unify", PRIM_0);
   unify_star = symbol_lookup("unify*", PRIM_0);   
	bind = symbol_lookup("bind", PRIM_0);
	var_out_of_scope = symbol_lookup("|*var out of scope*|", SYM);
	genvar = symbol_lookup("%gv%", SYM);

	
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
                   if (debug) {
                     outstring(stdscr, "\n\rIF primitive in HEAD");
                     wrefresh(stdscr);
                   }
                  if (argcount >= 3) {
                     primitive = pc + 1;
                     prim_args = 1;
                     /* save corrected argcount for restoration after test */
                     (--aux)->intval = argcount - 3;
                  }
                  break;

      case RESULT:
         argcount = (aux++)->intval;      /* Restore proper argcount */

         if (reductions == red_limit) {
            if (debug) {
               outstring(stdscr, "\n\rIF primitive NOT FIRING, redlimit");
               wrefresh(stdscr);
            }
            return;
         }

         ++pc;       /* counter-act the decrement in move_backward */                  
         if ((pc->type != SYM) ||
             ((pc->type == SYM) && (pc->op.sym != true) && 
              (pc->op.sym != false))) {
            /* The conditional test did not yield TRUE or FALSE, so  */
            /* inhibit the reduction of the true and false branches. */
            if (debug) {
               outstring(stdscr, "\n\rIF primitive -- INHIBITING!");
               wrefresh(stdscr);
            }
            frozen_redcnt = reductions;
            reductions = red_limit;
            inhibit = primitive - 4;
            --pc;
            return;
         }


         ws = primitive - 2;    /* ws now points to true branch */
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
            if (debug) {
               foutstring(stdscr, "\n\r IF -- true branch taken, pc = %p", pc);
               wrefresh(stdscr);
            }
         }
         else {
            pc = pc - 2;
            if (pc->type == PTR) pc = pc->op.addr;
            else pc->class = HEAD;
            if (debug) {
               foutstring(stdscr, "\n\rIF -- false branch taken, pc = %p", pc);
               wrefresh(stdscr);
            }
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
                  if (debug) {
                     outstring(stdscr, "\n\rAND primitive -- head");
                     wrefresh(stdscr);
                  }
                  if ((argcount >= 1) && (reductions != red_limit)) {
                     prim_args = 1;
                     primitive = pc + 1;
							(--aux)->ptr = heap;
							(--aux)->rptr = reset_ptr;
                     (--aux)->intval = argcount - 1;
                  }
                  break;
                  
      case RESULT:   
         {
            node *arg = pc + 1;
            argcount = (aux++)->intval;
				if (debug) {
					foutstring(stdscr, "\n\rAND primitive  aux->rptr = %p", aux->rptr);
					wrefresh(stdscr);
				}

			
            if (reductions == red_limit) {
               if (debug) {
                  outstring(stdscr, "\n\rAND primitive -- NOT FIRING, redlimit");
                  wrefresh(stdscr);
               }
					if (aux->rptr == reset_ptr) ++aux;  /* pop reset ptr value */
					else {
/*						(++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = arg;
						(++ws)->class = CONTROL; ws->type = RESET;
						ws->op.rptr = aux->rptr;
*/						jump_subgraph();
						pc = insert_binding_pairs((aux++)->rptr, arg, arg+1, TRUE);
						mode = RESULT;
					}
					++aux;  /* pop heap pointer */
               return;
            }
            
            if ((arg->type != SYM) ||
                ((arg->op.sym != true) && (arg->op.sym != false) &&
				     (arg->op.sym != neutral))) {
               if (debug) {
                  outstring(stdscr, "\n\rAND primitive -- NOT FIRING, not a bool!");
                  wrefresh(stdscr);
               }
               (--aux)->intval = argcount - 1;
               prim_args = 1;
            }
            
            if ((arg->type == SYM) && (arg->op.sym == false)) {
               /* pop all args and return false */
               if (debug) {
                  outstring(stdscr, "\n\rAND primitive -- EXIT with FALSE");
                  wrefresh(stdscr);
               }
               while (argcount > 0) {
                  --arg;
                  if (arg->type == PTR) --stack;  /* pop off unused contxts */
                  --argcount;
               }
               undo_bindings((aux++)->rptr);		/* pop reset pointer */
               heap = (aux++)->ptr;					/* pop heap pointer */
					make_result(arg, false);
               return;
            }
            
            if ((arg->type == SYM) &&
					 ((arg->op.sym == true) || (arg->op.sym == neutral))) {
               /* set up for next invocation */
               node *temp = arg;
               if (debug) {
                  if (arg->op.sym == true)
							outstring(stdscr, "\n\rAND primitive -- TRUE, set up for next arg");
						else
							outstring(stdscr, "\n\rAND primitive -- NEUTRAL, set up for next arg");						
                  wrefresh(stdscr);
               }

               (--aux)->intval = argcount - 1;
               if (! ((argcount == 0) && (primitive == arg+1))) {
						if (arg->op.sym == true) ++reductions;
                  while (temp->class != HEAD) {
                     *temp = *(temp + 1);
                     ++temp;
                  }
                  primitive = temp - 1;
                  prim_args = 1;
               }
            }

            if (argcount == 0) {
            	if ((arg->type == SYM) && (arg->op.sym == neutral))
            		arg->op.sym = true;
               if (primitive == arg+1) {
	               ++reductions;
                  arg->class = HEAD;
                  if (atomic(arg)) ws = arg;
               }
               if (debug) {
                  foutstring(stdscr, "\n\rAND primitive -- FINISHED, value (%p) is ", arg);
                  print_node(stdscr, arg);
               }
               aux += 3;  /* pop off argcount, reset, and heap pointers */
               prim_args = 0;
            }
            return;            
         }
   }
}   
               
               

/* OR
/* Logical boolean disjunction.  This is an N-ary operator that reduces to
/* true if any of its arguments reduces to true.
*/

void prim_or()
{
   switch (mode) {
      case HEADM: inst_inert();
                  if (debug) {
                     outstring(stdscr, "\n\rOR primitive -- head");
                     wrefresh(stdscr);
                  }
                  if ((argcount >= 1) && (reductions != red_limit)) {
                     prim_args = 1;
                     primitive = pc + 1;
							(--aux)->rptr = reset_ptr;
                     (--aux)->intval = argcount - 1;
                  }
                  break;
                  
      case RESULT:   
         {
            node *arg = pc + 1;
            argcount = (aux++)->intval;

            if (reductions == red_limit) {
               if (debug) {
                  outstring(stdscr, "\n\rOR primitive -- NOT FIRING, redlimit");
                  wrefresh(stdscr);
               }
					if (aux->rptr == reset_ptr) ++aux;  /* pop reset ptr value */
					else {
/*						(++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = arg;
						(++ws)->class = CONTROL; ws->type = RESET;
						ws->op.rptr = aux->rptr;
*/						jump_subgraph();
						pc = insert_binding_pairs((aux++)->rptr, arg, arg+1, FALSE);
						mode = RESULT;
					}
               return;
            }
            
            if ((arg->type != SYM) ||  /* not boolean value */
                ((arg->op.sym != true) && (arg->op.sym != false) &&
					  (arg->op.sym != neutral))) {
               if (debug) {
                  outstring(stdscr, "\n\rOR primitive -- NOT FIRING, not a bool!");
                  wrefresh(stdscr);
               }
               undo_bindings(aux->rptr);
               (--aux)->intval = argcount - 1;
               prim_args = 1;
            }
            
            if ((arg->type == SYM) && (arg->op.sym == true)) {
               /* pop all args and return true */
               if (debug) {
                  outstring(stdscr, "\n\rOR primitive -- EXIT with TRUE");
                  wrefresh(stdscr);
               }
               while (argcount > 0) {
                  --arg;
                  if (arg->type == PTR) --stack;  /* pop off unused contxts */
                  --argcount;
               }
               ++aux; 	/* pop off reset ptr */
               make_result(arg, true);
               return;
            }
            
            if ((arg->type == SYM) && 
					 ((arg->op.sym == false) || (arg->op.sym == neutral))) {
               /* set up for next invocation */
               node *temp = arg;
               if (debug) {
               	if (arg->op.sym == false)
	                  outstring(stdscr, "\n\rOR primitive -- FALSE, set up for next arg");
   					else
	                  outstring(stdscr, "\n\rOR primitive -- NEUTRAL, set up for next arg");
               wrefresh(stdscr);
               }
					if (arg->op.sym == false) {
               	undo_bindings(aux->rptr);
               }
               (--aux)->intval = argcount - 1;
               if (! ((argcount == 0) && (primitive == arg+1))) {
						if (arg->op.sym == false) ++reductions;
                  while (temp->class != HEAD) {
                     *temp = *(temp + 1);
                     ++temp;
                  }
                  primitive = temp - 1;
                  prim_args = 1;
               }
            }

            if (argcount == 0) {
            	if ((arg->type == SYM) && (arg->op.sym == neutral))
            		arg->op.sym = false;
               if (primitive == arg+1) {
               	++reductions;
                  arg->class = HEAD;
                  if (atomic(arg)) ws = arg;
               }
               if (debug) {
                  outstring(stdscr, "\n\rOR primitive -- FINISHED value is ");
                  print_node(stdscr, arg);
               }
               ++aux;  /* pop off argcount */
               ++aux;  /* pop off reset ptr */
               prim_args = 0;
            }
            return;
         }
   }
}   




/* NOT
/* Logical boolean negation.  If its argument reduces to true, it reduces
/* to false and undoes any bindings that may have been made by the argument;
/* if its argument reduces to false, it reduces to true.
*/

void prim_not()
{
	switch (mode) {
      case HEADM: inst_inert();
                  if (debug) {
                     outstring(stdscr, "\n\rNOT primitive -- head");
                     wrefresh(stdscr);
                  }
                  if ((argcount >= 1) && (reductions != red_limit)) {
                     prim_args = 1;
                     primitive = pc + 1;
							(--aux)->ptr = heap;
							(--aux)->rptr = reset_ptr;
                  }
                  break;

		case RESULT:
			{		
			   node *arg = pc + 1;

			   if (reductions == red_limit) {
			   	if (debug) {
			   		outstring(stdscr, "\n\rNOT primitive -- NOT FIRING, redlimit");
			   		wrefresh(stdscr);
			   	}
					if (aux->rptr == reset_ptr) ++aux;  /* pop reset ptr value */
					else {
						node *head = ++ws;
						ws->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;
/*						(++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = arg;
						(++ws)->class = CONTROL; ws->type = RESET;
						ws->op.rptr = aux->rptr;
*/						jump_subgraph();
						pc = insert_binding_pairs((aux++)->rptr, arg, head, TRUE);
						arg->class = APPLY;
						mode = RESULT;
					}
					++aux;		/* pop heap pointer */
               return;
            }

			   if ((arg->type != SYM) ||  /* not boolean value, end reduction */
			       ((arg->op.sym != true) && (arg->op.sym != false))) {
					if (debug) {
						outstring(stdscr, "\n\rNOT primitive -- NOT FIRING, not a bool");
						wrefresh(stdscr);
					}
			      aux += 2;  		/* pop reset and heap pointers */
				   return;
			   }


			   if (arg->op.sym == true) {
			      arg->op.sym = false;
			      undo_bindings((aux++)->rptr);
			      heap = (aux++)->ptr;
			   }
			   else {
			      arg->op.sym = true;
			      aux += 2;
			   }
			   arg->class = HEAD;
			   ++reductions;
			   ws = arg;
			   break;
			}
	}
}



     


/* EQUAL
/* Alpha-equality predicate.  
*/

void prim_equal()
{
   switch (mode) {
      case HEADM:
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

            /* Dereference EP's */
            if (arg1->type == EP) {
            	node *value = lookup(arg1->op.addr, 0);
            	arg1->type = value->type;
            	arg1->op = value->op;
            	if (debug) {
            		outstring(stdscr, "\n\r dereferencing arg1 to ");
            		print_node(stdscr, arg1);
            	}
            }
            if (arg2->type == EP) {
            	node *value = lookup(arg2->op.addr, 0);
            	arg2->type = value->type;
            	arg2->op = value->op;
            	if (debug) {
            		outstring(stdscr, "\n\r dereferencing arg2 to ");
            		print_node(stdscr, arg2);
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
                  outstring(stdscr, "\n\r  atomic Vs. lambda, fire FALSE");
                  wrefresh(stdscr);
               }
               if ((atomic(arg1) && (arg2->type == PTR)) ||
                   (atomic(arg2) && (arg1->type == PTR))) {
                  --stack;  /* pop env off stack */
                   }
               arg2->class = HEAD; arg2->type = SYM; arg2->op.sym = false;
               ws = arg2;
               ++reductions;
               pc = ws - 1;
               mode = RESULT;
               return;
            }
       
            /* If either argument is a PTR or CLOSURE, then reduce the arguments */
            /* and apply EQUAL*  */ 
            if ((arg1->type == PTR) || (arg1->type == CLOSURE) ||
                (arg2->type == PTR) || (arg2->type == CLOSURE)) {
               if (debug) {
                  outstring(stdscr, "\n\r  reducing both arguments first");
                  wrefresh(stdscr);
               }
               inst_inert();
               ++ws;       /* leave a space for extra equal* arg later */
               primitive = pc + 1;
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

      case RESULT:
         {
            /* convert over to an EQUAL* instruction and invoke. */
            if (reductions == red_limit) return;
            if (debug) {
               outstring(stdscr, "\n\r  converting to an equal*");
               wrefresh(stdscr);
            }
            primitive->class = APPLY; primitive->type = INT;
            primitive->op.intval = 0;
            (++primitive)->class = HEAD; primitive->type = PRIM_0;
            primitive->op.sym = equal_star;
            pc = primitive;
            return;
         }
   }
}


/* EQUAL_STAR
/* After both args have been reduced, equal star checks for structural
/* equality.
*/

void prim_equal_star()
{
   node *arg1, *arg2, *res;
   int lambdas, pop_stack = FALSE;


   if (mode == HEADM) {
      inst_inert();
      pc = pc+1;
      primitive = pc;
      pop_stack = TRUE;
   }

   
   lambdas = (--pc)->op.intval;
   arg1 = (--pc);
   arg2 = (--pc);
   res = pc;
   
   if (debug) {
      foutstring(stdscr, "\n\rprim_equal_star: n = %d, arg1 (%p) = ", lambdas, arg1);
      print_node(stdscr, arg1);
      foutstring(stdscr, ",  arg2 (%p) = ", arg2);
      print_node(stdscr, arg2);
   }

   if (reductions == red_limit) {
      if (debug) {
         outstring(stdscr, "\n\r  NOT FIRING, red_limit");
         wrefresh(stdscr);
      }
      if (pop_stack && arg1->type == PTR) --stack;
      if (pop_stack && arg2->type == PTR) --stack;
      pc = res - 1;
      return;
   }

   /* If either arg is a pointer to a head, promote the head object */
   /* and retry.  This is a kludge to get around VARs changing to   */
   /* UBV's if walked across by the reducer.                        */
   if (((arg1->type == PTR) && (arg1->op.addr->class == HEAD)) ||
       ((arg2->type == PTR) && (arg2->op.addr->class == HEAD))) {
      if (arg1->op.addr->class == HEAD) {
         arg1->type = arg1->op.addr->type;
         arg1->op = arg1->op.addr->op;
         if (pop_stack) --stack;
      }
      if (arg2->op.addr->class == HEAD) {
         arg2->type = arg2->op.addr->type;
         arg2->op = arg2->op.addr->op;
         if (pop_stack) --stack;
      }
      pc = primitive;
      return;
   }

   /* check if args are identical */
   if (nodes_equal(&arg1, &arg2, TRUE)) {
      if (debug) {
         outstring(stdscr, "\n\r  FIRING true, identical args");
         wrefresh(stdscr);
      }
      if (pop_stack && arg1->type == PTR) --stack;
      if (pop_stack && arg2->type == PTR) --stack;
      res->class = HEAD; res->type = SYM; res->op.sym = true;
      ++reductions;
      pc = res - 1;
      return;
   }

   /* check to see if one arg is an unbound var */
   if ((arg1->type == VAR) && (arg1->op.index >= lambdas)) {
      if ((arg2->type == VAR) && (arg2->op.index < lambdas)) {
         /* no way they can be equal */
         if (debug) {
            outstring(stdscr, "\n\r  FIRING false, unbound to bound var");
            wrefresh(stdscr);
         }
         res->class = HEAD; res->type = SYM; res->op.sym = false;
         ++reductions;
         pc = res - 1;
         ws = res;
         return;
      }
      else {
         if (debug) {
            outstring(stdscr, "\n\r  NOT FIRING, unbound var");
            wrefresh(stdscr);
         }
         if (lambdas > 0) {
            wrap_lambdas(lambdas, arg1);
            wrap_lambdas(lambdas, arg2);
            if (debug) {
               outstring(stdscr, "\n\r  wrapping args in lambdas");
               wrefresh(stdscr);
            }
         }
         (--primitive)->class = HEAD; primitive->type = PRIM_0;
         primitive->op.sym = equal;
         pc = res - 1;
         return;
      }
   }
   if ((arg2->type == VAR) && (arg2->op.index >= lambdas)) {
      if ((arg1->type == VAR) && (arg1->op.index < lambdas)) {
         /* no way they can be equal */
         if (debug) {
            outstring(stdscr, "\n\r  FIRING false, unbound to bound var");
            wrefresh(stdscr);
         }
         res->class = HEAD; res->type = SYM; res->op.sym = false;
         ++reductions;
         pc = res - 1;
         ws = res;
         return;
      }
      else {
         if (debug) {
            outstring(stdscr, "\n\r  NOT FIRING, unbound var");
            wrefresh(stdscr);
         }
         if (lambdas > 0) {
            wrap_lambdas(lambdas, arg1);
            wrap_lambdas(lambdas, arg2);
            if (debug) {
               outstring(stdscr, "\n\r  wrapping args in lambdas");
               wrefresh(stdscr);
            }
         }
         (--primitive)->class = HEAD; primitive->type = PRIM_0;
         primitive->op.sym = equal;
         pc = res - 1;
         return;
      }
   }

   /* if args not pointers, then they cannot be equal */
   if ((arg1->type != PTR) || (arg2->type != PTR)) {
      if (debug) {
         outstring(stdscr, "\n\r  FIRING false, args not same");
         wrefresh(stdscr);
      }
      if (pop_stack && arg1->type == PTR) --stack;
      if (pop_stack && arg2->type == PTR) --stack;
      res->class = HEAD; res->type = SYM; res->op.sym = false;
      ++reductions;
      pc = res - 1;
      ws = res;
      return;
   }

   /* split up pointers */
   if ((arg1->op.addr->class == APPLY) && (arg2->op.addr->class == APPLY)) {
      if (debug) {
         outstring(stdscr, "\n\r  splitting an ap");
         wrefresh(stdscr);
      }
      if (pop_stack) stack -= 2;

      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 7;
      pc = ws;
      (++ws)->class = APPLY; ws->type = PTR; ws->op.addr = ws + 2;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;

      /* All this madness with VAR's is to make sure they don't get */
      /* re-reduced when the split is walked through.               */
      if (arg1->op.addr->type == VAR) {
         *(++ws) = *arg1;
         arg1->op.addr->class = HEAD;
      }
      else *(++ws) = *(arg1->op.addr);
      if (arg2->op.addr->type == VAR) {
         *(++ws) = *arg2;
         arg2->op.addr->class = HEAD;
      }
      else *(++ws) = *(arg2->op.addr);
      (++ws)->class = APPLY; ws->type = INT; ws->op.intval = lambdas;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = equal_star;

      if (((arg1->op.addr+1)->class == HEAD) &&
          ((arg1->op.addr+1)->type != VAR)) {
         *(++ws) = *(arg1->op.addr+1);
         ws->class = APPLY;
      }
      else {
         (++ws)->class = APPLY; ws->type = PTR;
         ws->op.addr = arg1->op.addr + 1;
      }
      if (((arg2->op.addr+1)->class == HEAD) &&
          ((arg2->op.addr+1)->type != VAR)) {
         *(++ws) = *(arg2->op.addr+1);
         ws->class = APPLY;
      }
      else {
         (++ws)->class = APPLY; ws->type = PTR;
         ws->op.addr = arg2->op.addr + 1;
      }
      (++ws)->class = APPLY; ws->type = INT; ws->op.intval = lambdas;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = equal_star;

      (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = res;
      res->class = HEAD;
      
      jump_subgraph();
      mode = PROBLEM;
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
      if (pop_stack) stack -= 2;
      ++lambdas;
      
      /* Check if the tags are different */
      if (arg1->op.addr->op.sym != arg2->op.addr->op.sym) {
         if (debug) {
            outstring(stdscr, "\n\r  FIRING FALSE, different tags");
            wrefresh(stdscr);
         }
         res->class = HEAD; res->type = SYM; res->op.sym = false;
         ++reductions;
         pc = res - 1;
         ws = res;
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
         res->class = HEAD; res->type = SYM; res->op.sym = false;
         ++reductions;
         pc = res - 1;
         ws = res;
         return;
      }

      /* build new equality graph */
      if (debug) {
         outstring(stdscr, "\n\r  building new equality graph");
         wrefresh(stdscr);
      }
      pc = ws + 1;
      arg1 = arg1->op.addr;
      arg2 = arg2->op.addr;
      ws += len1;
      temp = pc;
      (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = and;
      while (len1-- > 0) {
         node *t1, *t2;
         /* put in pointer to equality graph */
         temp->class = APPLY; temp->type = PTR; temp->op.addr = ws + 1;
         ++temp;
         /* build new equality graph */
         *(++ws) = *(++arg2); t2 = ws;
         *(++ws) = *(++arg1); t1 = ws;
         (++ws)->class = HEAD; ws->type = PRIM_0; ws->op.sym = equal;
         wrap_lambdas(lambdas, t2);
         wrap_lambdas(lambdas, t1);
      }
      (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = res;
      res->class = HEAD;
      if (debug) print_mem(stdscr, temp-len2, ws);
      
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
      if (pop_stack) stack -= 2;
      ++((primitive-1)->op.index);
      ++(arg1->op.addr);
      ++(arg2->op.addr);
      pc = primitive;
      return;
   }

   if (debug) {
      outstring(stdscr, "\n\r  NOT HANDLED");
      wrefresh(stdscr);
   }
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
		case EX_VAR:	return(((*arg1)->op.addr == (*arg2)->op.addr));
      case SYM:
      case PRIM_0:
      case PRIM_1:
      case PRIM_2:   return(((*arg1)->op.sym == (*arg2)->op.sym));

      case UBV:      return((*arg1)->op.index == (*arg2)->op.index);

      case EP:			{
								node *t1 = lookup((*arg1)->op.addr, 0);
      						node *t2 = lookup((*arg2)->op.addr, 0);
      						return(nodes_equal(&t1, &t2, reduced));
      					}

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
                     else return((*arg1)->op.addr == (*arg2)->op.addr);


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


/* WRAP_LAMBDAS
/* Wrap an expression in N lambda bindings, and replace the original
/* expression with the new one.
*/

wrap_lambdas(n, exp)
int n;
node *exp;
{
   node *new_exp = ws + 1;
   symbol *var = symbol_lookup("%gv%", SYM);
   
   while (n-- > 0) {
      (++ws)->class = BINDER; ws->type = LAMBDA; ws->op.sym = var;
   }
   *(++ws) = *exp; ws->class = HEAD;
   exp->type = PTR; exp->op.addr = new_exp;
}
