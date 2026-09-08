/* Primitive Operators for the Lambda Reduction System
/* Mike Hilton, 19 July 1989
/*
/* This file contains the implementation details of the LRS builtin
/* primitive operators.
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
symbol *and;
symbol *equal;
symbol *nil;


/* List primitives, found in the file LISTS.C */
void prim_cons(), prim_car(), prim_cdr(), prim_null();

/* Arithmetic primitives, found in the file ARITH.C */
void prim_add(), prim_sub(), prim_mult(), prim_div(), prim_mod();
void prim_min(), prim_max();
void prim_eq(), prim_neq(), prim_gt(), prim_gte(), prim_lt(), prim_lte();
void prim_abs(), prim_sqrt(), prim_minus(), prim_inc(), prim_dec();
void prim_even(), prim_odd(), prim_pos(), prim_neg();
void prim_atom();


/* Primitives found in this file. */
void prim_if(), prim_y(), prim_and(), prim_or(), prim_not();
void prim_pack(), prim_select(), prim_equal();

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
   {"sqrt", PRIM_1, prim_sqrt},
   {"minus", PRIM_1, prim_minus},
   {"1+", PRIM_1, prim_inc},
   {"1-", PRIM_1, prim_dec},
   {"even?", PRIM_1, prim_even},
   {"odd?", PRIM_1, prim_odd},
   {"positive?", PRIM_1, prim_pos},
   {"negative?", PRIM_1, prim_neg},
	{"atom?", PRIM_1, prim_atom},
   {"if", PRIM_0, prim_if},
   {"Y", PRIM_0, prim_y},
   {"and", PRIM_0, prim_and},
   {"or", PRIM_0, prim_or},   
   {"not", PRIM_1, prim_not},      
   {"pack", PRIM_0, prim_pack},
   {"select", PRIM_0, prim_select},
   {"equal", PRIM_2, prim_equal},
   {"cons", PRIM_0, prim_cons},
   {"car", PRIM_0, prim_car},
   {"cdr", PRIM_0, prim_cdr},
	{"null?", PRIM_1, prim_null},
   {"end_of_primtab", 0, NULL}
};


/* INSTALL_PRIMITIVES
/* The primitive operator names and types have to be entered into the
/* symbol table so the compiler will know about them.
*/

void install_primitives()
{
   symbol *symbol_lookup(), *sym;
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
   equal = symbol_lookup("equal", PRIM_2);
	nil = symbol_lookup("nil", SYM);

}




/* IF
/* The basic conditional for the LRS system.
*/

