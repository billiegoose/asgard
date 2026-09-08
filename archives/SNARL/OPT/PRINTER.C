/* Basic Output Routines For The Head Order Reduction System
/* Mike Hilton, 10 Jan 1990.
/*
/*
/* The printer actually prints to an output buffer string, BUFFER,
/* and then prints this string on STREAM.  This is done in anticipation
/* of having a pretty printing program that could use the string
/* at some time in the future.  If you want to get ahold of the string,
/* you can call the routine
/*
/* char *sprint_expression(int ADDR);
/*
/* which returns a pointer to the output buffer.
/*
/*
/* The printer is recursive in nature, so it is possible to exceed
/* the depth of C's runtime stack when printing structures and lists.
/* To prevent aborting the reduction system, an exception is raised
/* when MAX_PRINT_DEPTH recursive calls have been made.  The exception
/* handler aborts the reduction sequence.
*/

#include <stdio.h>
#ifdef IBM
#include <conio.h>
#include <io.h>
#endif
#include <setjmp.h>
#include <varargs.h>
#include <curses.h>
#include "lrs.h"


#define MAX_PRINT_DEPTH    35       /* value is determined experimentally */



extern node *fs;
extern node *ws;
extern node *env;
extern int binding_offset;
extern int force;
extern unsigned long red_limit;
extern unsigned long reductions;
extern control *stack;
extern unsigned long total_reds;
extern symbol *nil, *pair, *string;
extern jmp_buf abort_context;

#define BUFFER_SIZE     2048     /* Size of the output buffer */
#define SAFETY_MARGIN   128      /* Safety margin for detecting overflow */
char  outbuffer[BUFFER_SIZE];
char  *prin_index;
int   end_of_buffer;

int   print_partial;    /* flags whether to print lazy structures  */
char *partial_buf;      /* as they are computed */
WINDOW *partial_scr;

static jmp_buf printer_abort;

control *orig_stack; /* original stack ptr value when printer called */

/* Prototypes */
#ifdef IBM
char *sprint_expression(node *addr);
void force_reduction(node *addr, control *binds);
void sprint(char *format, ...);
#endif

#ifdef SUN
char *sprint_expression();
void force_reduction();
void sprint();
#endif


/*
/* Printer Routines
*/


char *print_expression(window, addr)
WINDOW *window;
node *addr;
{
   print_partial = 1;
   partial_buf = outbuffer;
   partial_scr = window;
   sprint_expression(addr);
   outstring_ns(window, partial_buf);
   wrefresh(window);
   print_partial = 0;
   return(outbuffer);
}

char *sprint_expression(addr)
node *addr;
{
   int jmpval;

   orig_stack = stack;
   prin_index = outbuffer;
   end_of_buffer = BUFFER_SIZE - SAFETY_MARGIN;
   jmpval = setjmp(printer_abort);
   if (jmpval == 0) print_express(addr, stack, 0);
   return(outbuffer);
}



/* SPRINT
/* String print manager.  SPRINT is called like SPRINTF would be, but
/* SPRINT advances the placekeeping pointer into the buffer.
*/

void sprint(va_alist)
va_dcl
{
   va_list args;
   char *format;
   
   va_start(args);
   format = va_arg(args, char *);
   vsprintf(prin_index, format, args);
   while(*prin_index != '\0') prin_index++;
   va_end(args);
   if (prin_index > &outbuffer[end_of_buffer]) {
      outstring_ns(stdscr, "\n\rMAXIMUM PRINT LENGTH EXCEEDED!");
      wrefresh(stdscr);
      *prin_index = '\0';
      longjmp(printer_abort, 1);
   }     
}  


