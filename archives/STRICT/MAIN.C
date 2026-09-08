/* Driver for the Lambda Reduction System
/* Mike Hilton, 20 July 1989
*/

#include <stdio.h>
#include <io.h>
#include <time.h>
#include <sys\types.h>
#include <sys\timeb.h>
#include <setjmp.h>
#include <signal.h>
#include <float.h>
#include "lrs.h"


symbol	*command;   	/* LRS command value, passed from parser globally */
symbol	*comm_switch;  /* command modifier */
int		expr_type;     /* set by parser to tell if input is a command or exp */
int		focus;         /* boolean flag, if there is a current expression */
int		force;         /* boolean flag, if output should be forced to n.f. */
node		*high;         /* Highest location in free graph memory */
node		*low;          /* Lowest location in free graph memory */
node		*problem;      /* root of the problem graph */
int		reds_allowed;  /* number of reductions allowed by user   */
node		*result;       /* root of the result graph */
int		stats;         /* boolean flag, if statistics should be printed */
int		step;          /* boolean flag, if in step mode */
int		supress_out;   /* boolean flag, if output should be suppressed */

struct timeb start_time, stop_time;		/* used to measure elapsed time */
jmp_buf	abort_context;						/* error handling return context */

extern int total_reds, reductions;
extern node *ws, *fs, *max_graph, *max_env, *initial_env;
extern union control *max_stack, *max_aux, *initial_aux, *stack, *aux;
extern unsigned long instructs;
extern history input_history;

/* Prototypes */
int	abort_handler(int signal);
node	*copy_cons(node *from, node *to);
node	*copy_graph(node *from, node *to);
node	*copy_struct(node *source, node *to);
int	ctrlc_handler(int signal);
int	fp_handler(int signal, int signum);
void	handle_command(char *command, char *modifier);
void	print_stats(FILE *stream, int flag);
void	rep_loop(FILE *in, FILE *out);
void	set_binary_mode(char *mode, int *var, char *value);
node	*shift_memory(node *begin, node *end, node *dest);
node	*struct_def(node *def, node *space);


#define NEW    1  /* values for FOCUS */
#define OLD    2
#define NONE   3
     
main(argc, argv)
int argc;
char *argv[];
{
   int   terminal;   /* Boolean flag if input stream is a terminal */
   
   install_primitives();
   terminal = (isatty (fileno(stdin)));   
   high = &mem[MEM_SIZE-1];
   low  = mem;
	fs = high;
	ws = low;
	stack = constack;
	aux = &constack[CONTROL_SIZE-1];
   focus = NONE;
   force = FALSE;
   step = FALSE;
   stats = TRUE;
   supress_out = FALSE;
   
   while (argc > 1) { 
      handle_command("load", argv[--argc]);
      fprintf(stdout, "\n");
   }

   if (terminal) {
      fprintf(stdout, "\nLambda Reduction System, Version 0.0");
      fprintf(stdout, "\n%d graph nodes, %d control stack", 
                  MEM_SIZE, CONTROL_SIZE);
   }

   /* if an error occurs later, control jumps to this point */
	if (setjmp(abort_context) != 0)
			fprintf(stderr, "\n\n REDUCTION ABORTED!\n");

	/* install a control-c interrupt handler */
	if (signal(SIGINT, ctrlc_handler) == SIG_ERR)
		fprintf(stderr, "\nControl-C signal handler failed to install.");
	/* install a floating point error handler */
	if (signal(SIGFPE, fp_handler) == SIG_ERR)
		fprintf(stderr, "\nFloating point error handler failed to install.");
	/* install a SIGABRT handler */
	if (signal(SIGABRT, abort_handler) == SIG_ERR)
		fprintf(stderr, "\nAbnormal termination handler failed to install.");
			
	history_initialize(&input_history);
   while (1) { 
      if (terminal) fprintf(stdout, "\nred1.5> ");
      rep_loop(stdin, stdout);
   }
}


int abort_handler(sig)
int sig;
{
	fprintf(stderr, "\nAbnormal termination of reduction...");
	longjmp(abort_context, 1);
}

int ctrlc_handler(sig)
int sig;
{
	fprintf(stderr, "\nUser Interrupt...");
	longjmp(abort_context, 1);
}

int fp_handler(sig, num)
int sig, num;
{
	fprintf(stderr, "\nFloating point error...");
	_fpreset();
	longjmp(abort_context, 1);
}






