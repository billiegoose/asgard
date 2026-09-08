/* Head Order Lambda Reducer
/* Mike Hilton, 8 Dec 1989
/*
*/
#define DEBUG_LOOKUP
#undef DECODE_TABLE

#include <stdio.h>
#include <time.h>
#ifdef IBM
#include <sys\types.h>
#include <sys\timeb.h>
#endif
#ifdef SUN
#include <sys/types.h>
#include <sys/timeb.h>
#endif
#include <setjmp.h>
#include <curses.h>
#include "lrs.h"

#define WARNING_SIZE 10    /* free memory size that evokes warning */


/* IF DECODE_TABLE IS DEFINED...
/* Instructions are decoded using a table indexed by instruction type.
/* The table consists of pointers to the functions which implement the
/* instructions.
*/
typedef void (*P_VOID_FUNC)();
P_VOID_FUNC decode[35];



int   argcount;         /* number of preceeding argument nodes */
int   binding_offset;   /* number of preceeding unapplied lambdas */
unsigned long  frozen_redcnt;    /* used during inhibition to hold old red. count */
int   mode;             /* direction of traversal: Problem, Result, Headm */
unsigned long  reductions;       /* count of reductions performed this invocation */
unsigned long  red_limit;        /* maximum number of reductions allowed */
unsigned long  total_reds;       /* total number of reductions performed */

node  *env;    /* current ENVironment context */
node	*ex_ptr;	/* pointer to the existential variable list area at top of heap*/
node  *fs;     /* Free Space pointer, where environments and structs go */
node  *inhibit; /* address where inhibition of reduction ends */
node  *pc;     /* Program Counter, node currently being executed */
node  *ws;     /* Working graph Space pointer, where result graph is built */

node *primitive;  /* Address of primitive waiting to be fired */
int   prim_args;  /* Number of strict arguments remaining to be reduced */

control *stack;   /* Top of control stack   */
control *aux;     /* Top of auxillary stack */

extern jmp_buf abort_context;    /* Error restart handler. */

node *max_graph, *max_env, *initial_env;
control *max_stack, *max_aux, *initial_aux;
reset *max_reset;
unsigned long instructs;   /* number of instructions executed */
extern int stats;          /* flags if statistics are being gathered */
extern int debug;          /* flags if debug tracing to be printed */
extern reset *reset_ptr;	/* pointer to top of reset_list */
extern symbol *neutral;
extern node *heap, *heap_space;

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
   void init_stats(), build_decode_table(), sum_times();

   if (debug) {
      foutstring(stdscr, "\n\rREDUCE: start = %p, ws = %p, fs = %p, reds = %d, rec = %s\n",
         start, workspace, freespace, reds_allowed, (recursive ? "TRUE" : "FALSE"));
   }
      
   pc = start;
   ws = workspace;
   fs = freespace;
   env = freespace;
	reset_ptr = reset_list;
   
   argcount = 0;
   inhibit = NULL;
   mode = PROBLEM;
   prim_args = -1;
   red_limit = reds_allowed;
   reductions = 0;
   if (! recursive) {   
      aux = &constack[CONTROL_SIZE];
	   binding_offset = 0;
		ex_ptr = &heap_space[HEAP_SIZE];
		heap = heap_space;
      stack = constack; 
      init_stats();
   }

#ifdef DECODE_TABLE
   build_decode_table();
#endif

   ws->class = CONTROL;   ws->type = STOP;
   ftime(&start_time);
   answer = red();
   ftime(&stop_time);
   sum_times(&start_time, &stop_time);
   total_reds += reductions;
   fs = freespace;
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
   (++stack)->ptr = fs;
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
   if (debug) foutstring(stdscr, "\n\rlookup(%p, %d) ", env, index);
   while (1) {
#ifdef DEBUG_LOOKUP
		if (debug) {
			foutstring(stdscr, "\n\r   index = %d, env = %p", index, env);
			wrefresh(stdscr);
		}
#endif
      if (env->type == MARKER) 
         env = env->op.addr;
      else if (index == 0) {
      	while (env->type == IP) {
#ifdef DEBUG_LOOKUP
				if (debug) {
					foutstring(stdscr, "\n\r   chasing ip, from %p to %p", env, env->op.addr);
			 		wrefresh(stdscr);
			 	}
#endif
			env = env->op.addr;
			}
         if (debug) {
            foutstring(stdscr, "  returning %p -> ", env);
            print_node(stdscr, env);
         }
         return(env);
      }
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
   (--fs)->class = HEAD; fs->type = CL_ENV; fs->op.addr = context;
   (--fs)->class = HEAD; fs->type = CL_PTR; fs->op.addr = code;
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
   if (pc == inhibit) { /* turn inhibition off */
      reductions = frozen_redcnt;
      inhibit = NULL;
   }
   if (prim_args == 0) 
      (*((primitive->op.sym)->def.prim)) ();
}   


