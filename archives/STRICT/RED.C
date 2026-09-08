/* Head Order Lambda Reducer
/* Mike Hilton, 17 July 1989
/*
*/

#include <stdio.h>
#include <time.h>
#include <sys\types.h>
#include <sys\timeb.h>
#include <setjmp.h>
#include "lrs.h"


#define WARNING_SIZE 100    /* free memory size that evokes warning */

int   argcount;         /* number of preceeding argument nodes */
int   binding_offset;   /* number of preceeding unapplied lambdas */
int   frozen_redcnt;    /* used during inhibition to hold old red. count */
int   mode;             /* direction of traversal: Problem, Result, Head */
int   reductions;       /* count of reductions performed this invocation */
int   red_limit;        /* maximum number of reductions allowed */
int   total_reds;	/* total number of reductions performed */

node  *env;    /* current ENVironment context */
node  *fs;     /* Free Space pointer, where environments and structs go */
node  *inhibit; /* address where inhibition of reduction ends */
node  *pc;     /* Program Counter, node currently being executed */
node  *ws;     /* Working graph Space pointer, where result graph is built */

node *primitive;  /* Address of primitive waiting to be fired */
int   prim_args;  /* Number of strict arguments remaining to be reduced */

union control *stack;   /* Top of control stack   */
union control *aux;     /* Top of auxillary stack */

node *max_graph;	/* tracks max graph size */
union control *max_stack;	/* tracks max stack size */
union control *max_aux, *initial_aux;
node *max_env, *initial_env;
unsigned long instructs;	/* number of instructions executed */
extern int stats;				/* flags if statistics are being gathered */

extern jmp_buf abort_context;		/* Error restart handler. */


/* REDUCE
/* Reduces an expression graph with root at START, returning a pointer
/* to the root of the result graph.  WORKSPACE is a pointer into low graph
/* space that indicates where working memory (where the result graph is
/* constructed) begins.  FREESPACE is a pointer into high graph space 
/* that indicates where free memory (where the environments and objects go)
/* begins.  RECURSIVE is a boolean flag that marks whether the reducer 
/* is being called recursively;  this should normally be 0.
/*
/* Returns a pointer to the root of the reduced graph.
*/

node *reduce(start, workspace, freespace, reds_allowed, recursive)
node *start, *workspace, *freespace;
int reds_allowed, recursive;
{
   node *red(), *answer;
   extern struct timeb start_time, stop_time;
   void init_stats();
   
   pc = start;
   ws = workspace;
   fs = freespace;
   
   argcount = 0;
   aux = &constack[CONTROL_SIZE-1];
   env = freespace;
   inhibit = NULL;
   mode = PROBLEM;
   prim_args = -1;
   red_limit = reds_allowed;
   reductions = 0;
   stack = constack; 
   if (! recursive) {   
      binding_offset = 0;
      init_stats();
   }

   ws->head = FALSE;   ws->type = STOP;
   ftime(&start_time);
   answer = red();
   ftime(&stop_time);
   total_reds += reductions;
   return(answer);
}


/* JUMP_SUBGRAPH
/* Before reducing a subgraph hanging to the right of an ap node,
/* some housekeeping chores need to be done.  The JOIN instruction
/* is somewhat of an inverse to this function.
*/

void jump_subgraph()
{
   (++stack)->intval = prim_args;
   (++stack)->ptr = primitive;
   argcount = 0;   
   mode = PROBLEM;
   prim_args = -1;   
}

/* LOOKUP
/* Looks up a value in the environment.  ENV is a pointer to the start
/* of the environment context and INDEX is the binding index of the
/* value to be looked up.
/*
/* Returns a pointer to the environment entry of the value.
*/

node *lookup(env, index)
node *env;
int index;
{

   while (1) {
#ifdef DEBUG_LOOKUP
      fprintf(stdout,"\n  lookup: env = %p, index = %d, value = ", 
               env, index);
      print_node(stdout, env);
#endif      
      if (env->type == MARKER) 
         env = env->op.addr;
      else if (index == 0) 
         return(env);
      else {
         ++env;
         --index;
      }
   }
}