/* REP_LOOP
/* Read-Eval-Print Loop.
*/


void rep_loop(in, out)
FILE *in, *out;
{
   char *exp;
   node *end_token;
   
   exp = input_line_editor(in, out);
	add_string_to_history(exp, &input_history);
#ifdef DEBUG
	fprintf(stdout, "\nInput string: \"%s\"", exp);
#endif   
   end_token = parse_expression(exp, low, high);
   if (end_token == NULL) return;
#ifdef DEBUG
	fprintf(stdout, "\nParse string:");
	print_mem(stdout, end_token, high);
#endif


   switch (expr_type) {
      case LAM_EXP:  /* establish a new focus expression */
                     if (focus != NONE) low = problem;
                     result = compile_graph(high, end_token, low) + 1;
                     problem = low;
                     focus = NEW;
                     low = result;
                     total_reds = 0;
#ifdef DEBUG
      fprintf(stdout, "\nProblem Graph:");
      print_mem(stdout, problem, result-2);
      fprintf(stdout, "\nProblem string:\n");
      print_expression(stdout, problem);
#endif

                     if (step == FALSE) {
                        result = reduce(problem, result, high, -1, FALSE);
                        if (! supress_out) {
                           putc('\n', out);
                           print_expression(out, result);
                           print_stats(out, stats);
#ifdef DEBUG
	fprintf(stdout, "\nResult graph:");
   print_mem(stdout, result, ws);
#endif
                        }
                        focus = OLD;
                     }
                     break;
                     
      case LAM_DEF:  /* associating a graph with a symbol */
         {
            symbol *name = high->op.sym;
            if (name->typ != SYM) {
               fprintf(stderr, "\nUser redefining %s builtin.", 
                        name->print_name);
               name->typ = SYM;
            }
            if (focus != NONE) low = problem;
            low->type = DEF; low->op.sym = name;
            result = compile_graph(high-1, end_token, low+2);
            (low+1)->type = EOD; (low+1)->op.addr = result-1;
            name->def.user = low + 2;
            low = result + 1;
            focus = NONE;
            if (!supress_out) 
               fprintf(out, "\n%s defined.", name->print_name);
            break;
         }
         
      case LAM_RED:  /* reduce current focus expression */        
            if (focus != NONE) {
               low = problem;
               if (focus == OLD) {
                  result = copy_graph(result, ws+1);
#ifdef DEBUG
	fprintf(stdout, "\nCopied graph is now:");
	print_mem(stdout, ws+1, result);
#endif	
                  result = shift_memory(ws+1, result, low) + 1;
                  problem = low;
#ifdef DEBUG
   fprintf(stdout, "\nMoved graph is now:");
#endif
               }
#ifdef DEBUG
	fprintf(stdout, "\nProblem graph:");
   print_mem(stdout, problem, result-1);
	putc('\n', stdout);
#endif
               result = reduce(problem, result, high, reds_allowed, FALSE);
               if (!supress_out) {
                  print_expression(out, result);
                  print_stats(out, stats);
               }
#ifdef DEBUG
   fprintf(stdout, "\nResult graph:");
   print_mem(stdout, result, ws);
#endif                  
               focus = OLD;
            }
            else {
               if (!supress_out) fprintf(out, "\nNo current expression!");
            }
            break;
            
      case LAM_COM:  /* LRS System command  */
            if (comm_switch == NULL)
               handle_command(command->print_name, NULL);
            else
               handle_command(command->print_name, comm_switch->print_name);
            break;

      case LAM_STRUCT:		/* Structure definition */
#ifdef DEBUG
	fprintf(stdout,"\nStructure Definition");
#endif
      		low = struct_def(high, low) + 1;
				focus = NONE;
      		break;
            
   }
}



/* HANDLE_COMMAND
/* Handler for LRS System commands.  COM is the command given and MODIFIER
/* is the command switch.
*/