void prim_if()
{
   switch (mode) {
      case HEAD:  inst_inert();
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
            else pc->head = TRUE;
#ifdef DEBUG
            fprintf(stdout, " -- true branch taken, pc = %p", convert(pc));
#endif            
         }
         else {
            pc = pc - 2;
            if (pc->type == PTR) pc = pc->op.addr;
            else pc->head = TRUE;
#ifdef DEBUG
            fprintf(stdout, " -- false branch taken, pc = %p", convert(pc));
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
      temp.head = TRUE;
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
      case HEAD:  inst_inert();
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
               arg->head = TRUE;
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
               arg->head = TRUE; arg->type = SYM; arg->op.sym = false;
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
      case HEAD:  inst_inert();
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
               arg->head = TRUE;
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
               arg->head = TRUE; arg->type = SYM; arg->op.sym = true;
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
   arg->head = TRUE;
   ws = arg;
}





/* PACK
/* Structure creation primitive with lazy semantics.  The form of usage is:
/*    PACK tag size arg1 ... argN
/* where N=size.  TAG is the name given to the type of the structure.
/* The ARG's are the elements of the structure.
*/

void prim_pack()
{
   switch (mode) {
      case HEAD:  
         inst_inert();
         if ((argcount >= 2) && (reductions != red_limit)) {
            primitive = pc + 1;
            prim_args = 2;
            (--aux)->intval = argcount - 2;
         }
         else {
#ifdef DEBUG
            fprintf(stdout, "\npack primitive -- NOT FIRING! args or red_limit");
#endif
         }                        
         break;
         
      case RESULT:
         {
            node *tag  = pc + 2;
            node *size = pc + 1;
            node *res = fs - 1;
            int i;
            node *next, *make_suspend();
            
            argcount = (aux++)->intval;
            /* check type of tag and size */
            if ((tag->type != SYM) && (size->type != INT)) {
#ifdef DEBUG
               fprintf(stdout, "\npack primitive -- NOT FIRING! tag or size");
#endif               
               return;
            }
            /* check to see if all args are available */
            if (argcount < size->op.intval) {
#ifdef DEBUG
               fprintf(stdout, "\npack primitive -- NOT FIRING! argcount");
#endif
					frozen_redcnt = reductions;
					reductions = red_limit;
					inhibit = pc - argcount;
               return;
            }

#ifdef DEBUG
            fprintf(stdout, "\npack primitive -- creating struct");
#endif               
            (--fs)->head = TRUE; fs->type = SYM; fs->op.sym = tag->op.sym;
            (--fs)->head = TRUE; fs->type = INT; fs->op.intval = size->op.intval;
            next = fs;
            fs -= size->op.intval;     /* allocate space for the elements */

            for(i = size->op.intval; i > 0; i--) {
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
                  else {
                     *next = *(pc->op.addr);
                  }
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
            ws->head = TRUE; ws->type = STRUCT; ws->op.addr = res;
            ++reductions;
            return;
         }
   }
}



/* SELECT
/* Structure accessing primitive.  Its usage is of the form
/*    SELECT tag element structure
/* where TAG is the type the structure should be, ELEMENT is
/* the index of the element to be extracted, and STRUCTURE is the
/* structure to be accessed.
*/

void prim_select()
{
   switch (mode) {
      case HEAD:  inst_inert();
                  if ((argcount >= 3) && (reductions != red_limit)) {
                     primitive = pc + 1;
                     prim_args = 3;
                     (--aux)->intval = argcount - 3;
                  }
                  break;
                  
      case RESULT:
         {
            node *structure = pc + 1;
            node *elem      = pc + 2;
            node *tag       = pc + 3;
            
#ifdef DEBUG
            fprintf(stdout, "\nselect primitive -- ");
#endif                        
            argcount = (aux++)->intval;
            /* check type and size of structure */
            if (structure->type != STRUCT) {
#ifdef DEBUG
            fprintf(stdout, "NOT FIRING! not a structure");
#endif
               return;
            }
            structure = structure->op.addr;
            if (structure->op.sym != tag->op.sym) {
#ifdef DEBUG
               fprintf(stdout, "NOT FIRING! wrong type");
#endif
               return;
            }
            --structure;
            if (structure->op.intval < elem->op.intval) {
#ifdef DEBUG
               fprintf(stdout, "NOT FIRING! selector out of bounds");
#endif               
               return;
            }
#ifdef DEBUG
            fprintf(stdout, "firing");
#endif
            ws = pc;             /* prepare to move forward again */
            mode = PROBLEM;
            pc = structure - elem->op.intval;  /* accessed element */

            /* arrange for element to be updated with value if possible */
            if ((pc->type == SUSPEND) && (ws->type == JOIN)) {
               *(ws->op.addr) = *pc;
#ifdef DEBUG
               fprintf(stdout, "\nselect primitive -- sharing value");
#endif               
           }
            return;
         }
   }
}
     


/* EQUAL
/* Alpha-equality predicate.  The two arguments are first reduced and 
/* then compared. The comparison of structures is delayed as long as 
/* possible, in order to avoid reducing structure elements.
*/

int structs;
int lambdas;

void prim_equal()
{
   node *arg1   = --primitive;
   node *arg2   = --primitive;
   node *res    = primitive;
   int   first = TRUE;
   union control *stack_orig = stack;
   union control *aux_orig = aux;
   int node_equal();
               
#ifdef DEBUG
   fprintf(stdout, "\nequal primitive: arg1 = %p, arg2 = %p", convert(arg1),
            convert(arg2));
   print_mem(stdout, arg2, ws);
   fprintf(stdout, "\n");
#endif

   if (reductions == red_limit) return;
   structs = 0;               
   lambdas = 0;
   
   /* walk down the args and compare elements */
   Down:

#ifdef DEBUG
      fprintf(stdout, "\nequality loop");
#endif

      if (node_equal(arg1, arg2) == FALSE) {
         if (((arg1->type == VAR) && (arg1->op.index >= lambdas)) ||
             ((arg2->type == VAR) && (arg2->op.index >= lambdas)))
               goto Pass;
         else goto Fail;
      }
      if (first == TRUE && stack_orig == stack && aux_orig == aux)
         goto Succeed;

      if ((first == FALSE) && (arg1->head == FALSE)) {
         ++arg1;
         ++arg2;
         goto Down;
      }
      first = FALSE;
      
      /* If there are any more subgraphs to do, get pointer to them and */
      /* loop back to label Down. */
      if (stack_orig != stack) {
#ifdef DEBUG
         fprintf(stdout, "\nequality loop -- popping pointers");
#endif                  
         arg1 = (stack--)->ptr;
         arg2 = (stack--)->ptr;
         lambdas = (stack--)->intval;
         goto Down;
      }
      
   /* The two arguments are now known to be equal except for possible */
   /* suspended closures from structures */

   if (structs == 0) goto Succeed;
   else {
      /* Build a graph that reduces and compares the closures separately */
      node *base, *argptr;
      
      base = fs - (structs * 3) - 1;
      base->head = TRUE; base->type = PRIM_0; base->op.sym = and;
      argptr = base;
      for (; structs > 0; structs--) {
         ++argptr;
         --base;
         base->head = FALSE; base->type = PTR; base->op.addr = argptr;
         *argptr = *((aux++)->ptr); argptr->head = FALSE;
         ++argptr;
         *argptr = *((aux++)->ptr); argptr->head = FALSE;
         ++argptr;
         argptr->head = TRUE; argptr->type = PRIM_2; argptr->op.sym = equal;
      }
#ifdef DEBUG
      fprintf(stdout, "\nequal -- new graph created");
      print_mem(stdout, base, fs);
#endif
      fs = base;
      pc = base;
      ws = res - 1;
      mode = PROBLEM;
      argcount = 0;
      return;
   }
      

   Pass:
#ifdef DEBUG
      fprintf(stdout, "\nequal primitive -- Passing, not firing");
#endif
      stack = stack_orig;
      aux = aux_orig;
      return;
            
   Succeed:
      res->head = TRUE; res->type = SYM; res->op.sym = true;
#ifdef DEBUG
      fprintf(stdout, "\nequal primitive -- TRUE");
      print_mem(stdout, res, ws);
#endif      
      ws = res;
      ++reductions;
      return;
   
   Fail:
      res->head = TRUE; res->type = SYM; res->op.sym = false;
#ifdef DEBUG
      fprintf(stdout, "\nequal primitive -- FALSE");
      print_mem(stdout, res, ws);
#endif
      stack = stack_orig;
      aux = aux_orig;
      ws = res;
      ++reductions;
      return;
}




/* NODE_EQUAL
/* Predicate to test if two nodes are equal.  To be used in conjunction with
/* the PRIM_EQUAL.
*/

int node_equal(arg1, arg2)
node *arg1, *arg2;
{
   
#ifdef DEBUG
      fprintf(stdout, "\nnode_equal -- arg1 %p = ", convert(arg1));
      print_node(stdout, arg1);
      fprintf(stdout, "  arg2 %p = ", convert(arg2));
      print_node(stdout, arg2);
#endif        

   if ((arg1->head != arg2->head) || (arg1->type != arg2->type))
      return(FALSE);
   else 
      switch (arg1->type) {
         case FLOAT:    if (arg1->op.floval != arg2->op.floval) return(FALSE);
                        else return(TRUE);
         case INT:      if (arg1->op.intval != arg2->op.intval) return(FALSE);
                        else return(TRUE);
         case LAMBDA:   ++lambdas; 
                        return(TRUE);      /* disregard name info */
         case PTR:      if (arg1->op.addr != arg2->op.addr) {      
                           (++stack)->intval = lambdas;
                           (++stack)->ptr = arg1->op.addr;   
                           (++stack)->ptr = arg2->op.addr;
                        }
                        return(TRUE);
         case STRUCT:   if (arg1->op.addr != arg2->op.addr) {
                           node *s1 = arg1->op.addr;
                           node *s2 = arg2->op.addr;
                           int elnum;

                           if (s1->op.sym != s2->op.sym) return(FALSE);
                           --s1; --s2;
                           for(elnum = s1->op.intval; elnum > 0; elnum--) {
                              /* Check each element for equality */
                              --s1; --s2;
                              if ((s1->type == SUSPEND) || 
                                  (s2->type == SUSPEND)) {
                                 (--aux)->ptr = s1;
                                 (--aux)->ptr = s2;
                                 ++structs;
                              }
                              else if (node_equal(s1, s2) == FALSE)
                                 return(FALSE);
                           }
                        }
                        return(TRUE);
                           
         case SYM:
         case PRIM_0:
         case PRIM_1:
         case PRIM_2:   if (arg1->op.sym != arg2->op.sym) return(FALSE);
                        return(TRUE);
         case VAR:      if (arg1->op.index != arg2->op.index) return(FALSE);
                        return(TRUE);
      }
}


