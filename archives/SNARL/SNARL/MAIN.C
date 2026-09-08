/* Driver for the Head Order Reduction System
/* Mike Hilton, 10 Jan 1990
*/
#undef DEBUG_COPY
#undef DEBUG_PARSER

#include <stdio.h>
#include <ctype.h>
#ifdef SUN
#include <sys/types.h>
#include <sys/timeb.h>
#endif
#ifdef  IBM
#include <stdlib.h>
#include <sys\types.h>
#include <sys\timeb.h>
#include <float.h>
#include <io.h>
#endif
#include <setjmp.h>
#include <signal.h>
#include <malloc.h>
#include <curses.h>
#include "lrs.h"

#define  VERSION  "1.0"             /* System version number */
#define  PROMPT   "\n\rhorse> "     /* System prompt */


symbol   *command;      /* LRS command value, passed from parser globally */
symbol   *comm_switch;  /* command modifier */
int      debug;         /* boolean flag, if debugging trace to be made */
int      expr_type;     /* set by parser to tell if input is a command or exp */
int      focus;         /* boolean flag, if there is a current expression */
int      force;         /* boolean flag, if output should be forced to n.f. */
node     *high;         /* Highest location in free graph memory */
FILE     *input_file;   /* file being loaded as input */
FILE     *logfile;      /* file for output logging */
int      logging;       /* boolean flag, if output is being logged */
node     *low;          /* Lowest location in free graph memory */
node     *problem;      /* root of the problem graph */
unsigned long     reds_allowed;  /* number of reductions allowed by user   */
node     *result;       /* root of the result graph */
int      stats;         /* boolean flag, if statistics should be printed */
int      step;          /* boolean flag, if in step mode */
int      supress_out;   /* boolean flag, if output should be suppressed */

struct timeb start_time, stop_time;    /* used to measure elapsed time */
long total_seconds;
unsigned short total_millisecs;

jmp_buf  abort_context;                /* error handling return context */

extern int line_number;
extern char *file_name;
extern node *mem;
extern control *constack;
extern unsigned long total_reds, reductions;
extern node *ws, *fs, *max_graph, *max_env, *initial_env;
extern control *max_stack, *max_aux, *initial_aux, *stack, *aux;
extern unsigned long instructs;
extern history input_history, output_history;

/* Prototypes */
#ifdef IBM
int   abort_handler(int signal);
node  *copy_graph(node *from, node *to);
node  *copy_struct(node *source, node *to);
int   ctrlc_handler(int signal);
int   fp_handler(int signal, int signum);
void  handle_command(char *command, char *modifier);
int   load_file(char *name, int line_no, char *file_name);
void  print_stats(WINDOW *stream, int flag);
void  rep_loop(FILE *in);
void  set_binary_mode(char *mode, int *var, char *value);
node  *shift_memory(node *begin, node *end, node *dest);
node  *struct_def(node *def, node *space);
#endif

#ifdef SUN
int   abort_handler();
node  *copy_graph();
node  *copy_struct();
int   ctrlc_handler();
int   fp_handler();
void  handle_command();
int   load_file();
void  print_stats();
void  rep_loop();
void  set_binary_mode();
node  *shift_memory();
node  *struct_def();
#endif


#define NEW    1  /* values for FOCUS */
#define OLD    2
#define NONE   3
     