/* MAKE_CLOSURE
/* Creates a closure in free space, with CODE a pointer to the graph
/* and CONTEXT a pointer to the environment context. 
/*
/* Returns a pointer to the closure.
*/

node *make_closure(code, context)
node *code, *context;
{
   (--fs)->type = CL_ENV; fs->op.addr = context;
   (--fs)->type = CL_PTR; fs->op.addr = code;
   return(fs);
}


/* MAKE_SUSPEND
/* Creates a suspension closure in free space, with CODE a pointer to the graph
/* and CONTEXT a pointer to the environment context. A suspension closure is
/* different that a regular closure in the the current value of binding_offset
/* (BN) is stored with the closure; this value is used when reducing delayed 
/* expressions inside structures.
/*
/* Returns a pointer to the suspension closure.
*/

node *make_suspend(code, context, bn)
node *code, *context;
int bn;
{
   (--fs)->type = CL_BN;  fs->op.intval = bn;
   (--fs)->type = CL_ENV; fs->op.addr = context;
   (--fs)->type = CL_PTR; fs->op.addr = code;
   return(fs);
}



/* MOVE_BACKWARD
/* This routine is invoked after execution of many instructions in the
/* RESULT mode.  It is a useful point to check on certain conditions,
/* such as:
/*    if a primitive should be fired
/*    decrementing a strict primitive's argument count
/*    un-inhibiting the reduction count
*/

void move_backward()
{
   --prim_args;
   --pc;                /* make sure prims take this into account! */
   if (prim_args == 0) 
      (*((primitive->op.sym)->def.prim)) ();
   if (pc == inhibit) { /* turn inhibition off */
      reductions = frozen_redcnt;
      inhibit = NULL;
   }
}   


/* PUSH_MARKER
/* If the current environment pointer is not the same as the free space
/* pointer, then push an environment jump marker onto the free space
/* and point ENV to the marker.  Also check to see if out of space.
*/

void push_marker()
{
   if (ws + WARNING_SIZE > fs) {
      if (fs < ws) 
         fprintf(stderr, "\nOUT OF MEMORY!!");
      else
         fprintf(stderr, "\nRUNNING OUT OF MEMORY!!");
   }
   
   if (env != fs) { 
      (--fs)->type = MARKER; 
      fs->op.addr = env;
   }
   env = --fs;
}






/*
/* Instruction Set Implementation
*/


/* CLOSURE
/* Closures contain the information needed to reduce subgraphs.
/* It is possible that the value of a closure has already been computed
/* and has overwritten the original closure contents;  this must be
/* checked for.
*/

void inst_closure()
{
   node *closure = pc->op.addr;
   void inst_inert();
   
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      
      case RESULT:   
            if (closure->type == CL_PTR) {
               (++ws)->head = FALSE; ws->type = JOIN; ws->op.addr = pc;
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               jump_subgraph();
            }
            else {                  /* shared value */
#ifdef DEBUG
               fprintf(stdout, "\nclosure -- SHARED VALUE!");
#endif               
               *pc = *closure;
               pc->head = FALSE;
               move_backward();
            }
            break;
                     
      case HEAD:
            if (closure->type == CL_PTR) {
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               mode = PROBLEM;
            }
            else {               /* shared value */
#ifdef DEBUG
               fprintf(stdout, "\nclosure -- SHARED VALUE!");
#endif               
               pc = closure;
            }
            break;
   }
}



/* INST_INERT
/* Simply copies over the contents of the PC into the result graph.
*/

void inst_inert()
{
   switch (mode) {
      case PROBLEM:  ++argcount; *(++ws) = *(pc++); break;
      case RESULT:   move_backward(); break;                  
      case HEAD:     *(++ws) = *pc; pc = ws-1; mode = RESULT; break;
   }
}





