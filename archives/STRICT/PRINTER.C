/* Basic Output Routines For The Lambda Reduction System
/* Mike Hilton, 12 Sep 1989
/*
/* This file contains routines for printing lambda expressions:
/*
/* void print_expression(FILE *stream, int ADDR);
/*
/* The printer is recursive in nature, so it is possible to exceed
/* the depth of C's runtime stack when printing structures and lists.
/* To prevent aborting the reduction system, an exception is raised
/* when MAX_PRINT_DEPTH recursive calls have been made.  The exception
/* handler aborts the reduction sequence.
*/

#include <stdio.h>
#include <conio.h>
#include <io.h>
#include <signal.h>
#include "lrs.h"

#define MAX_PRINT_DEPTH		35			/* value is determined experimentally */


extern node *fs;
extern node *ws;
extern int binding_offset;
extern int force;
extern int red_limit;
extern int reductions;
extern int total_reds;
extern symbol *nil;

/*
/* Printer Routines
*/



/* PRINT_EXPRESSION
/* Prints a graph beginning at address ADDR in expression format on output
/* stream STREAM.  If an unreduced object is to be printed, it is instantiated
/* first and then printed.  (Instantiation is performed by calling the 
/* reducer recursively with a reduction limit of 0.)
*/

void print_expression(stream, addr)
FILE *stream;
node *addr;
{
   print_express(stream, addr, fs, 0);
}


print_express(stream, i, bindings, depth)
FILE *stream;
node *i, *bindings;
int depth;
{
   node *finished;
   int first;
   int parens = TRUE;

   /* Check to see if recursion depth is too great */
   if (depth > MAX_PRINT_DEPTH) {
   	fprintf(stderr, "\n\nMAXIMUM PRINT DEPTH EXCEEDED!");
   	raise(SIGABRT);
   }

   if (i->head == TRUE) print_exp(stream, i, bindings, FALSE, depth+1);
   else {
      if ((i->type == LET)) parens = FALSE;
		if (parens) putc('(', stream);
      if (i->type == LAMBDA) {
         first = 1;
         fputs("LAMBDA (", stream);
         while (i->type == LAMBDA) {
            *(--bindings) = *i;
            if (! first) putc(' ', stream);
            fputs(i->op.sym->print_name, stream);
            first = 0;
            i++;
         }
         fputs(") ", stream);
      }

      else if (i->type == LET) {
			node *arg = i-1;
      	(--bindings)->type = MARKER; bindings->op.addr = bindings+1;
      	fputs("LET (", stream);
      	first = 1;
      	while (i->type == LET) {
      		if (!first) putc(' ', stream);
      		first = 0;
      		fprintf(stream, "(%s ", i->op.sym->print_name);
      		if (arg->type == PTR)
      			print_express(stream, arg->op.addr, bindings, depth+1);
      		else
      			print_exp(stream, arg, bindings, FALSE, depth+1);
      		putc(')', stream);
				*(bindings-1) = *bindings;
      		*(bindings--) = *i;
      		i++;
      		arg--;
      	}
      	fputs(") ", stream);
      	++bindings;
      }

      else if (i->type == LETREC) {
			node *arg = i;
      	while (arg->type == LETREC) {
				*(--bindings) = *(arg->op.addr);
				arg++;
			}
      	fputs("LETREC (", stream);
      	first = 1;
      	while (i->type == LETREC) {
      		if (!first) putc(' ', stream);
      		first = 0;
      		fprintf(stream, "(%s ", i->op.addr->op.sym->print_name);
      		if ((i->op.addr+1)->head == FALSE)
      			print_express(stream, i->op.addr+1, bindings, depth+1);
      		else
      			print_exp(stream, i->op.addr+1, bindings, FALSE, depth+1);
      		putc(')', stream);
      		i++;
      	}
      	fputs(") ", stream);
      }
      		
      else if ((i+1)->type == LETSTAR) {
      	fputs("LET* (", stream);
      	first = 1;
      	while ((i+1)->type == LETSTAR) {
				if (!first) putc(' ', stream);
   	      fprintf(stream, "(%s ", (i+1)->op.sym->print_name);
      	   if (i->type == PTR)
					print_express(stream, i->op.addr, bindings, depth);
				else
					print_exp(stream, i, bindings, FALSE, depth+1);
				fputs(")", stream);
            *(--bindings) = *(i+1);
				first = 0;
				i += 2;
			}
			fputs(") ", stream);
		}

      finished = i;
      first = 1;
      while (i->head != TRUE) {    /* find head of expression */
         if ((i->type == LAMBDA) || ((i+1)->type == LETSTAR) ||
         	 (i->type == LETREC)) {
            print_express(stream, i, bindings, depth+1);
            --i;
            first = 0;
            break;
         }
         else if (i->type == LET) {
				node *x;
         	print_express(stream, i, bindings, depth+1);
         	for (x = i; x->type == LET; x++, i--);
         	i--;
         	first = 0;
         	break;
         }
         else ++i;
      }
      while (i >= finished) {
         if (!first && (i->type != RUP)) putc(' ', stream);
         print_exp(stream, i, bindings, FALSE, depth+1);
         i--;
         first = 0;
      }
      if (parens) putc(')', stream);
   }
}


