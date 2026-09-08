/* Debuging Utilities for the Lambda Reduction System  */
/* Mike Hilton, 7 Nov 1989  */

#include <setjmp.h>
#include <stdio.h>
#ifdef IBM
#include <conio.h>
#endif
#include <varargs.h>
#include <curses.h>
#include "lrs.h"

extern int logging, supress_out;
extern FILE *logfile;
extern node *ws, *result, *fs, *problem;
extern jmp_buf abort_context;    /* Error restart handler */

/* Prototypes */
#ifdef IBM
void print_mem(WINDOW *stream, node *start, node *end);
#endif

#ifdef SUN
void print_mem();
#endif



/* BOMB
/* Perform a core dump and exit.
*/

void bomb()
{
   outstring(stdscr, "\n\rBOMB!\n\r\nProblem Graph Dump:");
   wrefresh(stdscr);
   print_mem(stdscr, problem, result-1);
   outstring(stdscr, "\n\r\nResult Graph Dump:");
   wrefresh(stdscr);
   print_mem(stdscr, result, ws);
   foutstring(stdscr, "\n\r\nEnvironment Dump:");
   wrefresh(stdscr);
   print_mem(stdscr, fs, &mem[MEM_SIZE]);
   longjmp(abort_context, 1);
}


/* PRINT_MEM
Prints out the contents of a section of graph memory.
*/

void print_mem(stream, start, end)
WINDOW *stream;
node *start, *end;
{
#ifdef IBM
   foutstring(stream, "\n\rMemory dump %p - %p", start, end);
#endif
#ifdef SUN
   foutstring(stream, "\n\rMemory dump %lu - %lu", start, end);
#endif
   wrefresh(stream);
   while (start <= end) {
#ifdef IBM
      foutstring(stream, "\n\r%p: ", start);
#endif
#ifdef SUN
      foutstring(stream, "\n\r%lu: ", start);
#endif
      print_node(stream, start++);
   }
}
 
/* PRINT_NODE
Prints out the contents of a graph node.
*/   

void print_node(stream, i)
WINDOW *stream;
node *i;
{
	if (i->class & EXISTS) outstring(stream, "E"); else outstring(stream, " ");
   if (i->class & PAIR) outstring(stream, "P"); else outstring(stream, " ");
	if (i->class & UNBOUND) outstring(stream, "U"); else outstring(stream, " ");

	if (i->class & HEAD) outstring(stream, "H ");
	else if (i->class & APPLY) outstring(stream, "@ ");
   else outstring(stream, "  ");

   switch (i->type) {
		case EX_LAMBDA:foutstring(stream, "EX_LAM %s", i->op.sym->print_name); break;
		case EX_SCOPE:	foutstring(stream, "EX_SCOPE %d", i->op.index); break;
      case IP:       foutstring(stream, "IP     %p", i->op.addr); break;
      case LAMBDA:   if (i->op.sym != NULL)
								foutstring(stream, "LAMBDA %s", i->op.sym->print_name);
							else foutstring(stream, "LAMBDA (null)");
							break;
      case LET:      foutstring(stream, "LET    %s", i->op.sym->print_name); break;
      case LETSTAR:  foutstring(stream, "LET*   %s", i->op.sym->print_name); break;
      case LETREC:   foutstring(stream, "LETREC %p", i->op.addr); break;
      case REC:      foutstring(stream, "REC    %p (%s)", i->op.addr, i->op.addr->op.addr->op.sym->print_name); break;
      case RUP:      foutstring(stream, "RUP    %d", i->op.intval); break;
      case PROT:     foutstring(stream, "PROT   %s,%d",
                              ((protected *)i->op.sym)->sym->print_name,
                              ((protected *)i->op.sym)->marks); break;
      case SYM:      foutstring(stream, "SYMBOL %s", i->op.sym->print_name); break;
      case INT:      foutstring(stream, "INT    %d", i->op.intval); break;
      case FLOAT:    foutstring(stream, "FLOAT  %f", i->op.floval); break;
      case PTR:      foutstring(stream, "PTR    %p", i->op.addr); break;
      case VAR:      foutstring(stream, "VAR    %d", i->op.index); break;
      case PRIM_0:   foutstring(stream, "PRIM_0 %s", i->op.sym->print_name); break;
      case PRIM_1:   foutstring(stream, "PRIM_1 %s", i->op.sym->print_name); break;
      case PRIM_2:   foutstring(stream, "PRIM_2 %s", i->op.sym->print_name); break;
      case JOIN:     foutstring(stream, "JOIN   %p", i->op.addr); break;
      case UBV:      foutstring(stream, "UBV    %d", i->op.index); break;
      case MARKER:   foutstring(stream, "MARKER %p", i->op.addr); break;
      case CLOSURE:  foutstring(stream, "CLOSURE (%p) {", i->op.addr);
                     print_node(stream, i->op.addr);
                     outstring(stream, ", ");
                     print_node(stream, (i->op.addr) + 1);
                     outstring(stream, "}");
                     break;                    
      case CL_PTR:   foutstring(stream, "CL_PTR %p", i->op.addr); break;
      case CL_ENV:   foutstring(stream, "CL_ENV %p", i->op.addr); break;
      case STRUCT:   foutstring(stream, "STRUCT %p", i->op.addr); break;
      case STOP:     foutstring(stream, "STOP"); break;
      case DEF:      foutstring(stream, "DEF %s", i->op.sym->print_name); break;
      case EOD:      foutstring(stream, "EOD %p", i->op.addr); break;
      case NOOP:     foutstring(stream, "NOOP"); break;
		case RESET:		foutstring(stream, "RESET  %p", i->op.addr); break;
		case EP:			foutstring(stream, "EP     %p", i->op.addr); break;


      case OPEN_PAREN:     outstring(stream, "OPEN-PAREN"); break;
      case CLOSE_PAREN:    outstring(stream, "CLOSE-PAREN"); break;
      case OPEN_BRACKET:   outstring(stream, "OPEN-BRACKET"); break;
      case CLOSE_BRACKET:  outstring(stream, "CLOSE-BRACKET"); break;
      case OPEN_BRACE:     outstring(stream, "OPEN-BRACE"); break;
      case CLOSE_BRACE:    outstring(stream, "CLOSE-BRACE"); break;

            
      default: foutstring(stream, "unknown, type %d", i->type); break;
   }
   wrefresh(stream);
}