/* JOIN
/* Join instructions are used to mark the end of reducing an argument
/* and provide the address for rejoining the parent graph.  A join 
/* should only be found while in the RESULT mode.
/* 
/* Sharing takes place here.
*/

void inst_join()
{
   node *destination = pc->op.addr;
   node *result = pc + 1;
   
   if (result->head == TRUE) {               /* atomic result  */
      if ((destination->type == CLOSURE)  ||
          (destination->type == SUSPEND)) {    /* share result via closure */
         *(destination->op.addr) = *result;
      }
      *destination = *result;                /* write result into spine */
      destination->head = FALSE;
      ws -= 2;
   }
   else {
      destination->op.addr = result;
      if (destination->type != LETREC) destination->type = PTR;
   }
   
   pc = destination;
   primitive = (stack--)->ptr;
   prim_args = (stack--)->intval;
   move_backward();
}

   

/* LAMBDA
/* Lambda abstraction binds argument if there is one, else pushes an
/* unbound variable marker onto the environment if there is not.
*/

void inst_lambda()
{
   switch (mode) {
      case PROBLEM:  
         if ((argcount == 0) || (reductions == red_limit)) {
            /* push an unbound variable onto env */
            ++binding_offset;
            push_marker();
            env->head = TRUE; env->type = UBV; 
            env->op.index = binding_offset;
            *(++ws) = *pc;
         } 
         else {
            /* push the preceeding arg onto env */
            ++reductions;
            --argcount;
            switch (ws->type) {
               case PTR:   
                  {
                     node *closure; 
                     closure = make_closure(ws->op.addr, (stack--)->ptr);
                     push_marker();
                     env->head = TRUE; env->type = CLOSURE; 
                     env->op.addr = closure;
                     break;
                  }

               case VAR:   push_marker();
                           env->head = TRUE; env->type = UBV; 
                           env->op.index = binding_offset - ws->op.index;
                           break;

               default:    push_marker();
                           *env = *ws;
                           env->head = TRUE;
                           break;
            }
            --ws;
         }
         ++pc;
         break;

      case RESULT:   --binding_offset;
                     move_backward();
                     break;                     
   }
}


/* LETREC
/* Recursive binding constructor.  The Letrec deposits its operand into
/* the environment.
*/

void inst_letrec()
{
	switch (mode) {
		case PROBLEM:
			{
				if (reductions != red_limit) {
					if (((pc->op.addr+1)->head == FALSE) ||
						 ((pc->op.addr+1)->type == VAR)) {
						node *closure;
					   (--fs)->type = NOOP; fs->op.addr = NULL;						
					   (--fs)->type = NOOP; fs->op.addr = NULL;
					   (--fs)->type = NOOP; fs->op.addr = pc->op.addr;
						closure = fs;
						push_marker();
						env->head = TRUE; env->type = REC;
						env->op.addr = closure;
					}
					else {
						push_marker();
						*env = *(pc->op.addr+1);
					}
				}
				else {
					++binding_offset;
					push_marker();
					env->head = TRUE; env->type = UBV;
					env->op.index = binding_offset;
				}
				inst_inert();
				break;
			}
	

		case RESULT:
			{
				  /* Recreate previous env context, begin reducing arg */
              env = (stack--)->ptr;  /* Restore env context */
              (++ws)->head = FALSE; ws->type = JOIN; ws->op.addr = pc;
              pc = pc->op.addr; 
              jump_subgraph();
              break;
   		}
   		
	}
}


/* PRIM_0
/* Nonstrict primitives.  Invoke the primitive function if in the head.
*/

void inst_prim_0()
{
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      case RESULT:   inst_inert(); break;
      case HEAD:     (*((pc->op.sym)->def.prim)) (); break;
   }
}


/* PRIM_1
/* Unary strict primitives.  If one or more arguments are available,
/* set up the firing registers appropriately.
*/