/* PRINT_EXP
/* Prints out a single graph element at address I.
*/

print_exp(stream, i, bindings, struct_elem, depth)
FILE *stream;
node *i, *bindings;
int struct_elem, depth;
{
   switch (i->type) {
      case SYM:
      case PRIM_0:
      case PRIM_1:
      case PRIM_2: fputs(i->op.sym->print_name, stream); break;
      case INT   : fprintf(stream, "%d", i->op.intval); break;
      case FLOAT : fprintf(stream, "%f", i->op.floval); break;
      case PTR   :
			{
				node *value, *reduce();
				int reds;
				
				if (struct_elem && force && reductions != red_limit) {
					reds = ((red_limit == -1) ? -1 : red_limit - reductions);
				   value = reduce(i->op.addr, ++ws, bindings, reds, TRUE);
               if (value->head == TRUE) 
                  *i = *value;
               else 
                  i->op.addr = value;
               (--fs)->type = MARKER; fs->op.addr = bindings;
               print_express(stream, value, fs, depth+1);
            }
            else
					print_express(stream, i->op.addr, bindings, depth+1);
				break;
			}

		case REC:
			{
				node *value;
				int reds;
				
				if (struct_elem) {
					if (force) reds = ((red_limit == -1) ? -1 : red_limit - reductions);
					else reds = 0;
					i->head = TRUE;
				   value = reduce(i, ++ws, bindings, reds, TRUE);
               if (value->head == TRUE) 
                  *i = *value;
               else 
                  i->op.addr = value;
               (--fs)->type = MARKER; fs->op.addr = bindings;
               print_express(stream, value, fs, depth+1);
            }
            else
					fprintf(stream, "<REC %s>", i->op.addr->op.addr->op.sym->print_name);
				break;
			}

		case RUP: 	break;	
					
      case SUSPEND:
         {
            node *value;
            
            if (i->op.addr->type != CL_PTR) {
            	/* ??? problems because bindings may not be right */
               print_exp(stream, i->op.addr, bindings, FALSE, depth+1); 
            }
            else {
               int reds;
               if (force) reds = ((red_limit == -1) ? -1 : red_limit - reductions);
               else reds = 0;
               
               value = reduce(i, ++ws, bindings, reds, TRUE);
               if (value->head == TRUE) {
                  *(i->op.addr) = *value;
                  *i = *value;
               }
               else {
                  node *cl = i->op.addr;
                  cl->type = PTR; cl->op.addr = value;
                  i->type = PTR; i->op.addr = value;
               }
               (--fs)->type = MARKER; fs->op.addr = bindings;
               print_express(stream, value, fs, depth+1);
            }
            break;
         }
         
      case STRUCT: 
         {
            int x;
            i = i->op.addr;
            fprintf(stream, "{%s", (i--)->op.sym->print_name);
            for (x = i->op.intval; x > 0; x--) {
               putc(' ', stream);
               print_exp(stream, --i, bindings, TRUE, depth+1);
            }
            putc('}', stream);
            break;
         }

		case CONS:
			{
				putc('[', stream);
				while (i->type == CONS) {
					i = i->op.addr;
					print_exp(stream, i+1, bindings, TRUE, depth+1);
					if ((i->type == SUSPEND) && force) {
						int reds = ((red_limit == -1) ? -1 : red_limit - reductions);
               	node *value = reduce(i, ++ws, bindings, reds, TRUE);
               	if (value->head == TRUE) {
               		*(i->op.addr) = *value;
							*i = *value;
						}
	               else {
   	               node *cl = i->op.addr;
      	            cl->type = PTR;
							cl->op.addr = value;
         	         i->type = PTR;
							i->op.addr = value;
            	   }
               	(--fs)->type = MARKER; fs->op.addr = bindings;
               	bindings = fs;
					}
					if (i->type == CONS) putc(' ', stream);
				}
				if ((i->type != SYM) || (i->op.sym != nil)) {
					fputs(" | ", stream);
					print_exp(stream, i, bindings, TRUE, depth+1);
				}
				putc(']', stream);
				break;
			}                        
                     
      case VAR   : 
         {
            node *limit, *lookup();
            symbol *pname;

            limit = lookup(bindings, i->op.index);
            pname = limit->op.sym;
            while(bindings < limit) {
               if (bindings->type == MARKER) 
                  bindings = bindings->op.addr;
               else {
						if (bindings->op.sym == pname) putc('#', stream);
	               bindings++;
	            }
            }
            fputs(pname->print_name, stream);
         }
         break;
      
     default:  fprintf(stream, "\nPrinter Error: Unknown type in output: %d\n", 
                        i->type);
   }
}