/* PUSH_MARKER
/* If the current environment pointer is not the same as the free space
/* pointer, then push an environment jump marker onto the free space
/* and point ENV to the marker.  Also check to see if out of space.
*/

void push_marker()
{
   if (ws + WARNING_SIZE > fs) {
      outstring(stdscr, "\n\rRUNNING OUT OF MEMORY!!");
      wrefresh(stdscr);
   }
   
   if (env != fs) { 
      (--fs)->type = MARKER; 
		fs->class = CONTROL;
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
               (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = pc;
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               jump_subgraph();
            }
            else {                  /* shared value */
               if (debug) {
                  outstring(stdscr, "\n\rclosure -- SHARED VALUE!");
                  wrefresh(stdscr);
               }
               *pc = *closure;
               pc->class = APPLY;
               move_backward();
            }
            break;
                     
      case HEADM:
            if (closure->type == CL_PTR) {
               pc = closure->op.addr;      /* Restore code */
               env = (++closure)->op.addr; /* Restore context */
               mode = PROBLEM;
            }
            else {               /* shared value */
               if (debug) {
                  outstring(stdscr, "\n\rclosure -- SHARED VALUE!");
                  wrefresh(stdscr);
               }
               pc = closure;
            }
            break;
   }
}


/* EP
/* Environment Pointer, points to a value cell in the environment.
/* Retrieve the value, and execute it.
*/

void inst_ep()
{
	node *value = lookup(pc->op.addr, 0);
	pc->type = value->type;
	pc->op = value->op;
}


/* EX_VAR
/* a free-floating existential variable out of context
*/