void inst_prim_1()
{
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      case RESULT:   inst_inert(); break;

      case HEAD:     inst_inert();
                     if ((argcount >= 1) && (reductions != red_limit)) {
                        primitive = pc + 1;
                        prim_args = 1;
                     }
                     break;
   }
}


/* PRIM_2
/* Binary strict primitives.  If two or more arguments are available,
/* set up the firing registers appropriately.
*/

void inst_prim_2()
{
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      case RESULT:   inst_inert(); break;

      case HEAD:  inst_inert();
                  if ((argcount >= 2) && (reductions != red_limit)) {
                     primitive = pc + 1;
                     prim_args = 2;
                  }
                  break;
   }
}
                  


/* PTR
/* 
*/

void inst_ptr()
{
   switch (mode) {
      case PROBLEM:  /* Push env onto control stack for retrieval later */
                     (++stack)->ptr = env;
                     ++argcount;
                     *(++ws) = *(pc++);
                     break;
                     
      case RESULT:   /* Recreate previous env context, begin reducing arg */
                     env = (stack--)->ptr;  /* Restore env context */
                     (++ws)->head = FALSE; ws->type = JOIN; ws->op.addr = pc;
                     pc = pc->op.addr; 
                     jump_subgraph();
                     break;
   }
}



/* REC
/* Recursive closure.  If there are reductions left, expand the closure.
/* If not, copy the letrec block around the variable.
*/

void inst_rec()
{
	node *closure = pc->op.addr;

	switch (mode) {
		case HEAD:
			{
				if (reductions != red_limit) {
					pc = closure->op.addr+1;			/* code pointer */
					env = (++closure)->op.addr;		/* env pointer */
					mode = PROBLEM;
					++reductions;
				}
				else inst_rec_1();
				break;
			} 

		case RESULT:
			{
            (++ws)->head = FALSE; ws->type = JOIN; ws->op.addr = pc;
				if (reductions != red_limit) {
					++reductions;
   	         pc = closure->op.addr+1;		/* Restore code */
      	      env = (++closure)->op.addr; 	/* Restore context */
         	   jump_subgraph();
				}
				else {
					jump_subgraph();
					inst_rec_1();
				}
				break;
			}

		case PROBLEM:	inst_inert(); break;
	}
}

inst_rec_1()
{
	node *closure = pc->op.addr;
	node *ptr = (closure + 2)->op.addr;
	int count = 0;
	int index = 0;
#ifdef DEBUG
	fprintf(stdout, "\ninst_rec_1: ptr = (%p) ", ptr);
	print_node(stdout, ptr);
#endif

	env = (closure+1)->op.addr;		/* restore context */
	while (ptr->type == LETREC) {
#ifdef DEBUG
	fprintf(stdout, "\ninst_rec_1:  copying letrec %s", ptr->op.addr->op.sym->print_name);
#endif
		index++; count++;
		if (ptr->op.addr == closure->op.addr) index = 0;
		*(++ws) = *(ptr++);		/* copy the letrecs */
		++binding_offset;
		push_marker();				/* push unbound var into env */
		env->head = TRUE; env->type = UBV;
		env->op.index = binding_offset;
	}
	while (count-- > 0) {(++stack)->ptr = env;}
#ifdef DEBUG
	fprintf(stdout, "\ninst_rec_1: copying rup (%p) to (%p) ", ptr, ws+1);
	print_node(stdout, ptr);
#endif
	*(++ws) = *ptr;				/* copy RUP instruction */
	(++ws)->head = TRUE;			/* insert head var  */
	ws->type = VAR; ws->op.index = index;
	mode = RESULT;					/* reverse directions */
	pc = ws-1;
}


/* RUP
/* Recursive UPdate.  Modifies the top N entries in the environment
/* (where N is the integer operand of the RUP instruction) such that
/* if the entry is a closure, the environment pointer of the closure
/* is made to point at the current top of environment.  This is used
/* in the implementation of Letrecs.
*/