main(argc, argv)
int argc;
char *argv[];
{
   int   terminal;   /* Boolean flag if input stream is a terminal */
   
   /* Create the graph and control memories */
#ifdef IBM
   mem = (node huge *)halloc((long)MEM_SIZE, sizeof(node));
#endif
#ifdef SUN
   mem = (node *) malloc(MEM_SIZE * sizeof(node));
#endif
   if (mem == NULL) {
      fprintf(stderr, "\nUnable to allocate memory for MEM.");
      exit(1);
   }
#ifdef IBM
   constack = (control huge *)halloc((long)CONTROL_SIZE, sizeof(control));
#endif 
#ifdef SUN
   constack = (control *) malloc(CONTROL_SIZE * sizeof(control));
#endif
   if (constack == NULL) {
      fprintf(stderr, "\nUnable to allocate memory for CONSTACK.");
      exit(1);
   }

   terminal = (isatty (fileno(stdin)));   
   high = &mem[MEM_SIZE-1];
   low  = mem;
   fs = high;
   ws = low;
   stack = constack;
   aux = &constack[CONTROL_SIZE-1];
   file_name = "";
   focus = NONE;
   force = FALSE;
   line_number = 1;
   step = FALSE;
   stats = FALSE;
   supress_out = FALSE;

   /* initialize CURSES terminal package */
   if (initscr() == ERR) {       
      fprintf(stderr, "\nUnable to initialize the CURSES package.");
      exit(1);
   }
   scrollok(stdscr, TRUE);
   leaveok(stdscr, FALSE);
   noecho();
   nonl();
#ifdef IBM
   keypad(stdscr, TRUE);
#endif
   
   if (terminal) {
      foutstring(stdscr, "\n\rHead Order Reduction System, Version %s", VERSION);
      foutstring(stdscr, "\n\r%lu graph nodes, %lu control stack", 
                  (unsigned long) MEM_SIZE, (unsigned long) CONTROL_SIZE);
      wrefresh(stdscr);            
   }
   
   install_primitives();
   while (argc > 1) load_file(argv[--argc], line_number, file_name);
   history_initialize(&input_history);
   history_initialize(&output_history);

   /* if an error occurs later, control jumps to this point */
   if (setjmp(abort_context) != 0) {
         outstring_ns(stdscr, "\n\rREDUCTION ABORTED!");
         wrefresh(stdscr);
   }

   /* install a control-c interrupt handler */
   if (signal(SIGINT, ctrlc_handler) == SIG_ERR) {
      outstring_ns(stdscr, "\n\rControl-C signal handler failed to install.");
      wrefresh(stdscr);
   }
   /* install a floating point error handler */
   if (signal(SIGFPE, fp_handler) == SIG_ERR) {
      outstring_ns(stdscr, "\n\rFloating point error handler failed to install.");
      wrefresh(stdscr);
   }
   /* install a SIGABRT handler */
   if (signal(SIGABRT, abort_handler) == SIG_ERR) {
      outstring_ns(stdscr, "\n\rAbnormal termination handler failed to install.");
      wrefresh(stdscr);
   }

   while (1) { 
      if (terminal) { outstring_ns(stdscr, PROMPT); wrefresh(stdscr); }
      rep_loop(stdin);
   }
}


int abort_handler(sig)
int sig;
{
   outstring_ns(stdscr, "\n\rAbnormal termination of reduction...");
   wrefresh(stdscr);
   longjmp(abort_context, 1);
}

int ctrlc_handler(sig)
int sig;
{
   outstring_ns(stdscr, "\n\rUser Interrupt...");
   wrefresh(stdscr);
   longjmp(abort_context, 1);
}

int fp_handler(sig, num)
int sig, num;
{
   outstring_ns(stdscr, "\n\rFloating point error...");
   wrefresh(stdscr);
#ifdef IBM
   _fpreset();
#endif
   longjmp(abort_context, 1);
}






/* REP_LOOP
/* Read-Eval-Print Loop.
*/