/* OUTSTRING
/* If output logging is active, send output to the log file
/* along with putting it out to WIN.
*/

outstring(win, str)
WINDOW *win;
char *str;
{
   if (logging) fputs(str, logfile);
   if (!supress_out) waddstr(win, str);

#ifdef IBM
   if (kbhit()) {
      char ch = wgetch(win);
      if (ch == 3) {
         longjmp(abort_context, 1);
      }
      else ungetch(ch);
   }
#endif
      
   
}

/* OUTSTRING_NS
/* Like outstring, only does not supress output.
*/
outstring_ns(win, str)
WINDOW *win;
char *str;
{
   if (logging) fputs(str, logfile);
   waddstr(win, str);

#ifdef IBM
   if (kbhit()) {
      char ch = wgetch(win);
      if (ch == 3) {
         longjmp(abort_context, 1);
      }
      else ungetch(ch);
   }
#endif

}

/* FOUTSTRING
/* Like outstring, but a Formatted output string is expected.
*/

foutstring(va_alist)
va_dcl
{
   va_list args;
   WINDOW *win;
   char *format;
   double a1, a2, a3, a4, a5;
   
   if (logging) {
      va_start(args);
      win = va_arg(args, WINDOW *);
      format = va_arg(args, char *);
      vfprintf(logfile, format, args);
   }
   if (!supress_out) {
      va_start(args);
      win = va_arg(args, WINDOW *);
      format = va_arg(args, char *);
      /* these sneaky things are all dependent on how wprintw was */
      /* implemented */
      a1 = va_arg(args, double);
      a2 = va_arg(args, double);
      a3 = va_arg(args, double);
      a4 = va_arg(args, double);
      a5 = va_arg(args, double);          
      wprintw(win, format, a1, a2, a3, a4, a5);
   }

#ifdef IBM
   if (kbhit()) {
      char ch = wgetch(win);
      if (ch == 3) {
         longjmp(abort_context, 1);
      }
      else ungetch(ch);
   }
#endif
   
}

/* FOUTSTRING_NS
/* Like foutstring, but output is not supressed.
*/

foutstring_ns(va_alist)
va_dcl
{
   va_list args;
   WINDOW *win;
   char *format;
   double a1, a2, a3, a4, a5;
   
   if (logging) {
      va_start(args);
      win = va_arg(args, WINDOW *);
      format = va_arg(args, char *);
      vfprintf(logfile, format, args);
   }

   va_start(args);
   win = va_arg(args, WINDOW *);
   format = va_arg(args, char *);
   /* these sneaky things are all dependent on how wprintw was */
   /* implemented */
   a1 = va_arg(args, double);
   a2 = va_arg(args, double);
   a3 = va_arg(args, double);
   a4 = va_arg(args, double);
   a5 = va_arg(args, double);          
   wprintw(win, format, a1, a2, a3, a4, a5);

#ifdef IBM
   if (kbhit()) {
      char ch = wgetch(win);
      if (ch == 3) {
         longjmp(abort_context, 1);
      }
      else ungetch(ch);
   }
#endif
   
}