print_express(i, bindings, depth)
node *i;
control *bindings;
int depth;
{
   node *finished;
   int first;
   int parens = TRUE;

#ifdef DEBUG
   wprintw(stdscr, "\nprint_express: i = %p, depth = %d,  bindings = %p\n", i, depth, bindings);
   wrefresh(stdscr);
#endif
   /* Check to see if recursion depth is too great */
   if (depth > MAX_PRINT_DEPTH) {
      outstring(stdscr, outbuffer);
      outstring_ns(stdscr, "\n\rMAXIMUM PRINT DEPTH EXCEEDED!");
      wrefresh(stdscr);
      longjmp(abort_context, 1);
   }

   if ((i->class & PAIR) && (i->op.sym == pair)) {
      /* List */
      sprint("[");
      while ((i->class & PAIR) && (i->op.sym == pair)) {
         (++bindings)->sym = i->op.sym;
         if (force) force_reduction(i+2, bindings);
         print_exp(i+2, bindings, depth+1);
         i++;
         if ((i->type != PTR) || !(i->op.addr->class & PAIR)) {
            if (force) force_reduction(i, bindings);
         }
         if ((i->type == PTR) && (i->op.addr->class & PAIR)) {
            i = i->op.addr;
            sprint(" ");
         }
      }
      if (i->type != SYM || i->op.sym != nil) {
         sprint(" | ");
         print_exp(i, bindings, depth+1);
      }
      sprint("]");
      return;
   }

   else if ((i->class & PAIR) && (i->op.sym == string)) {
      /* String */
      sprint("\"");
      while ((i->class & PAIR) && (i->op.sym == string)) {
         (++bindings)->sym = i->op.sym;
         if (force) force_reduction(i+2, bindings);
         if ((i+2)->type == CHARAC) sprint_char((i+2)->op.charval);
         else print_exp(i+2, bindings, depth+1);
         i++;
         if ((i->type != PTR) || !(i->op.addr->class & PAIR)) {
            if (force) force_reduction(i, bindings);
         }
         if ((i->type == PTR) && (i->op.addr->class & PAIR)) {
            i = i->op.addr;
         }
      }
      if (i->type != SYM || i->op.sym != nil) {
         sprint(" | ");
         print_exp(i, bindings, depth+1);
      }
      sprint("\"");
      return;
   }

   else if (i->class & PAIR) {
      /* Structure */
      sprint("{%s", i->op.sym->print_name);
      (++bindings)->sym = i->op.sym;
      while ((++i)->class != HEAD);
      while ((--i)->type != LAMBDA) {
         sprint(" ");
         if (force) force_reduction(i, bindings);
         print_exp(i, bindings, depth+1);
      }
      sprint("}");
      return;
   }
         
   else if (i->class == HEAD) print_exp(i, bindings, depth+1);
   else {
      if (i->type == LET) parens = FALSE;
      if (parens) sprint("(");
      if (i->type == LAMBDA) {
         first = 1;
         sprint("LAMBDA (");
         while ((i->type == LAMBDA) && !(i->class & PAIR)) {
            (++bindings)->sym = i->op.sym;
            if (! first) sprint(" ");
            sprint("%s", i->op.sym->print_name);
            first = 0;
            i++;
         }
         sprint(") ");
         print_express(i, bindings, depth+1);
         sprint(")");         
         return;
      }

      else if (i->type == LET) {
         node *arg = i-1;
         node *binds = i;
         sprint("LET (");
         first = 1;
         while (i->type == LET) {
            if (!first) sprint(" ");
            first = 0;
            sprint("(%s ", i->op.sym->print_name);
            if (arg->type == PTR)
               print_express(arg->op.addr, bindings, depth+1);
            else
               print_exp(arg, bindings, depth+1);
            sprint(")");
            i++;
            arg--;
         }
         sprint(") ");
         while (binds < i) (++bindings)->sym = (binds++)->op.sym;
         print_express(i, bindings, depth+1);
         sprint(")");
         return;
      }

      else if (i->type == LETREC) {
         node *arg = i;
         while (arg->type == LETREC) {
            (++bindings)->sym = arg->op.addr->op.sym;
            arg++;
         }
         sprint("LETREC (");
         first = 1;
         while (i->type == LETREC) {
            if (!first) sprint(" ");
            first = 0;
            sprint("(%s ", i->op.addr->op.sym->print_name);
            if ((i->op.addr+1)->class != HEAD)
               print_express(i->op.addr+1, bindings, depth+1);
            else
               print_exp(i->op.addr+1, bindings, depth+1);
            sprint(")");
            i++;
         }
         sprint(") ");
         print_express(i, bindings, depth+1);
         sprint(")");
         return;
      }
            
      else if ((i+1)->type == LETSTAR) {
         sprint("LET* (");
         first = 1;
         while ((i+1)->type == LETSTAR) {
            if (!first) sprint(" ");
            sprint("(%s ", (i+1)->op.sym->print_name);
            if (i->type == PTR)
               print_express(i->op.addr, bindings, depth);
            else
               print_exp(i, bindings, depth+1);
            sprint(")");
            (++bindings)->sym = (i+1)->op.sym;
            first = 0;
            i += 2;
         }
         sprint(") ");
         print_express(i, bindings, depth+1);
         sprint(")");
         return;
      }

      finished = i;
      first = 1;
      while (i->class != HEAD) {    /* find head of expression */
         if (i->class & PAIR) {
            print_express(i, bindings, depth+1);
            --i;
            first = 0;
            break;
         }
         else if ((i->type == LAMBDA) || ((i+1)->type == LETSTAR) ||
             (i->type == LETREC)) {
            print_express(i, bindings, depth+1);
            --i;
            first = 0;
            break;
         }
         else if (i->type == LET) {
            node *x;
            print_express(i, bindings, depth+1);
            for (x = i; x->type == LET; x++, i--);
            i--;
            first = 0;
            break;
         }
         else ++i;
      }
      while (i >= finished) {
         if (!first && (i->type != RUP)) sprint(" ");
         print_exp(i, bindings, depth+1);
         i--;
         first = 0;
      }
      if (parens) sprint(")");
   }
}