void rep_loop(in)
FILE *in;
{
   char *exp, *outexp;
   node *end_token;
   int terminal = isatty(fileno(in));
   char *input_line_editor(), *print_expression();

   total_seconds = 0;      /* this should probably be done in REDUCE */
   total_millisecs = 0;
   
   if (terminal) {
      exp = input_line_editor(stdscr);
      if (logging) fputs(exp, logfile);
   }
   else exp = NULL;

#ifdef DEBUG_PARSER
   if (debug) {
      foutstring(stdscr, "\n\rInput string: \"%s\"", exp);
      wrefresh(stdscr);
   }
#endif
   end_token = parse_expression(exp, low, high);
   if (end_token == NULL) return;
#ifdef DEBUG_PARSER
   if (debug) {
      foutstring(stdscr, "\n\rParse string:");
      wrefresh(stdscr);
      print_mem(stdscr, end_token, high);
   }
#endif

   switch (expr_type) {
      case LAM_EXP:  /* establish a new focus expression */
                     if (terminal) add_string_to_history(exp, &input_history);
                     if (focus != NONE) low = problem;
                     result = compile_graph(high, end_token, low) + 1;
                     problem = low;
                     focus = NEW;
                     low = result;
                     total_reds = 0;
#ifdef DEBUG_PARSER
                     if (debug) {
                        outstring(stdscr, "\n\rProblem Graph:");
                        wrefresh(stdscr);
                        print_mem(stdscr, problem, result-2);
/*                      outstring(stdscr, "\n\rProblem string:\n\r");
                        outstring(stdscr, sprint_expression(problem));
                        wrefresh(stdscr);
*/                   }
#endif
                     if (step == FALSE) {
                        result = reduce(problem, result, high, -1, FALSE);
                        if (terminal) {
                           outstring_ns(stdscr, "\n\r");
                           outexp = print_expression(stdscr, result);
                           add_string_to_history(outexp, &output_history);
                           print_stats(stdscr, stats);
                           wrefresh(stdscr);
                           if (debug) {
                              outstring(stdscr, "\n\rResult graph:");
                              wrefresh(stdscr);
                              print_mem(stdscr, result, ws);
                           }
                        }
                        focus = OLD;
                     }
                     break;
                     
      case LAM_DEF:  /* associating a graph with a symbol */
         {
            symbol *name = high->op.sym;
            if (name->typ != SYM) {
               foutstring(stdscr, "\n\rUser redefining %s builtin.", 
                        name->print_name);
               wrefresh(stdscr);
               name->typ = SYM;
            }
            if (terminal) add_string_to_history(exp, &input_history);
            if (focus != NONE) low = problem;
            low->type = DEF; low->op.sym = name;
            result = compile_graph(high-1, end_token, low+2);
            (low+1)->type = EOD; (low+1)->op.addr = result-1;
            name->def.user = low + 2;
            low = result + 1;
            focus = NONE;
            if (terminal) {
               foutstring_ns(stdscr, "\n\r%s defined.", name->print_name);
               wrefresh(stdscr);
            }
            break;
         }
         
      case LAM_RED:  /* reduce current focus expression */        
            if (focus != NONE) {
               low = problem;
               if (focus == OLD) {
                  result = copy_graph(result, ws+1);
#ifdef DEBUG_PARSER
                  if (debug) {
                     outstring(stdscr, "\n\rCopied graph is now:");
                     wrefresh(stdscr);
                     print_mem(stdscr, ws+1, result);
                  }
#endif
                  result = shift_memory(ws+1, result, low) + 1;
                  problem = low;
#ifdef DEBUG_PARSER
                  if (debug) {
                     outstring(stdscr, "\n\rMoved graph is now:");
                     wrefresh(stdscr);
                  }
#endif
               }
#ifdef DEBUG_PARSER
               if (debug) {
                  outstring(stdscr, "\n\rProblem graph:");
                  wrefresh(stdscr);
                  print_mem(stdscr, problem, result-2);
               }
#endif
               result = reduce(problem, result, high, reds_allowed, FALSE);
               if (terminal) {
                  outstring_ns(stdscr, "\n\r");
                  outexp = print_expression(stdscr, result);
                  add_string_to_history(outexp, &output_history);
                  print_stats(stdscr, stats);
                  wrefresh(stdscr);
               }
               if (debug) {
                  outstring(stdscr, "\n\rResult graph:");
                  wrefresh(stdscr);
                  print_mem(stdscr, result, ws);
               }
               focus = OLD;
            }
            else {
               if (terminal) {
                  outstring_ns(stdscr, "\n\rNo current expression!");
                  wrefresh(stdscr);
               }
            }
            break;
            
      case LAM_COM:  /* LRS System command  */
            if (comm_switch == NULL)
               handle_command(command->print_name, NULL);
            else
               handle_command(command->print_name, comm_switch->print_name);
            break;

      case LAM_STRUCT:     /* Structure definition */
            low = struct_def(high, low) + 1;
            focus = NONE;
            break;


      case LAM_RDEF:
         {
            symbol *name = high->op.sym;
            if (name->typ != SYM) {
               foutstring(stdscr, "\n\rUser redefining %s builtin.", 
                        name->print_name);
               wrefresh(stdscr);
               name->typ = SYM;
            }
            if (terminal) add_string_to_history(exp, &input_history);
            if (focus != NONE) low = problem;
            low->type = DEF; low->op.sym = name;
            result = compile_graph(high-1, end_token, low+2);
            name->def.user = low + 2;
            problem = low+2;
            total_reds = 0;
            result = reduce(problem, result, high, -1, FALSE);
            if (terminal) {
                outstring_ns(stdscr, "\n\r");
                outexp = print_expression(stdscr, result);
                add_string_to_history(outexp, &output_history);
                print_stats(stdscr, stats);
                wrefresh(stdscr);
                if (debug) {
                   outstring(stdscr, "\n\rResult graph:");
                   wrefresh(stdscr);
                   print_mem(stdscr, result, ws);
                }
            }
            result = copy_graph(result, ws+1);
            result = shift_memory(ws+1, result, low+2);
            (low+1)->type = EOD; (low+1)->op.addr = result;
            low = result + 1;
            focus = NONE;
            if (terminal) {
               foutstring_ns(stdscr, "\n\r%s defined.", name->print_name);
               wrefresh(stdscr);
            }
            break;
         }
            
   }
}