void inst_rup()
{
	switch (mode) {
		case PROBLEM:
			{
				int n = pc->op.intval;
				node *ptr = env;
				node *recstart = pc - n;

				if (red_limit != reductions) {
					ws -= n;
					while (n > 0) {
						if (ptr->type == MARKER) 
							ptr = ptr->op.addr;
						else {
							if (ptr->type == REC)  {
								(ptr->op.addr + 1)->op.addr = env;
								(ptr->op.addr + 2)->op.addr = recstart;
#ifdef DEBUG1
	fprintf(stdout, "\n	modifying loc %p to be %p\n	", (ptr->op.addr+1), env);
	print_node(stdout, ptr);
#endif
								n--;
								ptr++;
							}
							else {
#ifdef DEBUG1
	fprintf(stdout,"\n	not modifying loc %p", ptr);
#endif						
								ptr++;
								n--;
							}
						}
					}
					pc++;
					/* if the body is just a (letrec) var, don't incr reductions */
					if (pc->type != VAR || pc->head != TRUE)
						++reductions;

				}
				else {
					/* push env onto stack for each letrec */
					while (n-- > 0) (++stack)->ptr = env;
					inst_inert();
				}
				break;
			}


		case RESULT: inst_inert(); break;
	}
}




/* SUSPEND
/* A suspension is a closure whose reduction has been delayed by
/* structure creation.  It acts just like a closure, except that
/* the binding number must be retrieved from the suspension.
*/

void inst_suspend()
{
   node *closure = pc->op.addr;
   
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      
      case RESULT:   
            if (closure->type == CL_PTR) {
               (++ws)->head = FALSE; ws->type = JOIN; ws->op.addr = pc;
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               binding_offset = (++closure)->op.intval;  /* Restore bn */
               jump_subgraph();
            }
            else {                  /* shared value */
#ifdef DEBUG
               fprintf(stdout, "\nsuspended closure -- SHARED VALUE!");
#endif               
               *pc = *closure;
               pc->head = FALSE;
               move_backward();
            }
            break;
                     
      case HEAD:
            if (closure->type == CL_PTR) {
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               binding_offset = (++closure)->op.intval; /* Restore bn */
               mode = PROBLEM;
            }
            else {               /* shared value */
#ifdef DEBUG
               fprintf(stdout, "\nsuspended closure -- SHARED VALUE!");
#endif               
               pc = closure;
            }
            break;
   }
}
      

/* SYMBOL
/* In problem mode, symbols are just copied to the result graph. In result
/* or head mode, the symbol is checked to see if it has an associated
/* definition; if it does, the definition is expanded into the graph.
*/

void inst_symbol()
{
   switch (mode) {
      case PROBLEM:  inst_inert(); break;

      case RESULT:   if ((reductions == red_limit) ||
                         (pc->op.sym->def.user == NULL)) {
                        inst_inert();
                        break;
                     }
                     else if (pc->op.sym->def.user != NULL) {
                        pc->type = PTR;
                        pc->op.addr = pc->op.sym->def.user;
                        (++stack)->ptr = env;
                        ++reductions;
                        break;
                     }

      case HEAD:     if ((reductions == red_limit) ||
                         (pc->op.sym->def.user == NULL)) {
                        inst_inert();
                        break;
                     }
                     else if (pc->op.sym->def.user != NULL) {
                        pc = pc->op.sym->def.user;
                        ++reductions;
                        mode = PROBLEM;
                        break;
                     }                     
   }
}


/* UBV
/* UnBound Variables only come from the environment.  They need to
/* have their binding index corrected to its proper value.
*/

void inst_ubv()
{
   switch (mode) {
      case RESULT:   pc->type = VAR; 
                     pc->op.index = binding_offset - pc->op.index;
                     move_backward();
                     break;
                     
      case HEAD:     (++ws)->head = TRUE; ws->type = VAR; 
                     ws->op.index = binding_offset - pc->op.index;
                     pc = ws - 1;
                     mode = RESULT;
                     break;
   }
}