void handle_command(com, modifier)
char *com, *modifier;
{
   if (stricmp(com, "EXIT") == 0) exit(0);

   else if (stricmp(com, "DUMP") == 0) {
   	fprintf(stdout, "\nRESULT GRAPH:");
   	print_mem(stdout, result, ws);
   	fprintf(stdout, "\n\nENVIRONMENT: ");
   	print_mem(stdout, fs, high);
   }
   
   else if (stricmp(com, "LOAD") == 0) {
      FILE *file;
      int temp_supress, temp_step;

      if ((file = fopen(modifier, "r")) == NULL) {
         fprintf(stderr, "\nUnable to open file %s", modifier);
         return;
      }
      fprintf(stdout, "Loading %s...", modifier);
      temp_supress = supress_out;
      temp_step = step;
      supress_out = TRUE;
      step = FALSE;
      while (!feof(file)) rep_loop(file, NULL);
      fclose(file);
      fprintf(stdout, "done.");
      supress_out = temp_supress;
      step = temp_step;
      return;
   }

   else if (stricmp(com, "FORCE") == 0) 
      set_binary_mode(com, &force, modifier);
   else if (stricmp(com, "STATS") == 0) 
      set_binary_mode(com, &stats, modifier);
   else if (stricmp(com, "STEP") == 0) {
      set_binary_mode(com, &step, modifier);
		if (step == FALSE) focus = NONE;
	}

   else if (stricmp(com, "SHOW") == 0) {
      if (!supress_out) {
         if (modifier == NULL) fprintf(stdout, "\nSHOW definition");
         else {
            symbol *symbol_lookup();
            symbol *sym = symbol_lookup(modifier, SYM);
            if (sym->def.user == NULL)
               fprintf(stdout, "\nNo definition for %s", modifier);
            else if (sym->typ != SYM)
               fprintf(stdout, "\n%s is not a user symbol", modifier);
            else print_mem(stdout, (sym->def.user-2), 
                           (sym->def.user-1)->op.addr);
         }
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

   while (from->head != TRUE) *(next++) = *(from++);    /* copy spine */
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
      else if (up->type == STRUCT) {	/* copy from free space to graph space */
      	if (up->op.addr->type == MARKER) 		/* has already been copied */
      		up->op.addr = up->op.addr->op.addr;
			else 
				next = copy_struct(up, next);
      }
      else if (up->type == CONS) {
      	if (up->op.addr->type == MARKER)
      		up->op.addr = up->op.addr->op.addr;
      	else
      		next = copy_cons(up, next);
      }
      --up;
   }
   return(next);
}

/* COPY_CONS
/* Copy a list cons cell and its contents
*/

node *copy_cons(source, to)
node *source, *to;
{
	node *from = source->op.addr;
	node *ptr, *temp;
	int i;
	
	source->op.addr = ++to;
	*to = *from;  											/* copy cdr */
	temp = to;
	from->type = MARKER; from->op.addr = to;		/* mark cell as copied */
	*(++to) = *(++from);									/* copy car */

	for (i = 2; i > 0; i--) {
		if ((temp->type == PTR) || (temp->type == LETREC)) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else {
				++to;
				temp->op.addr = to;
				to = copy_graph(ptr, to);
				ptr->type = MARKER; ptr->op.addr = temp->op.addr;
			}
		}
		else if (temp->type == STRUCT) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else 
				to = copy_struct(temp, to);
		}
		else if (temp->type == CONS) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else
				to = copy_cons(temp, to);
		}
		temp++;
	}
	return(to);
}




/* COPY_STRUCT
/* Copy a structure and its contents
*/

node *copy_struct(source, to)
node *source, *to;
{
	node *from = source->op.addr;
	int  size;
	node *next, *temp, *ptr;
	
	size = (from - 1)->op.intval;
	next = to + size + 2;
	source->op.addr = next;
	temp = next;
	*temp = *from;  										/* copy tag */
	from->type = MARKER; from->op.addr = next;	/* mark as copied */
	*(--temp) = *(--from);								/* copy size */
	for (; size > 0; size--) {
		*(--temp) = *(--from);							/* copy element */
		if ((temp->type == PTR) || (temp->type == LETREC)) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else {
				++next;
				temp->op.addr = next;
				next = copy_graph(ptr, next);
				ptr->type = MARKER; ptr->op.addr = temp->op.addr;
			}
		}
		else if (temp->type == STRUCT) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else 
				next = copy_struct(temp, next);
		}
		else if (temp->type == CONS) {
			ptr = temp->op.addr;
			if (ptr->type == MARKER)
				temp->op.addr = ptr->op.addr;
			else
				next = copy_cons(temp, next);
		}
	}
	return(next);
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
		if (dest->type == PTR || dest->type == STRUCT || dest->type == LETREC ||
			 dest->type == CONS)
			dest->op.addr = dest->op.addr - dif;
		++dest;
		++begin;
	}
	return(dest-1);
}