/* COPY_GRAPH
/* Copies a graph whose root is at FROM so that its new root is at TO.
/*
/* Returns the first available location after the new graph.
*/

node *copy_graph(from, to)
node *from, *to;
{
   int counter = 0;
   node *next = to;
   node *up, *temp;
#ifdef DEBUG_COPY
   if (debug) {
      foutstring(stdscr, "\n\rcopy_graph: from (%p) = ", from);
      print_node(stdscr, from);
      foutstring(stdscr, ", to (%p) = ", to);
      print_node(stdscr, to);
   }
#endif
   while (from->class != HEAD) {
      if (from->type == IP) from = from->op.addr;
      else *(next++) = *(from++);                        /* copy spine */
   }
   *next = *from;                                       /* copy head */
   up = next;
   while (up >= to) {
      if ((up->type == PTR) || (up->type == LETREC)) {     /* move arg */
         temp = up->op.addr;
         if (temp->type == MARKER)
            up->op.addr = temp->op.addr;
         else {         
            ++next;
            up->op.addr = next;
            next = copy_graph(temp, next);
            if (up->type == PTR) {
               temp->type = MARKER; temp->op.addr = up->op.addr;
            }
         }
      }
      --up;
   }
   return(next);
}



/* HANDLE_COMMAND
/* Handler for LRS System commands.  COM is the command given and MODIFIER
/* is the command switch.
*/

void handle_command(com, modifier)
char *com, *modifier;
{
#ifdef DEBUG_PARSER  
  if (debug) {
    foutstring(stdscr, "\n\rhandle_command:  com = %s, modifier = %s", com, modifier);
    wrefresh(stdscr);
  }
#endif
   if (stricmp(com, "EXIT") == 0) {
#ifdef IBM
      hfree((void huge *) mem);
      hfree((void huge *) constack);
#endif
#ifdef SUN
      free(mem);
      free(constack);
#endif
      outstring_ns(stdscr, "\n\rExiting HORSE system.\n\r");
      wrefresh(stdscr);
      endwin();
      exit(0);
   }

   else if (stricmp(com, "DUMP") == 0) {
      outstring(stdscr, "\n\rPROBLEM GRAPH:");
      print_mem(stdscr, problem, result -1);
      outstring(stdscr, "\n\rRESULT GRAPH:");
      print_mem(stdscr, result, ws);
      outstring(stdscr, "\n\rENVIRONMENT: ");
      print_mem(stdscr, fs, high);
      wrefresh(stdscr);
   }
   
   else if (stricmp(com, "LOAD") == 0) {
      load_file(modifier, line_number, file_name);
   }
      
   else if (stricmp(com, "LOG") == 0) {
      if (stricmp(modifier, "END") != 0) {
         if ((logfile = fopen(modifier, "w")) == NULL) {
            foutstring_ns(stdscr, "\n\rUnable to open log file %s", modifier);
            wrefresh(stdscr);
            return;
         }
         logging = 1;
         foutstring_ns(stdscr, "\n\rLogging output to file %s", modifier);
         wrefresh(stdscr);
         return;
      }
      else if (stricmp(modifier, "END") == 0) {
         fclose(logfile);
         logging = 0;
         outstring_ns(stdscr, "\n\rLog File Closed.");
         wrefresh(stdscr);
         return;
      }
      else {
         outstring(stdscr, "\n\rNeed a Log file name.");
         wrefresh(stdscr);
      }
   }
   
   else if (stricmp(com, "DEBUG") == 0)
      set_binary_mode(com, &debug, modifier);
   else if (stricmp(com, "FORCE") == 0) 
      set_binary_mode(com, &force, modifier);
   else if (stricmp(com, "STATS") == 0) 
      set_binary_mode(com, &stats, modifier);
   else if (stricmp(com, "STEP") == 0) {
      set_binary_mode(com, &step, modifier);
      if (step == FALSE) focus = NONE;
   }
   else if (stricmp(com, "SUPRESS") == 0) {
      set_binary_mode(com, &supress_out, modifier);
   }

   else if (stricmp(com, "SHOW") == 0) {
      if (!supress_out) {
         if (modifier == NULL) {
            outstring(stdscr, "\n\rSHOW definition");
            wrefresh(stdscr);
         }
         else {
            symbol *symbol_lookup();
            symbol *sym = symbol_lookup(modifier, SYM);
            if (sym->def.user == NULL) {
               foutstring(stdscr, "\n\rNo definition for %s", modifier);
               wrefresh(stdscr);
            }
            else if (sym->typ != SYM) {
               foutstring(stdscr, "\n\r%s is not a user symbol", modifier);
               wrefresh(stdscr);
            }
            else print_mem(stdscr, (sym->def.user-2), 
                           (sym->def.user-1)->op.addr);
         }
      }
   } 
}