/* VAR
/* Variables lookup values in the environment.
*/

void inst_var()
{
   switch (mode) {
      case PROBLEM:  ++argcount;
                     *(++ws) = *(lookup(env, pc->op.index));
                     ws->head = FALSE;
                     ++pc;
                     break;
            
      case RESULT:   move_backward(); break;
      
      case HEAD:     pc = lookup(env, pc->op.index);
                     mode = PROBLEM;
                     break;
   }
}




        
/* RED
*/

node *red()
{
	void get_stats();

	
   while (TRUE) {
      if (ws >= fs) {
         fprintf(stderr, "\nOUT OF GRAPH MEMORY!");
			longjmp(abort_context, 1);
      }
      if (stack >= aux) {
         fprintf(stderr, "\nOUT OF STACK MEMORY!");
         longjmp(abort_context, 1);
      }
      if ((mode == PROBLEM) && (pc->head == TRUE)) mode = HEAD;
#ifdef DEBUG
      fprintf(stdout, "\n\nmode = ");
      switch (mode) {
         case PROBLEM: fprintf(stdout, "PROBLEM"); break;
         case RESULT:  fprintf(stdout, "RESULT "); break;
         case HEAD:    fprintf(stdout, "HEAD   "); break;
      }
      fprintf(stdout, "   pc  = %p   ", pc);   
      print_node(stdout, pc);
      fprintf(stdout, "\n                 env = %p   ", env);
      print_node(stdout, env);
#endif      
      switch (pc->type) {
			case CONS:		inst_inert(); break;
         case CLOSURE:  inst_closure(); break;
         case INT:      inst_inert(); break;
         case FLOAT:    inst_inert(); break;
         case JOIN:     inst_join(); break;
         case LAMBDA:   inst_lambda(); break;
			case LET:		inst_lambda(); break;
			case LETREC:	inst_letrec(); break;
			case LETSTAR:	inst_lambda(); break;
         case PRIM_0:   inst_prim_0(); break;
         case PRIM_1:   inst_prim_1(); break;
         case PRIM_2:   inst_prim_2(); break;
         case PTR:      inst_ptr(); break;
			case REC:		inst_rec(); break;
			case RUP:		inst_rup(); break;
         case STOP:     return(pc+1);
         case STRUCT:   inst_inert(); break;
         case SUSPEND:  inst_suspend(); break;
         case SYM:      inst_symbol(); break;
         case UBV:      inst_ubv(); break;
         case VAR:      inst_var(); break;
         
         default: fprintf(stderr, "\nred: pc = %p unexpected type: ", pc);
                  print_node(stderr, pc);
                  if (stderr != stdout) {
                     fprintf(stdout, "\nred: unexpected type: ");
                     print_node(stdout, pc);
                  }
                  bomb();
                  break;
      }
      if (stats) get_stats();
#ifdef DEBUG
      fprintf(stdout, "\n                 ws  = %p   ", ws);
      print_node(stdout, ws);
      fprintf(stdout, "\n           stack-top (%p) = %p or %d,  bn = %d", 
            stack, stack->ptr, stack->intval, binding_offset);
      fprintf(stdout, "\n                 aux (%p) = %p or %d",
				aux, aux->ptr, aux->intval);
#endif            
   }
}



/* GET_STATS
/* Collects statistics about machine execution.
*/

void get_stats()
{
	++instructs;
	if (max_graph < ws) max_graph = ws;
	if (max_env > fs) max_env = fs;
	if (max_stack < stack) max_stack = stack;
	if (max_aux > aux) max_aux = aux;
}


/* INIT_STATS
/* Initialize statistics gathering equipment.
*/

void init_stats()
{
	instructs = 0;
	max_graph = ws;
	initial_env = fs;
	max_env = fs;
	max_stack = stack;
	initial_aux = aux;
	max_aux = aux;
}