void inst_exvar()
{
	switch (mode) {
		case HEADM: 	inst_inert(); break;
		case PROBLEM: 	inst_inert(); break;
		case RESULT:
			{
				if (reductions == red_limit) inst_inert();
				else {
					node *value = lookup(pc->op.addr, 0);
					pc->type = value->type;
					pc->op = value->op;
					inst_inert();
				}
				break;
			}
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
      case HEADM:    *(++ws) = *pc; pc = ws-1; mode = RESULT; break;
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

   if (destination->type == LETREC) {
      if ((destination-1)->type != LETREC) {
         node *temp = destination;
         while (temp->type == LETREC) { binding_offset--; temp++; }
      }
   }
   
   if (result->class == HEAD) { 
      /* atomic result  */
      if ((destination->type == CLOSURE) && (result->type != PTR))  {
         /* share result via closure */
         *(destination->op.addr) = *result;
      }
      destination->type = result->type;       /* write result into spine */
      destination->op = result->op;
      if (result->type != PTR)  ws -= 2;
   }
   else {
      destination->op.addr = result;
      if (destination->type != LETREC) destination->type = PTR;
   }
   
   pc = destination;
   fs = (stack--)->ptr;
   env = fs;  /* possible problems? */
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
         if ((argcount == 0) && (pc->class & PAIR) && (reductions != red_limit)) {
            frozen_redcnt = reductions;
            reductions = red_limit;
            inhibit = ws;
         }
         if ((argcount == 0) || (reductions == red_limit)) {
            /* push an unbound variable onto env */
            ++binding_offset;
            push_marker();
            env->class = HEAD + UNBOUND ; env->type = UBV; 
            env->op.index = binding_offset;
            *(++ws) = *pc;
            (++stack)->ptr = env;
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
                     env->class = HEAD; env->type = CLOSURE; 
                     env->op.addr = closure;
                     break;
                  }

               case EP:		push_marker();
               				env->class = HEAD; env->type = IP;
               				env->op.addr = ws->op.addr;
               				break;

               default:    push_marker();
                           *env = *ws;
                           env->class = HEAD;
                           break;
            }
            --ws;
         }
         ++pc;
         break;

      case RESULT:
			{
				node *temp = lookup((stack--)->ptr, 0);
            if ((temp->type != UBV) || (temp->op.index != binding_offset)) {
					if ((temp->type == EX_VAR) && (!(temp->class & EXISTS))) {
						(temp+3)->op.sym = pc->op.sym;
						pc->class = CONTROL; pc->type = EX_LAMBDA;
					}
					else if ((temp->class & EXISTS) && ((temp+2)->type == EX_LIST)) {
						pc->class = CONTROL; pc->type = EX_LIST;
						pc->op.addr = (temp+2)->op.addr;
					}
					else {
						pc->class = CONTROL; pc->type = EX_LAMBDA;
					}
					if (((pc+1)->class & HEAD) && atomic(pc+1) &&
						 ((pc+1)->type != VAR))
						*pc = *(pc+1);
            }
				--binding_offset;
            move_backward();
            break;
         }
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
               if (((pc->op.addr+1)->class != HEAD) ||
                   ((pc->op.addr+1)->type == VAR)) {
                  node *closure;
                  (--fs)->type = NOOP; fs->op.addr = NULL;                 
                  (--fs)->type = NOOP; fs->op.addr = NULL;
                  (--fs)->type = NOOP; fs->op.addr = pc->op.addr;
                  closure = fs;
                  push_marker();
                  env->class = HEAD; env->type = REC;
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
               env->class = HEAD | UNBOUND; env->type = UBV;
               env->op.index = binding_offset;
            }
            inst_inert();
            break;
         }
   

      case RESULT:
         {
              /* Recreate previous env context, begin reducing arg */
              env = (stack--)->ptr;  /* Restore env context */
              (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = pc;
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
   if (pc->class == HEAD) (*((pc->op.sym)->def.prim)) ();
   else inst_inert();
}
/*
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      case RESULT:   inst_inert(); break;
      case HEADM:    (*((pc->op.sym)->def.prim)) (); break;
   }
}
*/

/* PRIM_1
/* Unary strict primitives.  If one or more arguments are available,
/* set up the firing registers appropriately.
*/

void inst_prim_1()
{
   switch (mode) {
      case PROBLEM:  inst_inert(); break;
      case RESULT:   inst_inert(); break;

      case HEADM:    inst_inert();
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

      case HEADM: inst_inert();
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
                     env = (stack--)->ptr;   /* Restore env context */
                     (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = pc;
                     pc = pc->op.addr; 
                     jump_subgraph();
                     break;

      case HEADM:    pc = pc->op.addr; 
                     mode = PROBLEM;
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
      case HEADM:
         {
            if (reductions != red_limit) {
               pc = closure->op.addr+1;         /* code pointer */
               env = (++closure)->op.addr;      /* env pointer */
               mode = PROBLEM;
               ++reductions;
            }
            else inst_rec_1();
            break;
         } 

      case RESULT:
         {
            (++ws)->class = CONTROL; ws->type = JOIN; ws->op.addr = pc;
            if (reductions != red_limit) {
               ++reductions;
               pc = closure->op.addr+1;      /* Restore code */
               env = (++closure)->op.addr;   /* Restore context */
               jump_subgraph();
            }
            else {
               jump_subgraph();
               inst_rec_1();
            }
            break;
         }

      case PROBLEM:  inst_inert(); break;
   }
}

inst_rec_1()
{
   node *closure = pc->op.addr;
   node *ptr = (closure + 2)->op.addr;
   int count = 0;
   int index = 0;

   if (debug) {
      foutstring(stdscr, "\n\rinst_rec_1: ptr = (%p) ", ptr);
      print_node(stdscr, ptr);
   }

   
   env = (closure+1)->op.addr;      /* restore context */

   while (ptr->type == LETREC) {
      if (debug) {
         foutstring(stdscr, "\n\rinst_rec_1:  copying letrec %s", ptr->op.addr->op.sym->print_name);
         wrefresh(stdscr);
      }
      index++; count++;
      if (ptr->op.addr == closure->op.addr) index = 0;
      *(++ws) = *(ptr++);     /* copy the letrecs */
   }
   env = lookup(env, count);
   { int i;
     for (i=0; i < count; i++) {
         ++binding_offset;
         push_marker();          /* push unbound var into env */
         env->class = HEAD | UNBOUND; env->type = UBV;
         env->op.index = binding_offset;
     }
     for (i=0; i < count; i++) (++stack)->ptr = env;
   }
   if (debug) {
      foutstring(stdscr, "\n\rinst_rec_1: copying rup (%p) to (%p) ", ptr, ws+1);
      print_node(stdscr, ptr);
   }
   *(++ws) = *ptr;            /* copy RUP instruction */
   (++ws)->class = HEAD;         /* insert head var  */
   ws->type = VAR; ws->op.index = index;
   mode = RESULT;             /* reverse directions */
   pc = ws-1;
}


/* RESET
/* Undoes bindings made by unification.
*/

void inst_reset()
{
	undo_bindings(pc->op.rptr);
	if (reductions == red_limit) {
		pc->type = NOOP;
	}
	else {
		pc->class = APPLY; pc->type = SYM; pc->op.sym = neutral;
	}
	inst_inert();
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
               argcount -= n;
               while (n > 0) {
                  if (ptr->type == MARKER) 
                     ptr = ptr->op.addr;
                  else {
                     if (ptr->type == REC)  {
                        (ptr->op.addr + 1)->op.addr = env;
                        (ptr->op.addr + 2)->op.addr = recstart;
                        if (debug) {
                           foutstring(stdscr, "\n\r   modifying loc %p to be %p   ", (ptr->op.addr+1), env);
                           print_node(stdscr, ptr);
                        }
                        n--;
                        ptr++;
                     }
                     else {
                        if (debug) {
                           foutstring(stdscr, "\n\r   not modifying loc %p", ptr);
                           wrefresh(stdscr);
                        }
                        ptr++;
                        n--;
                     }
                  }
               }
               pc++;
               /* if the body is just a (letrec) var, don't incr reductions */
               if (pc->type != VAR || pc->class != HEAD)
                  ++reductions;

            }
            else {
               /* push env onto stack for each letrec */
               while (n-- > 0) (++stack)->ptr = env;
               inst_inert();
            }
            break;
         }


      case RESULT:   inst_inert();
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

      case HEADM:    if ((reductions == red_limit) ||
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
		case RESULT:	pc->type = VAR; 
               		pc->op.index = binding_offset - pc->op.index;
            			inst_inert();
            			break;
                     
      case HEADM:    (++ws)->class = HEAD; ws->type = VAR; 
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
      case PROBLEM:
         {
            node *val = lookup(env, pc->op.index);
            ++argcount;
            (++ws)->class = pc->class;
				if (val->type == UBV) {
					ws->type = EP; ws->op.addr = val;
				}
				else {
					ws->type = val->type; ws->op = val->op;
				}
            ++pc;
            break;
         }
            
      case RESULT:   move_backward(); break;
      
      case HEADM:
         {
            pc = lookup(env, pc->op.index);
            mode = PROBLEM;
            break;
         }
   }
}




        
/* RED
*/