/* LOAD_FILE
/* Loads a file into the reduction system. Returns 1 if everything went
/* OK, 0 otherwise.
*/

int load_file(name, line, current_file)
char *name, *current_file;
int line;
{
   FILE *file;
   int temp_supress, temp_step;

   if ((file = fopen(name, "r")) == NULL) {
      char *ptr;
      for (ptr = name; *ptr != '\0'; ptr++) 
         if (isalpha(*ptr)) *ptr = tolower(*ptr);
      if ((file = fopen(name, "r")) == NULL) {
         foutstring(stdscr, "\n\rUnable to open file %s", name);
         return(0);
      }
   }
      
   input_file = file;
   foutstring(stdscr, "\n\rLoading %s...", name);
   wrefresh(stdscr);
   temp_supress = supress_out;
   temp_step = step;
   supress_out = TRUE;
   step = FALSE;
   line_number = 0;
   file_name = name;
   while (!feof(file)) rep_loop(file);
   fclose(file);
   supress_out = temp_supress;
   step = temp_step;
   outstring(stdscr, "done.");
   wrefresh(stdscr);
   line_number = line;
   file_name = current_file;
   return(1);
}


/* SHIFT_MEMORY
/* Shifts a block of graph memory from BEGIN to END to a new
/* location starting at DEST.   DEST must be outside of BEGIN-END
/* for this to work properly; otherwise the shifted copy will be
/* corrupted.
/*
/* Returns the last addr in the new block.
*/

node *shift_memory(begin, end, dest)
node *begin, *end, *dest;
{
   long dif = begin - dest;

   while (begin <= end) {
      *dest = *begin;
      if (dest->type == PTR || dest->type == LETREC)
         dest->op.addr = dest->op.addr - dif;
      ++dest;
      ++begin;
   }
   return(dest-1);
}



/* SUM_TIMES
/* Add the difference of T1 and T2 to the running total execution time.
*/

void sum_times(t1, t2)
struct timeb *t1, *t2;
{
   long secs;
   unsigned short millisecs;

   secs = (long) t2->time - (long) t1->time;
   if (t1->millitm > t2->millitm) {
      --secs;
      millisecs = (unsigned short) ((int) t2->millitm + 1000 - 
                                    (int) t1->millitm);
   }
   else millisecs = t2->millitm - t1->millitm;

   total_seconds += secs;
   total_millisecs += millisecs;
   if (total_millisecs >= 1000) {
      total_seconds++;
      total_millisecs -= 1000;
   }
}




/* PRINT_STATS
/* Prints out statistics about the last reduction sequence.
*/

void print_stats(stream, flag)
WINDOW *stream;
int flag;
{
   foutstring(stream, "\n\r%lu reductions, total.", total_reds);
   foutstring(stream, "\n\rElapsed time: %ld.", total_seconds);
   if (total_millisecs < 100) outstring(stream, "0");
   if (total_millisecs < 10) outstring(stream, "0");
   foutstring(stream, "%hu seconds.", total_millisecs);
   wrefresh(stream);
   
   if (flag) {
      foutstring(stream, "\n\n\rinstructions executed: %lu", instructs);
      foutstring(stream, "\n\rmax graph nodes: %lu", (unsigned long) (max_graph - result));
      foutstring(stream, "\n\r   max env size: %lu", (unsigned long) (initial_env - max_env));     
      foutstring(stream, "\n\r max stack size: %lu", (unsigned long) (max_stack - constack));
      foutstring(stream, "\n\r   max aux size: %lu", (unsigned long) (initial_aux - max_aux));
      wrefresh(stream);    
   }
}