/* PRINT_EXP
/* Prints out a single graph element at address I.
*/

print_exp(i, bindings, depth)
node *i;
control *bindings;
int depth;
{
#ifdef DEBUG
   wprintw(stdscr, "\n\rprint_exp: i = %p, depth = %d, bindings = %p\n", i, depth, bindings);
   wrefresh(stdscr);
#endif

   switch (i->type) {
      case INT:      sprint("%ld", i->op.intval); break;
      case CHARAC:
         {
            sprint("\'");
            sprint_char(i->op.charval);
            sprint("\'");
            break;
         }

      case FLOAT:    sprint("%f", i->op.floval); break;
      case PTR:      print_express(i->op.addr, bindings, depth+1);
                     break;
      case REC:      sprint("<REC %s>", i->op.addr->op.addr->op.sym->print_name);
                     break;
      case RUP:      break;   

      case SYM:
      case PRIM_0:
      case PRIM_1:
      case PRIM_2:   
         {
            control *temp = bindings;
            symbol *pname = i->op.sym;

            while(temp > orig_stack) {
               if (temp->sym == pname) sprint("#");
               --temp;
            }
            sprint("%s", pname->print_name);
            break;
         }

                     
      case VAR   : 
         {
            control *limit, *temp;
            symbol *pname;

            limit = bindings - i->op.index;
            pname = limit->sym;
            temp = bindings;
            while(temp > limit) {
               if (temp->sym == pname) sprint("#");
               --temp;
            }
            sprint("%s", pname->print_name);
            break;
      }
   
      
     default:  sprint("\nPrinter Error: Unknown type in output at (%p): %d\n", 
                        i, i->type);
   }
}


sprint_char(c)
char c;
{
   switch (c) {
      case '\n': sprint("\\n"); break;
      case '\t': sprint("\\t"); break;
      case '\b': sprint("\\b"); break;
      case '\r': sprint("\\r"); break;
      case '\f': sprint("\\f"); break;
      case '\'': sprint("\\\'"); break;
      case '\"': sprint("\\\""); break;
      case '\\': sprint("\\\\"); break;
      default: sprint("%c", c); break;
   }
}



/* FORCE REDUCTION
/* In order to force the reduction of a frozen expression, all you
/* need to know is the address of the root of the expression, ADDR,
/* and the number of unbound lambdas in the expression's context, BN.
/* After reducing, surgically implant the result in the root location.
*/

void force_reduction(addr, bindings)
node *addr;
control *bindings;
{
   node *result, *wstemp;
   int i, reds, bn;
   union operand oper;

   if (addr->type != PTR) return;

   if (print_partial) {
      outstring_ns(partial_scr, partial_buf);
      wrefresh(partial_scr);
      partial_buf = prin_index;
   }


   bn = bindings - orig_stack;
   for (i = 1; i <= bn; i++) {
      oper.index = i;
      write_mem(--fs, HEAD, UBV, &oper);
   }
   binding_offset = bn;
   stack = bindings;
   reds = ((red_limit == -1) ? -1 : red_limit - reductions);
   wstemp = ws;
   result = reduce(addr->op.addr, ++ws, fs, reds, TRUE);

   if (result->class == HEAD) {
      *addr = *result;
      addr->class = APPLY;
      ws = wstemp;
   }
   else {
      addr->type = PTR;
      addr->op.addr = result;
   }
      
}