node *red()
{
   void get_stats();

   
   while (TRUE) {
      if (ws >= fs) {
         outstring_ns(stdscr, "\n\rOUT OF GRAPH MEMORY!");
         wrefresh(stdscr);
         longjmp(abort_context, 1);
      }
      if (stack >= aux) {
         outstring_ns(stdscr, "\n\rOUT OF STACK MEMORY!");
         wrefresh(stdscr);
         longjmp(abort_context, 1);
      }
      if (heap >= &heap_space[HEAP_SIZE]) {
      	outstring_ns(stdscr, "\n\rOUT OF HEAP SPACE!");
      	wrefresh(stdscr);
      	longjmp(abort_context, 1);
      }
      if (reset_ptr >= &reset_list[RESET_SIZE]) {
      	outstring_ns(stdscr, "\n\rOUT OF RESET LIST!");
      	wrefresh(stdscr);
      	longjmp(abort_context, 1);
      }
      
      if ((mode == PROBLEM) && (pc->class & HEAD)) mode = HEADM;
      if (debug) {
         outstring(stdscr, "\n\r\nmode = ");
         switch (mode) {
            case PROBLEM: outstring(stdscr, "PROBLEM"); break;
            case RESULT:  outstring(stdscr, "RESULT "); break;
            case HEADM:   outstring(stdscr, "HEAD   "); break;
         }
         foutstring(stdscr, "   pc  = %p   ", pc);   
         print_node(stdscr, pc);
      }

#ifdef DECODE_TABLE
      if (pc->type == STOP) return(pc+1);
      else   (*(decode[pc->type])) (); 
#else
      switch (pc->type) {
         case CLOSURE:  inst_closure(); break;
         case INT:      inst_inert(); break;
			case EP:			inst_ep(); break;
			case EX_VAR:	inst_exvar(); break;
         case FLOAT:    inst_inert(); break;
         case JOIN:     inst_join(); break;
         case LAMBDA:   inst_lambda(); break;
         case LET:      inst_lambda(); break;
         case LETREC:   inst_letrec(); break;
         case LETSTAR:  inst_lambda(); break;
         case PRIM_0:   inst_prim_0(); break;
         case PRIM_1:   inst_prim_1(); break;
         case PRIM_2:   inst_prim_2(); break;
         case PTR:      inst_ptr(); break;
         case REC:      inst_rec(); break;
			case RESET:		inst_reset(); break;
         case RUP:      inst_rup(); break;
         case STOP:     return(pc+1);
         case STRUCT:   inst_inert(); break;
         case SYM:      inst_symbol(); break;
         case UBV:      inst_ubv(); break;
         case VAR:      inst_var(); break;
         
         default: foutstring_ns(stdscr, "\n\rred: pc = %p unexpected type: ", pc);
                  print_node(stdscr, pc);
                  bomb();
                  break;
      }
#endif


      if (stats) get_stats();
      if (debug) {
         foutstring(stdscr, "\n\r                 env = %p   ", env);
         print_node(stdscr, env);
         if (mode == RESULT) {
            foutstring(stdscr, "\n\r        (after)  pc  = %p   ", (pc+1));
            print_node(stdscr, (pc+1));
         }
         foutstring(stdscr, "\n\r                 ws  = %p   ", ws);
         print_node(stdscr, ws);
         foutstring(stdscr, "\n\r           stack-top (%p) = %p or %d,  bn = %d", 
               stack, stack->ptr, stack->intval, binding_offset);
         foutstring(stdscr, "\n\r                 aux (%p) = %p or %d",
               aux, aux->ptr, aux->intval);
         foutstring(stdscr, "\n\r      fs=%p, argc=%d, primargs=%d, prim=%p, inhib=%p",
                     fs, argcount, prim_args, primitive, inhibit);
			foutstring(stdscr, "\n\r      reductions=%lu, red_limit=%lu, reset_ptr=%p, heap=%p",
							reductions, red_limit, reset_ptr, heap);
         wrefresh(stdscr);
      }
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
   if (reset_ptr > max_reset) max_reset = reset_ptr;
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
   max_reset = reset_list;
}


/* BUILD_DECODE_TABLE
/* Initialize the contents of the instruction decode table.
*/

void build_decode_table()
{
   decode[CLOSURE] = inst_closure;
   decode[INT] = inst_inert;
	decode[EP] = inst_ep;
   decode[FLOAT] = inst_inert;
   decode[JOIN] = inst_join; 
   decode[LAMBDA] = inst_lambda; 
   decode[LET] = inst_lambda; 
   decode[LETREC] = inst_letrec; 
   decode[LETSTAR] = inst_lambda; 
   decode[PRIM_0] = inst_prim_0; 
   decode[PRIM_1] = inst_prim_1; 
   decode[PRIM_2] = inst_prim_2; 
   decode[PTR] = inst_ptr; 
   decode[REC] = inst_rec; 
	decode[RESET] = inst_reset;
   decode[RUP] = inst_rup; 
   decode[STRUCT] = inst_inert; 
   decode[SYM] = inst_symbol;
   decode[UBV] = inst_ubv; 
   decode[VAR] = inst_var; 
}