/* SET_BINARY_MODE
/* Sets the binary mode 
*/

void set_binary_mode(mode, var, value)
int *var;
char *mode, *value;
{
   if ((value == NULL) && !supress_out) {
      if (*var) foutstring(stdscr,"\n\r%s ENABLED", mode);
         else foutstring(stdscr,"\n\r%s DISABLED", mode);
      }
      else if (stricmp(value, "ON") == 0) {
         *var = TRUE;
         if (!supress_out) foutstring(stdscr, "\n\r%s ENABLED", mode);
      }
      else if (stricmp(value, "OFF") == 0) {
         *var = FALSE;
         if (!supress_out) foutstring(stdscr, "\n\r%s DISABLED", mode);
      }
      else if (!supress_out)
         foutstring(stdscr, "\n\r%s %s UNKNOWN!", mode, value);

      wrefresh(stdscr);
}



/* STRUCT_DEF
/* Build up a creator function with symbol "make-" <struct name>,
/* and accessor functions with symbols <struct name>-<element name>.
/* DEF points to the beginning of the defstruct form in high graph
/* space, and SPACE points to the area where the definition graph bodies will
/* be put in low graph space.
/*
/* Returns the next free location after the definition bodies.
*/

node *struct_def(def, space)
node *def, *space;
{
   symbol *strsym = def->op.sym;
   char *name = strsym->print_name;
   int i, size;
   symbol *sym;
   node *eod, *ptr;
   extern char lex_buffer[];
   
   if (strsym->typ != SYM) {
      foutstring(stdscr, "\n\rUser redefining %s builtin.", name);
      wrefresh(stdscr);
      strsym->typ = SYM;
   }

   /* Create the constructor function */
   strcpy(lex_buffer, "make-");
   strcat(lex_buffer, name);
   sym = symbol_lookup(lex_buffer, SYM);
   (++space)->class = CONTROL; space->type = DEF; space->op.sym = sym;
   (++space)->class = CONTROL; space->type = EOD;
   eod = space;
   sym->def.user = space + 1;
   for (ptr = def-1, i = 0; ptr->type != CLOSE_PAREN; ptr--, i++) {
      (++space)->class = BINDER; space->type = LAMBDA; space->op.sym = ptr->op.sym;
   }
   size = i;
   (++space)->class = PAIR+BINDER; space->type = LAMBDA; space->op.sym = strsym;
   for (; i > 0; i--) {
      (++space)->class = APPLY; space->type = VAR; space->op.index = size - i + 1;
   }
   (++space)->class = HEAD; space->type = VAR; space->op.index = 0;
   eod->op.addr = space;


   /* Create selector functions */
   for (i = 0; i < size; i++) {
      strcpy(lex_buffer, name);
      strcat(lex_buffer, "-");
      strcat(lex_buffer, (def - 1 - i)->op.sym->print_name);
      sym = symbol_lookup(lex_buffer, SYM);

      (++space)->class = CONTROL; space->type = DEF; space->op.sym = sym;
      (++space)->class = CONTROL; space->type = EOD;
      eod = space;
      sym->def.user = space + 1;
      (++space)->class = BINDER; space->type = LAMBDA; space->op.sym = strsym;
      (++space)->class = APPLY; space->type = PTR; space->op.addr = space + 2;
      (++space)->class = HEAD; space->type = VAR; space->op.index = 0;
      for (ptr = def-1; ptr->type != CLOSE_PAREN; ptr--) {
         (++space)->class = BINDER; space->type = LAMBDA;
         space->op.sym = ptr->op.sym;
      }
      (++space)->class = HEAD; space->type = VAR; space->op.index = size - (i + 1);
      eod->op.addr = space;
   }

   if (!supress_out) {
      foutstring(stdscr, "\n\rStructure %s defined.", name);
      wrefresh(stdscr);
   }
   return(space);
}