/* PRINT_STATS
/* Prints out statistics about the last reduction sequence.
*/

void print_stats(stream, flag)
FILE *stream;
int flag;
{
   long secs;
   unsigned short millisecs;

   fprintf(stdout, "\n%d reductions, total.", total_reds);
   
   secs = (long) stop_time.time - (long) start_time.time;
   if (start_time.millitm > stop_time.millitm) {
      --secs;
      millisecs = (unsigned short) ((int) stop_time.millitm + 1000 - 
                                    (int) start_time.millitm);
   }
   else millisecs = stop_time.millitm - start_time.millitm;

   fprintf(stream, "\nElapsed time: %ld.", secs);
   if (millisecs < 100) putc('0',stream);
   if (millisecs < 10) putc('0', stream);
   fprintf(stream, "%hu seconds.", millisecs);

   if (flag) {
		fprintf(stream, "\n\ninstructions executed: %lu", instructs);
   	fprintf(stream, "\nmax graph nodes: %lu", (unsigned long) (max_graph - result));
   	fprintf(stream, "\n   max env size: %lu", (unsigned long) (initial_env - max_env));   	
/*   	fprintf(stream, "\n   max env size: %lu", (unsigned long) (&mem[MEM_SIZE-1] - max_env)); */
   	fprintf(stream, "\n max stack size: %lu", (unsigned long) (max_stack - constack));
/*   	fprintf(stream, "\n   max aux size: %lu", (unsigned long) (&constack[CONTROL_SIZE-1] - max_aux)); */
   	fprintf(stream, "\n   max aux size: %lu", (unsigned long) (initial_aux - max_aux));
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
      if (*var) fprintf(stdout,"%s ENABLED", mode);
         else fprintf(stdout,"%s DISABLED", mode);
      }
      else if (stricmp(value, "ON") == 0) {
         *var = TRUE;
         if (!supress_out) fprintf(stdout, "%s ENABLED", mode);
      }
      else if (stricmp(value, "OFF") == 0) {
         *var = FALSE;
         if (!supress_out) fprintf(stdout, "%s DISABLED", mode);
      }
      else if (!supress_out)
         fprintf(stdout, "\x07%s %s UNKNOWN!", mode, value);
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
	int size = 0;
	symbol *sym;
	symbol *select = symbol_lookup("select", PRIM_0);
	extern char lex_buffer[];
	
   if (strsym->typ != SYM) {
      fprintf(stderr, "\nUser redefining %s builtin.", name);
      strsym->typ = SYM;
	}
	
	while ((--def)->type != CLOSE) {
		++size;
		strcpy(lex_buffer, name);
		strcat(lex_buffer, "-");
		strcat(lex_buffer, def->op.sym->print_name);
		sym = symbol_lookup(lex_buffer, SYM);
#ifdef DEBUG
	fprintf(stdout, "\ndefining %s", sym->print_name);
#endif
		(++space)->head = FALSE; space->type = DEF; space->op.sym = sym;
		(++space)->head = FALSE; space->type = EOD; space->op.addr = space+3;
		(++space)->head = FALSE; space->type = INT; space->op.intval = size;
		sym->def.user = space;
		(++space)->head = FALSE; space->type = SYM; space->op.sym = strsym;
		(++space)->head = TRUE; space->type = PRIM_0; space->op.sym = select;
	}
	strcpy(lex_buffer, "make-");
	strcat(lex_buffer, name);
	sym = symbol_lookup(lex_buffer, SYM);
#ifdef DEBUG
	fprintf(stdout, "\ndefining %s", sym->print_name);
#endif
	(++space)->head = FALSE; space->type = DEF; space->op.sym = sym;
	(++space)->head = FALSE; space->type = EOD; space->op.addr = space+3;
	(++space)->head = FALSE; space->type = INT; space->op.intval = size;
	sym->def.user = space;
	(++space)->head = FALSE; space->type = SYM; space->op.sym = strsym;
	(++space)->head = TRUE; space->type = PRIM_0;
	space->op.sym = symbol_lookup("pack", PRIM_0);

	if (!supress_out) fprintf(stdout, "\nStructure %s defined.", name);
	return(space);
}

