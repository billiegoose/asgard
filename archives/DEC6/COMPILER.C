
# line 12 "compiler.Y"
#undef DEBUG
#undef DEBUG_BG
#undef DEBUG_FIND_INDEX
#undef DEBUG_LEX
#undef DEBUG_LETREC

#include <stdio.h>
#include <ctype.h>
#ifdef IBM
#include <stdlib.h>
#endif
#ifdef SUN
#include <floatingpoint.h>
#endif
#include <string.h>
#include <curses.h>
#include "lrs.h"

#define FILE_IO   1     /* Values to direct lexical analyzer to read */
#define TERMINAL  2     /* input from a file or a string             */


/* These global variables are used to pass information between YACC  */
/* grammar statements, and also with the lexical analyzer.           */

node *bindings;     /* low mem addr where bindings are pushed during parse */
node *code;         /* hi mem addr where token string is built by parser   */
char *expression;          /* Expression to be compiled */
int expi;                  /* index into EXPRESSION     */
char *file_name;           /* name of current file being read */
int list_depth = 0;
int line_number;           /* number of current line being read in file */
unsigned char oper_type;   /* type of CONSTANT object   */
union operand oper;        /* value of CONSTANT object  */
int protect_marks;         /* number of #'s in front of a symbol */
int source;                /* flags if input from terminal or input_file */

extern FILE *input_file;
extern symbol  *command;
extern symbol  *comm_switch;
extern symbol  *nil;
extern symbol  *pair;
extern unsigned long reds_allowed;
extern int  expr_type;
extern node *fs;
extern union control *stack;
extern int debug;


/* Prototypes */
#ifdef IBM
node  *build_graph(node *start, node *end, node *dest);
node  *build_list(node *start, node *end, node *dest);
node  *compile_graph(node *start, node *end, node *dest);
node  *compile_let(node *start, node *end, node *dest);
node  *compile_letrec(node *start, node *end, node *dest);
node  *compile_letstar(node *start, node *end, node *dest);
int   delimiter(char c);
int   find_index(symbol *sym, node *addr, int protects);
symbol *symbol_lookup(char *str, int typ);
node  *matching_close_bracket(node *i);
node  *matching_close_paren(node *i);
node  *matching_open_bracket(node *i);
node  *matching_open_paren(node *i);
node  *parse_expression(char *exp, node *low, node *high);
void  write_mem(node *addr, unsigned char headp, unsigned char typ, union operand *oper);
#endif

#ifdef SUN
node  *build_graph();
node  *build_list();
node  *compile_graph();
node  *compile_let();
node  *compile_letrec();
node  *compile_letstar();
int   delimiter();
int   find_index();
symbol *symbol_lookup();
node  *matching_close_bracket();
node  *matching_close_paren();
node  *matching_open_bracket();
node  *matching_open_paren();
node  *parse_expression();
void  write_mem();
#endif

# line 101 "compiler.Y"
typedef union  {
   long intval;
   float floval;
   symbol *sym;
} YYSTYPE;
#define YYSUNION /* %union occurred */
#define DEFINITION 257
#define DEFSTRUCT 258
#define INTEGER 259
#define FLONUM 260
#define LAM 261
#define LETS 262
#define LETT 263
#define LETR 264
#define PROTECTED 265
#define SYMBOL 266
#define EOS 267
YYSTYPE yylval, yyval;
#define YYERRCODE 256

# line 581 "compiler.Y"

#ifdef DEBUG
main()
{
   char *exp;
   node *end;
   fs = &mem[MEM_SIZE-1];
   stack = constack;
   
   while (feof(stdin)) {
      fprintf(stdout, "\ncompile>");
      exp = input_line_editor(stdin, stdout);
      end = parse_expression(exp, mem, &mem[MEM_SIZE-1]);
      fprintf(stdout, "\nPARSED GRAPH:");
      print_mem(stdout, end, &mem[MEM_SIZE-1]);
      end = compile_graph(&mem[MEM_SIZE-1], end, mem);
      fprintf(stdout, "\nCOMPILED GRAPH:");
      print_mem(stdout, mem, end-1);
      fprintf(stdout, "\n\n");
      print_expression(stdout, mem);
   }
}
#endif

/* PARSE_EXPRESSION
/* Parses the expression EXP into a token string that starts at location
/* HIGH and continues downward.  Then global variable EXP_TYPE is set to
/* tell whether EXP is a lambda expression, command, or definition.
/*
/* EXP is the expression to be parsed; if it is NULL, then input is to
/* come from a file, otherwise it is a string to be parsed.
/* HIGH is a location in upper free memory where the token string is placed.
/* LOW is a location in lower free memory where a temporary stack is
/* constructed.
/*
/* Returns the location of the last token in the token string if parsing
/* was successful, NULL otherwise.  Also passes EXP_TYPE as a global.
*/

node *parse_expression(exp, low, high)
char *exp;
node *low, *high;
{
   if (exp == NULL) source = FILE_IO;
   else {
      source = TERMINAL;
      expression = exp;
      expi = -1;
   }  
   low->type = STOP;
   bindings = low;
   code = high + 1;
   expr_type = yyparse();
   if (expr_type < 0) return(NULL);
   else return(code);
}



/*
/* Parser Support Routines
*/

void reparse_letrec(start, end, bindings)
node *start, *end, *bindings;
{
   node *ptr;
   int index;

   while (start >= end) {
      switch (start->type) {
         case OPEN_PAREN:     ptr = matching_close_paren(start--);
                        reparse_letrec(start, ptr+1, bindings);
                        start = ptr - 1;
                        break;
         case LETREC:   ptr = matching_close_paren(--start);
                        reparse_letrec(start-1, ptr+1, bindings);
                        start = ptr - 1;
                        break;
         case LETSTAR:                       
         case LAMBDA:   *(++bindings) = *(start--);
                        break;
         case LET:
            {
               int count = 0;
               while (start->type == LET) {
                  ptr = matching_close_paren(--start);
                  reparse_letrec(start, ptr+1, bindings);
                  start = ptr - 1;
                  count++;
               }
               while (count > 0) write_mem(++bindings, 0, LET, NULL);
               break;
            }
         case SYM:
         case PRIM_0:
         case PRIM_1:
         case PRIM_2:   index = find_index(start->op.sym, bindings, 0);
                        if (index > -1) {
                           start->type = VAR; start->op.index = index;
                        }
                        start--;
                        break;
         case PROT:
            {
               index = find_index(((protected *)start->op.sym)->sym, bindings,
                                  ((protected *)start->op.sym)->marks);
               if (index > -1) {
                  start->type = VAR; start->op.index = index;
               }
               else if (index == -1) {
                  start->type = ((protected *)start->op.sym)->sym->typ;
                  start->op.sym = ((protected *)start->op.sym)->sym;
               }
               else
                  ((protected *)start->op.sym)->marks =
                     ((protected *)start->op.sym)->marks + index + 1;

               start--;
               break;
            }

         default:    start--; break;
      }
   }
}           






/* YYERROR
Error handling routine for YYPARSE.  This routine does nothing, because
error handling is performed in the grammar description action statements.
*/

yyerror(str)
char *str;
{ return(0); }



/* WRITE_MEM
Write a word into graph memory at location ADDR, with class field = CLASSP,
type field = TYP, and op field OPER.
*/

void write_mem(addr, classp, typ, oper)
node *addr;
unsigned char classp, typ;
union operand *oper;
{
   addr->class = classp;
   addr->type = typ;
   if (oper != NULL) addr->op = *oper;
   else addr->op.sym = NULL;
}




   
/* 
/* Lexical Analyzer Routines
*/

int delimiter(c)
char c;
{ return((c == '(' || c == ')' || c == '}' || c == '{' || c == '\0' ||
          c == ']' || c == '[' || c == ',' || c == ';' || c == '|')); }

#define LEX_BUFFER_SIZE 256
char lex_buffer[LEX_BUFFER_SIZE];

/* NEXTCHAR, UNNEXTCHAR
/* Nextchar returns the next character in the input stream to the lexical
/* analyzer.  If the input stream is a file, the character is read from
/* the file; if it is not a file, the char is extracted from the string
/* EXPRESSION.
/*
/* Unnextchar returns the last char read to the input source.
*/

char nextchar()
{
   char ch;
   
   if (source == TERMINAL) {
      return(expression[++expi]);
   }
   else if (source == FILE_IO) {
      ch = getc(input_file);
#ifdef DEBUG_LEX
      waddch(stdscr, ch);
      if (ch == '\n') waddch(stdscr, '\r');
      wrefresh(stdscr);
#endif
      if (ch == '\n') ++line_number;
      return(ch);
   }
}

void unnextchar(ch)
char ch;
{
   if (source == TERMINAL) --expi;
   else if (source == FILE_IO) {
      ungetc(ch, input_file);
      if (ch == '\n') --line_number;
   }
}


/* YYLEX
/* Lexical analyzer called by YYPARSE.  
/* Returns a token type and sets YYLVAL to the token value.
*/

yylex()
{
   char ch, nextch;
   int index = 0;    /* index into LEX_BUFFER */
   int sign = 1;     /* sign value of numbers */

   /* Eat up comment lines */
   do {  
      while (isspace((ch = nextchar())));  /* eat whitespace */
      if (ch == ';') {     /* comment -- eat up chars till end of line */
         for(;;) {
            ch = nextchar();
            if ((ch == '\n') || (ch == '\r') || (ch == '\0') || (ch == EOF))
            break;
         }
         unnextchar(ch);
      }
      else break;
   } while (1);

   
   if (ch == '\0') return(EOS);  /* End of String */
   if (ch == EOF) return(EOS);  /* End Of File */
       
   if (ch == '#') {              /* protected symbol */
      protect_marks = 1;
      while ((ch = nextchar()) == '#') {++protect_marks;}
      if (! (isgraph(ch) && !delimiter(ch))) return(ch);
      while (isgraph(ch) && !delimiter(ch)) { 
         if (index < LEX_BUFFER_SIZE - 1) lex_buffer[index++] = ch; 
         ch = nextchar();
      }
      lex_buffer[index] = '\0';
      unnextchar(ch);
      yylval.sym = symbol_lookup(lex_buffer, SYM);
      return(PROTECTED);
   }
   
   if (ch == '-') {              /* unary minus sign */
      nextch = nextchar();
      if (isdigit(nextch) || nextch == '.') {
         sign = -1;
         ch = nextch;
      } else {
         unnextchar(nextch);
      }}
   else if (ch == '+') {         /* unary plus sign */
      nextch = nextchar();
      if (isdigit(nextch) || nextch == '.') {
         sign = 1;
         ch = nextch;
      } else {
         unnextchar(nextch);
      }}
   
   if (ch == '.') {              /* leading decimal point */
      nextch = nextchar();
      if (isdigit(nextch)) {
         lex_buffer[index++] = ch;
         ch = nextch;
      } else {
         unnextchar(nextch);
      }}
         
   if (isdigit(ch)) {            /* digits */
      while (isdigit(ch)) { 
         if (index < LEX_BUFFER_SIZE - 1) lex_buffer[index++] = ch; 
         ch = nextchar();
      }
      if (ch == '.') {   
         lex_buffer[index++] = ch;
         while (isdigit((ch = nextchar()))) { 
            if (index < LEX_BUFFER_SIZE - 1) lex_buffer[index++] = ch; 
         }
      }
      if (isspace(ch) || delimiter(ch)) {
         unnextchar(ch);
         lex_buffer[index] = '\0';
         if (strchr(lex_buffer, '.') != NULL) {   /* flonum */
            yylval.floval = sign *  atof(lex_buffer);
            return(FLONUM);
         } else {                                 /* fixnum */
            yylval.intval = sign * atol(lex_buffer);
            return(INTEGER);
         }
      }
   }

   if (isgraph(ch) && !delimiter(ch)) {
      while (isgraph(ch) && !delimiter(ch)) { 
         if (index < LEX_BUFFER_SIZE - 1) lex_buffer[index++] = ch; 
         ch = nextchar();
      }
      lex_buffer[index] = '\0';
      unnextchar(ch);
      if (stricmp(lex_buffer, "LAMBDA") == 0) return (LAM);
      else if (stricmp(lex_buffer, "LET") == 0) return(LETT);
      else if (stricmp(lex_buffer, "LET*") == 0) return(LETS);
      else if (stricmp(lex_buffer, "LETREC") == 0) return(LETR);
      else if (stricmp(lex_buffer, "DEFINE") == 0) return (DEFINITION);
      else if (stricmp(lex_buffer, "DEFSTRUCT") == 0) return (DEFSTRUCT);
      else {
         yylval.sym = symbol_lookup(lex_buffer, SYM);
         return(SYMBOL);
      }
   }
   else {
      return(ch);
   }
}






/*
/* Expression-to-Graph Compiler Routines
*/

/* COMPILE_GRAPH
/* Compiles the token string created by YYPARSE into a lambda expression
/* graph.
/*
/* Returns the last location in the compiled graph.
*/

node *compile_graph(start, end, dest)
node *start, *end, *dest;
{
   node *ptr = start;

   while (ptr >= end) {
      if (ptr->type == PROT) {
         ptr->type = ((protected *)ptr->op.sym)->sym->typ;
         ptr->op.sym = ((protected *)ptr->op.sym)->sym;
      }
      ptr--;
   }
   return (build_graph(start, end, dest));
}


/* BUILD_GRAPH
/* Builds an expression graph out of the token string created by YYPARSE.
/* The token string is in high graph memory, beginning at START and ending
/* at END.  The root of the graph will be location DEST.
/*
/* Returns the last location in the graph.
*/

node *build_graph(start, end, dest)
node *start, *end, *dest;
{
   node *origin = dest;
   node *temp;   
#ifdef DEBUG_BG 
if (debug) foutstring(stdscr, "\n\rbuild_graph(%p, %p, %p)", start, end, dest);
#endif

   while (start != end) {
      if (end->type == CLOSE_BRACKET) {
         /* NONE OF THE LIST COMPILATION IS USED IN THIS VERSION */
         /* List expression */
         node *next = matching_open_bracket(end);
         if (next == start) {
            dest = build_list(start, end, dest);
            return(dest);
         }
         else {
            /* Skip list subexpression, leaving an empty ap node to be */
            /* filled in later.                                   */
            union operand op;
            op.addr = end;
            write_mem(dest++, APPLY, PTR, &op);
            end = next + 1;
         }
      }
      else if (end->type == CLOSE_PAREN) {
         /* Application node, a subgraph must be built */
         node *next = matching_open_paren(end);
         if (next == start) {
            /* False alarm, subgraph is in the head position */
            --start; ++end;                     /* Move inside parens */
            while (start->type == LAMBDA)       /* Copy any lambdas   */
               *dest++ = *start--;
            if (start->type == LETSTAR) {
               temp = dest - 1;
               dest = compile_letstar(start, end, dest);
               end = temp;
               break;
            }
            else if (start->type == LET) {
               temp = dest - 1;
               dest = compile_let(start, end, dest);
               end = temp;
               break;
            }
            else if (start->type == LETREC) {
               temp = dest - 1;
               dest = compile_letrec(start, end, dest);
               end = temp;
               break;
            }
         }
         else {
            /* Skip subexpression, leaving an empty ap node to be */
            /* filled in later.                                   */
            union operand op;
            op.addr = end;
            write_mem(dest++, APPLY, PTR, &op);
            end = next + 1;
         }
      }
      else {
         /* Application node, immediate data type */
         *dest++ = *end++;
      }
   }
   
   if (start == end) {
      /* Fill in the head position */
      *dest = *start;
      dest->class = HEAD;
      ++dest;
   end = dest - 1;
   }
  
   /* Build operand subgraphs */

   while (end >= origin) {
      if (end->type == PTR) {
         node *arg;
         arg = end->op.addr;
         switch (arg->type) {
            case CLOSE_PAREN:    start = matching_open_paren(arg); break;
            case CLOSE_BRACKET:  start = matching_open_bracket(arg); break;
         }
         end->op.addr = dest;
         dest = build_graph(start, arg, dest);
      }
      --end;
   }
   return(dest);
}


/* BUILD_LIST
/*
*/

node *build_list(start, end, dest)
node *start, *end, *dest;
{
   node *origin = dest;
   node *temp = ++end;
   node *arg;
   union operand op; 

#ifdef DEBUG_BG
if (debug) foutstring(stdscr, "\n\rbuild_list(%p, %p, %p)", start, end, dest);
#endif

   --start;
   if (end->type == CLOSE_PAREN) end = matching_open_paren(end);
   else if (end->type == CLOSE_BRACKET) end = matching_open_bracket(end);
   
   while (start > end) {
      if (start->type == OPEN_PAREN) {
         op.addr = matching_close_paren(start);
         write_mem(dest++, APPLY+PAIR, PTR, &op);
         start = op.addr-1;
      }
      else if (start->type == OPEN_BRACKET) {
         op.addr = matching_close_bracket(start);
         write_mem(dest++, APPLY+PAIR, PTR, &op);
         start = op.addr-1;
      }
      else {   /* immediate data */
         *dest = *(start--);
         (dest++)->class = APPLY+PAIR;
      }
   }
   
   /* Compile last item in list */
   start = dest;
   dest = build_graph(end, temp, dest);

   /* Compile subgraphs */
   while (start >= origin) {
      if (start->type == PTR) {
         arg = start->op.addr;
         switch (arg->type) {
            case CLOSE_PAREN:    temp = matching_open_paren(arg); break;
            case CLOSE_BRACKET:  temp = matching_open_bracket(arg); break;
         }
         start->op.addr = dest;
         dest = build_graph(temp, arg, dest);
      }
      start--;
   }
   return(dest);
}


/* COMPILE_LET
*/

node *compile_let(start, end, dest)
node *start, *end, *dest;
{
   node *ap, *binding, *var, *ptr;
   int count = 0;

#ifdef DEBUG_BG
if (debug) foutstring(stdscr, "\n\rcompile_let(%p, %p, %p)", start, end, dest);
#endif
   
   /* allocate enough spine locations for each var+binding */
   ptr = start;
   while (ptr->type == LET) {
      ++count;
      ++dest;
      ptr = matching_close_paren(ptr-1) - 1;
   }
   var = dest;
   ap = dest-1;

   /* Compile body of Let expression */
   dest = build_graph(ptr, end, dest+count);

   /* insert Let var and its binding */
   while (start->type == LET) {
      *(var) = *(start--);                      /* copy var */
      binding = dest;
      ptr = matching_close_paren(start);  
      dest = build_graph(start, ptr, dest);     /* compile binding */
      if (binding->class == HEAD) {             /* insert binding in spine */
         *ap = *binding;
         --dest;
      }
      else {
         ap->type = PTR;
         ap->op.addr = binding;
      }
      ap->class = APPLY;
      ++var;
      --ap;
      start = ptr-1;
   }

   return(dest);
}


/* COMPILE_LETREC
*/
node *compile_letrec(start, end, dest)
node *start, *end, *dest;
{
   node *var, *ptr;
   int count = 0;

#ifdef DEBUG_BG
if (debug) foutstring(stdscr, "\n\rcompile_letrec(%p, %p, %p)", start, end, dest);
#endif
   
   /* allocate enough spine locations for each var+binding */
   ptr = start;
   var = dest;
   while (ptr->type == LETREC) {
      dest->class = BINDER; dest->type = LETREC;
      ++dest;
      ++count;
      ptr = matching_close_paren(ptr-1) - 1;
   }

   /* Compile body of Let expression */
   dest->class = CONTROL; dest->type = RUP; dest->op.intval = count;
   dest = build_graph(ptr, end, ++dest);

   /* insert Letrec var and its binding */
   while (start->type == LETREC) {
      (var++)->op.addr = dest;
      /* copy symbol for var */
      dest->class = CONTROL; dest->type = SYM; dest->op.sym = start->op.sym;
      ptr = matching_close_paren(--start);
      dest = build_graph(start, ptr, ++dest);      /* compile binding */
      start = ptr-1;
   }

   return(dest);
}


/* COMPILE_LETSTAR
*/

node *compile_letstar(start, end, dest)
node *start, *end, *dest;
{
   node *ap, *end_def;

#ifdef DEBUG_BG
if (debug) foutstring(stdscr, "\n\rcompile_letstar(%p, %p, %p)", start, end, dest);
#endif

   if (start->type == LETSTAR) { /* definition in let* */
      ap = dest++;            /* place holder for ap to go */
      *(dest++) = *(start--); /* copy let* binding */
      end_def = matching_close_paren(start);
      dest = compile_letstar(end_def-1, end, dest);
      ap->class = APPLY; ap->type = PTR; ap->op.addr = dest;
      dest = build_graph(start, end_def, dest);
      if (ap->op.addr->class == HEAD) {   /* arg graph just built is atomic */
         *ap = *(ap->op.addr);
         dest--;
         ap->class = APPLY;
      }
   }
   else {         /* body of let* */
      dest = build_graph(start, end, dest);
   }

   return(dest);
}
   
/* FIND_INDEX
/* Looks up a symbol in the bindings stack, beginning at location ADDR.
/* PROTECTS is the number of binding protection characters prefixing the
/* symbol name.  
/*
/* Returns a positive integer as the binding index if found, and -1 -
/* any remaining protects if not found.
*/

int find_index(sym, addr, protects)
symbol *sym;
node *addr;
int protects;
{
   int index = 0;
#ifdef DEBUG_FIND_INDEX
	if (debug) {
		foutstring(stdscr, "\n\rfind_index(%s, %p, %d)", sym->print_name, addr, protects);
		wrefresh(stdscr);
	}
#endif
   while (addr->type != STOP) {
#ifdef DEBUG_FIND_INDEX
		if (debug) {
			foutstring(stdscr, "\n\r index = %d, addr = (%p) ", index, addr);
			print_node(stdscr, addr);
		}
#endif
      if (addr->type == MARKER)
         addr = addr->op.addr;
      else {
         if (((addr->type != LETREC) && (addr->op.sym == sym)) ||
             ((addr->type == LETREC) && (addr->op.addr->op.sym == sym))) {
            if (protects == 0) {
#ifdef DEBUG_FIND_INDEX
					if (debug) {
						foutstring(stdscr, "\n\r  found, returning %d", index);
						wrefresh(stdscr);
					}
#endif
               return(index);
            }
            else  --protects;
         }
         if (addr->type != 0) ++index;
         --addr;
      }
   }
#ifdef DEBUG_FIND_INDEX
	if (debug) {
		foutstring(stdscr, "\n\r  Not Found, returning %d", (-1 - protects));
		wrefresh(stdscr);
	}
#endif
   return(-1 - protects);
}



/* MATCHING_CLOSE_PAREN
/* Returns the address of the matching CLOSE_PAREN marker for the OPEN_PAREN
/* marker at address I.
*/

node *matching_close_paren(i)
node *i;
{
   int count;

   for (count = 1; count != 0;) {
      if ((--i)->type == OPEN_PAREN)   ++count;
      else if (i->type == CLOSE_PAREN) --count;
   }
   return(i);
}

/* MATCHING_OPEN_PAREN
/* Returns the address of the matching OPEN_PAREN marker for the CLOSE_PAREN
/* marker at address I.
*/

node *matching_open_paren(i)
node *i;
{
   int count;

   for (count = 1; count != 0;) {
      if ((++i)->type == OPEN_PAREN)   --count;
      else if (i->type == CLOSE_PAREN) ++count;
   }
   return(i);
}

/* MATCHING_CLOSE_BRACKET
/* Returns the address of the matching CLOSE_BRACKET marker for the
/* OPEN_BRACKET marker at address I.
*/

node *matching_close_bracket(i)
node *i;
{
   int count;

   for (count = 1; count != 0;) {
      if ((--i)->type == OPEN_BRACKET)   ++count;
      else if (i->type == CLOSE_BRACKET) --count;
   }
   return(i);
}

/* MATCHING_OPEN_BRACKET
/* Returns the address of the matching OPEN_BRACKET marker for the
/* CLOSE_BRACKET marker at address I.
*/

node *matching_open_bracket(i)
node *i;
{
   int count;

   for (count = 1; count != 0;) {
      if ((++i)->type == OPEN_BRACKET)   --count;
      else if (i->type == CLOSE_BRACKET) ++count;
   }
   return(i);
}



/* COUNT_ELEMENTS
/* Counts the number of expressions found between locations START and
/* END.
*/

int count_elements(start, end)
node *start, *end;
{
   int count = 0;
   
   while (end <= start) {
      if (end->type == CLOSE_PAREN) end = matching_open_paren(end);
      ++count;
      ++end;
   }
   return(count);
}




/*
/* Symbol Table Management Routines
/*
/*
/* All symbols are hashed into a table upon input.  Each structure in this
/* table contains a symbol's print name, type (either PRIM_x or SYM),
/* and the address of the graph associated with the symbol (if a global 
/* function has been defined for the symbol).
*/



/* HASH
/* Hash a word.  This is a simple hashing function that adds up the ascii 
/* values of the letters in the word, modulo HASHSIZE.
*/

int hash(word)
char *word;
{
   int hashval;

   for(hashval = 0; *word != '\0'; ) hashval += *word++;
   return(hashval % HASHSIZE);
}

/* PROTECTED_ALLOC
/* Allocate space for a protected symbol structure.
*/

protected *protected_alloc(sym, protects)
symbol *sym;
int protects;
{
   protected *new;

   if ((new = (protected *)malloc(sizeof(struct protected))) == NULL) {
      outstring(stdscr, "\n\rOUT OF MEMORY!! protected_alloc ");
      wrefresh(stdscr);
      return(NULL);
   }
   new->sym = sym;
   new->marks = protects;
   return(new);
}     

/* STRING_ALLOC
/* Allocate space for a string of given length SIZE.
*/

char *string_alloc(size)
int size;
{
   char *new;
   
   if ((new = (char *)malloc(size)) == NULL) {
      outstring(stdscr, "\n\rOUT OF MEMORY!! string_alloc ");
      wrefresh(stdscr);
      return(NULL);
   }
   return(new);
}


/* SYMBOL_ALLOC
/* Allocate space for a symbol.
*/

symbol *symbol_alloc()
{
   symbol *new;
   
   if ((new = (symbol *) malloc (sizeof(symbol))) == NULL) {
      outstring(stdscr, "\n\rOUT OF MEMORY!! symbol_alloc ");
      wrefresh(stdscr);
      return(NULL);
   }
   new->print_name = '\0';
   new->def.user = NULL;
   return(new);
}
   
          
/* SYMBOL_LOOKUP
/* Look up a string in the symbol table.  If it does not exist, add it.  
/* Returns a pointer to the symbol table entry.  Alphabetic characters
/* in words are converted to uppercase.
*/

symbol *symbol_lookup(word, type)
char *word;
int type;
{
   symbol *ptr;
   int hashval;
   char *i;

   /* convert to uppercase */
   for(i = word; *i != '\0'; i++) if (isalpha(*i) && islower(*i)) *i = toupper(*i);

   hashval = hash(word);
   /* Search symbol table */
   for (ptr = symbol_table[hashval]; ptr != NULL; ptr = ptr->link)
      if (strcmp(word, ptr->print_name) == 0)
         return(ptr);

   /* if not found in symbol table, insert it */
   ptr = symbol_alloc();
   ptr->print_name = string_alloc(strlen(word)+1);
   strcpy(ptr->print_name, word);   
   ptr->typ = type;
   ptr->link = symbol_table[hashval];
   symbol_table[hashval] = ptr;
   return(ptr);
}

   
FILE *yytfilep;
char *yytfilen;
int yytflag = 0;
int svdprd[2];
char svdnams[2][2];

int yyexca[] = {
  -1, 1,
  0, -1,
  -2, 0,
  -1, 3,
  261, 15,
  262, 19,
  263, 17,
  264, 21,
  -2, 13,
  -1, 19,
  261, 15,
  262, 19,
  263, 17,
  264, 21,
  -2, 13,
  -1, 50,
  93, 69,
  124, 69,
  -2, 67,
  0,
};

#define YYNPROD 85
#define YYLAST 244

int yyact[] = {
      17,      28,      17,      97,      87,       3,     107,      19,
      82,       4,      17,     104,      17,      83,      86,      19,
      54,      19,     101,      74,      47,      37,      36,      35,
      46,      42,      44,      40,      20,      21,     117,     114,
     111,      66,      63,      60,      57,      80,      31,      95,
       6,      67,      33,      18,      92,      49,      89,      96,
     105,      93,     102,      90,      99,     129,     128,     127,
      11,       2,      11,       6,      64,      61,      58,      55,
      96,      93,      11,      90,      11,      32,      78,      77,
      76,      48,      75,      50,      70,      69,      51,      18,
      38,      68,      34,      10,     125,     113,     112,      91,
      12,      34,      12,      70,      71,      62,     126,     116,
      52,     115,      12,      94,      12,      65,     124,     110,
     109,      88,      59,      85,      56,      50,      72,      81,
      68,      18,      79,       9,       8,       7,      45,      26,
      43,      25,      72,      41,      24,      49,      39,      23,
      22,      29,      97,      73,      53,      52,     106,     100,
     103,       1,       0,       0,       0,       0,       0,       0,
       0,       0,      95,      89,      92,      18,       0,       0,
       0,       0,       0,     108,       0,       0,       0,      18,
      18,      18,      18,      18,      18,       0,     109,     118,
     119,       0,     120,     121,       0,     122,     123,       0,
     110,     112,     113,     115,     116,       2,       0,       0,
       0,       0,       0,       0,       0,       0,       0,       0,
       0,       0,       0,       0,       0,       0,       0,       0,
       0,       0,       0,       0,       0,       0,       0,       0,
       0,       0,       0,       0,       0,       0,       0,       0,
      27,       0,       0,       0,       0,       5,       0,      30,
      13,      14,      13,      14,      98,       0,      16,      15,
      16,      15,      13,      14,      13,      14,      84,       0,
      16,      15,      16,      15,
};

int yypact[] = {
     -35,   -1000,     -23,    -229,     -43,   -1000,   -1000,   -1000,
   -1000,   -1000,     -55,     -51,    -243,   -1000,   -1000,   -1000,
   -1000,   -1000,   -1000,   -1000,    -244,    -245,     -23,    -234,
    -238,    -236,    -240,   -1000,   -1000,   -1000,    -246,   -1000,
     -23,   -1000,     -23,   -1000,   -1000,   -1000,     -25,      22,
    -220,      21,    -221,      20,    -222,      19,    -223,   -1000,
     -52,   -1000,   -1000,     -23,     -23,    -247,   -1000,   -1000,
      34,   -1000,   -1000,      32,   -1000,   -1000,      31,   -1000,
   -1000,      30,   -1000,   -1000,     -23,     -88,     -23,   -1000,
     -33,     -28,   -1000,    -252,      27,      25,      24,   -1000,
   -1000,   -1000,   -1000,   -1000,   -1000,     -38,   -1000,   -1000,
      11,   -1000,    -248,       9,   -1000,    -255,       7,   -1000,
    -260,     -23,   -1000,   -1000,   -1000,    -224,   -1000,   -1000,
    -225,   -1000,   -1000,    -226,     -23,     -23,     -23,   -1000,
     -23,     -23,   -1000,     -23,     -23,   -1000,     -23,     -23,
     -23,     -23,     -23,     -23,      14,      13,      12,   -1000,
   -1000,   -1000,
};

int yypgo[] = {
       0,     137,      57,     133,     132,     131,     129,      40,
     128,     127,     126,     124,     123,     121,     120,     119,
     118,     117,     116,     115,     108,     107,     106,     105,
     104,      46,     103,     102,     101,      99,      97,      39,
      95,      94,      93,      87,      86,      44,      85,      84,
      83,      82,      45,      81,      78,      77,      76,
};

int yyr1[] = {
       0,       1,       3,       1,       4,       1,       1,       1,
       1,       1,       1,       2,       2,       8,       7,       9,
       7,      11,       7,      13,       7,      15,       7,       7,
       7,       7,      20,      10,      10,      21,      21,      21,
      22,      24,      12,      12,      23,      23,      26,      27,
      25,      25,      28,      30,      16,      16,      29,      29,
      32,      33,      31,      31,      34,      36,      14,      14,
      35,      35,      38,      39,      37,      37,      17,      17,
      17,      41,      40,      43,      42,      42,      44,      18,
      45,      45,      46,      46,       5,       5,      19,      19,
      19,      19,      19,       6,       6,
};

int yyr2[] = {
       2,       1,       0,       6,       0,       6,       2,       2,
       2,       0,       1,       2,       1,       0,       4,       0,
       4,       0,       4,       0,       4,       0,       4,       1,
       1,       1,       0,       6,       2,       2,       1,       1,
       0,       0,       7,       2,       2,       1,       0,       0,
       6,       3,       0,       0,       7,       2,       2,       1,
       0,       0,       6,       3,       0,       0,       7,       2,
       2,       1,       0,       0,       6,       3,       2,       4,
       2,       0,       3,       0,       3,       1,       0,       5,
       0,       1,       2,       1,       2,       1,       1,       1,
       1,       1,       1,       1,       2,
};

int yychk[] = {
   -1000,      -1,      -2,      40,      44,     256,      -7,     -17,
     -18,     -19,     -40,      91,     123,     259,     260,     266,
     265,      35,      -7,      40,     257,     258,      -8,      -9,
     -11,     -13,     -15,     259,      44,      -6,     266,      93,
     124,      93,     -41,     266,     266,     266,      -2,     -10,
     261,     -12,     263,     -14,     262,     -16,     264,     266,
      -7,     -42,      -7,     -44,      -3,      -4,      41,      41,
     -20,     256,      41,     -22,     256,      41,     -34,     256,
      41,     -28,     256,      93,     -43,     -45,     -46,      -7,
      -2,      -5,     266,      40,      40,      40,      40,     -42,
     125,      -7,      41,      41,     266,     -21,     266,     256,
     -23,     -25,      40,     -35,     -37,      40,     -29,     -31,
      40,      41,     266,      41,     -25,     266,      41,     -37,
     266,      41,     -31,     266,      -2,     -24,     -26,     256,
     -36,     -38,     256,     -30,     -32,     256,      -2,      -2,
      -2,      -2,      -2,      -2,     -27,     -39,     -33,      41,
      41,      41,
};

int yydef[] = {
       9,      -2,       1,      -2,       0,      10,      12,      23,
      24,      25,       0,      65,       0,      78,      79,      80,
      81,      82,      11,      -2,       0,       0,       0,       0,
       0,       0,       0,       6,       7,       8,      83,      62,
       0,      64,       0,      70,       2,       4,       0,       0,
      26,       0,      32,       0,      52,       0,      42,      84,
       0,      66,      -2,      72,       0,       0,      14,      16,
       0,      28,      18,       0,      35,      20,       0,      55,
      22,       0,      45,      63,       0,       0,      73,      75,
       0,       0,      77,       0,       0,       0,       0,      68,
      71,      74,       3,       5,      76,       0,      30,      31,
       0,      37,       0,       0,      57,       0,       0,      47,
       0,       0,      29,      33,      36,      38,      53,      56,
      58,      43,      46,      48,      27,       0,       0,      41,
       0,       0,      61,       0,       0,      51,      34,      39,
      54,      59,      44,      49,       0,       0,       0,      40,
      60,      50,
};

int *yyxi;


/*****************************************************************/
/* PCYACC LALR parser driver routine -- a table driven procedure */
/* for recognizing sentences of a language defined by the        */
/* grammar that PCYACC analyzes. An LALR parsing table is then   */
/* constructed for the grammar and the skeletal parser uses the  */
/* table when performing syntactical analysis on input source    */
/* programs. The actions associated with grammar rules are       */
/* inserted into a switch statement for execution.               */
/*****************************************************************/


#ifndef YYMAXDEPTH
#define YYMAXDEPTH 200
#endif
#ifndef YYREDMAX
#define YYREDMAX 1000
#endif
#define PCYYFLAG -1000
#define WAS0ERR 0
#define WAS1ERR 1
#define WAS2ERR 2
#define WAS3ERR 3
#define yyclearin pcyytoken = -1
#define yyerrok   pcyyerrfl = 0
YYSTYPE yyv[YYMAXDEPTH];     /* value stack */
int pcyyerrct = 0;           /* error count */
int pcyyerrfl = 0;           /* error flag */
int redseq[YYREDMAX];
int redcnt = 0;
int pcyytoken = -1;          /* input token */


yyparse()
{
  int statestack[YYMAXDEPTH]; /* state stack */
  int      j, m;              /* working index */
  YYSTYPE *yypvt;
  int      tmpstate, tmptoken, *yyps, n;
  YYSTYPE *yypv;


  tmpstate = 0;
  pcyytoken = -1;
#ifdef YYDEBUG
  tmptoken = -1;
#endif
  pcyyerrct = 0;
  pcyyerrfl = 0;
  yyps = &statestack[-1];
  yypv = &yyv[-1];


  enstack:    /* push stack */
#ifdef YYDEBUG
    printf("at state %d, next token %d\n", tmpstate, tmptoken);
#endif
    if (++yyps - &statestack[YYMAXDEPTH] > 0) {
      yyerror("pcyacc internal stack overflow");
      return(1);
    }
    *yyps = tmpstate;
    ++yypv;
    *yypv = yyval;


  newstate:
    n = yypact[tmpstate];
    if (n <= PCYYFLAG) goto defaultact; /*  a simple state */


    if (pcyytoken < 0) if ((pcyytoken=yylex()) < 0) pcyytoken = 0;
    if ((n += pcyytoken) < 0 || n >= YYLAST) goto defaultact;


    if (yychk[n=yyact[n]] == pcyytoken) { /* a shift */
#ifdef YYDEBUG
      tmptoken  = pcyytoken;
#endif
      pcyytoken = -1;
      yyval = yylval;
      tmpstate = n;
      if (pcyyerrfl > 0) --pcyyerrfl;
      goto enstack;
    }


  defaultact:


    if ((n=yydef[tmpstate]) == -2) {
      if (pcyytoken < 0) if ((pcyytoken=yylex())<0) pcyytoken = 0;
      for (yyxi=yyexca; (*yyxi!= (-1)) || (yyxi[1]!=tmpstate); yyxi += 2);
      while (*(yyxi+=2) >= 0) if (*yyxi == pcyytoken) break;
      if ((n=yyxi[1]) < 0) { /* an accept action */
        if (yytflag) {
          int ti; int tj;
          yytfilep = fopen(yytfilen, "w");
          if (yytfilep == NULL) {
            fprintf(stderr, "Can't open t file: %s\n", yytfilen);
            return(0);          }
          for (ti=redcnt-1; ti>=0; ti--) {
            tj = svdprd[redseq[ti]];
            while (strcmp(svdnams[tj], "$EOP"))
              fprintf(yytfilep, "%s ", svdnams[tj++]);
            fprintf(yytfilep, "\n");
          }
          fclose(yytfilep);
        }
        return (0);
      }
    }


    if (n == 0) {        /* error situation */
      switch (pcyyerrfl) {
        case WAS0ERR:          /* an error just occurred */
          yyerror("syntax error");
          yyerrlab:
            ++pcyyerrct;
        case WAS1ERR:
        case WAS2ERR:           /* try again */
          pcyyerrfl = 3;
	   /* find a state for a legal shift action */
          while (yyps >= statestack) {
	     n = yypact[*yyps] + YYERRCODE;
	     if (n >= 0 && n < YYLAST && yychk[yyact[n]] == YYERRCODE) {
	       tmpstate = yyact[n];  /* simulate a shift of "error" */
	       goto enstack;
            }
	     n = yypact[*yyps];


	     /* the current yyps has no shift on "error", pop stack */
#ifdef YYDEBUG
            printf("error: pop state %d, recover state %d\n", *yyps, yyps[-1]);
#endif
	     --yyps;
	     --yypv;
	   }


	   yyabort:
            if (yytflag) {
              int ti; int tj;
              yytfilep = fopen(yytfilen, "w");
              if (yytfilep == NULL) {
                fprintf(stderr, "Can't open t file: %s\n", yytfilen);
                return(1);              }
              for (ti=1; ti<redcnt; ti++) {
                tj = svdprd[redseq[ti]];
                while (strcmp(svdnams[tj], "$EOP"))
                  fprintf(yytfilep, "%s ", svdnams[tj++]);
                fprintf(yytfilep, "\n");
              }
              fclose(yytfilep);
            }
	     return(1);


	 case WAS3ERR:  /* clobber input char */
#ifdef YYDEBUG
          printf("error: discard token %d\n", pcyytoken);
#endif
          if (pcyytoken == 0) goto yyabort; /* quit */
	   pcyytoken = -1;
	   goto newstate;      } /* switch */
    } /* if */


    /* reduction, given a production n */
#ifdef YYDEBUG
    printf("reduce with rule %d\n", n);
#endif
    if (yytflag && redcnt<YYREDMAX) redseq[redcnt++] = n;
    yyps -= yyr2[n];
    yypvt = yypv;
    yypv -= yyr2[n];
    yyval = yypv[1];
    m = n;
    /* find next state from goto table */
    n = yyr1[n];
    j = yypgo[n] + *yyps + 1;
    if (j>=YYLAST || yychk[ tmpstate = yyact[j] ] != -n) tmpstate = yyact[yypgo[n]];
    switch (m) { /* actions associated with grammar rules */
      
      case 1:
# line 123 "compiler.Y"
      { return(LAM_EXP); } break;
      case 2:
# line 126 "compiler.Y"
      { oper.sym = yypvt[-0].sym; write_mem(--code, FALSE, SYM, &oper); } break;
      case 3:
# line 129 "compiler.Y"
      { return(LAM_DEF); } break;
      case 4:
# line 132 "compiler.Y"
      { oper.sym = yypvt[-0].sym; write_mem(--code, FALSE, SYM, &oper); } break;
      case 5:
# line 135 "compiler.Y"
      {  write_mem(--code, 0, CLOSE_PAREN, NULL);
               return(LAM_STRUCT);
            } break;
      case 6:
# line 139 "compiler.Y"
      { reds_allowed = yypvt[-0].intval;
              return(LAM_RED);
            } break;
      case 7:
# line 143 "compiler.Y"
      { reds_allowed = -1;
              return(LAM_RED);
            } break;
      case 8:
# line 147 "compiler.Y"
      { return(LAM_COM); } break;
      case 9:
# line 149 "compiler.Y"
      { return(-1); } break;
      case 10:
# line 151 "compiler.Y"
      { yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Parsing failure!");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 13:
# line 167 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 14:
# line 169 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 15:
# line 170 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 16:
# line 172 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 17:
# line 173 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 18:
# line 175 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 19:
# line 176 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 20:
# line 178 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 21:
# line 179 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 22:
# line 181 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 26:
# line 189 "compiler.Y"
      {
      				write_mem(++bindings, 0, 0, NULL);
#ifdef DEBUG_FIND_INDEX
      				if (debug) {
      					foutstring(stdscr, "\n\rEntering LAM, pushing bindings at %p", bindings);
      					wrefresh(stdscr);
      				}
#endif
      			} break;
      case 27:
# line 200 "compiler.Y"
      {
      				while((bindings--)->type != 0);
#ifdef DEBUG_FIND_INDEX
      				if (debug) {
      					foutstring(stdscr, "\n\rExiting LAM, popped bindings to %p", bindings);
      					wrefresh(stdscr);
      				}
#endif
      			} break;
      case 28:
# line 210 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad Abstraction!");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 29:
# line 222 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(++bindings, FALSE, LAMBDA, &oper);       
              write_mem(--code, BINDER, LAMBDA, &oper); 
            } break;
      case 30:
# line 227 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(++bindings, FALSE, LAMBDA, &oper);             
              write_mem(--code, BINDER, LAMBDA, &oper); 
            } break;
      case 31:
# line 232 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad binding list! ");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 32:
# line 246 "compiler.Y"
      {
             write_mem(++bindings, 0, 0, NULL);
             oper.addr = bindings-1;
             write_mem(++bindings, 0, MARKER, &oper);
           } break;
      case 33:
# line 252 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
             --bindings;
           } break;
      case 34:
# line 256 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 35:
# line 260 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Let expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 38:
# line 278 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LET, &oper);
              *(bindings+1) = *bindings;
              *bindings++ = *code;
              write_mem(--code, 0, OPEN_PAREN, NULL);
            } break;
      case 39:
# line 285 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 41:
# line 288 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let!",
                     yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 42:
# line 304 "compiler.Y"
      {
             write_mem(++bindings, 0, 0, NULL);
             oper.addr = code-1;
             write_mem(++bindings, 0, STOP, &oper);
           } break;
      case 43:
# line 310 "compiler.Y"
      {
             node *temp = bindings->op.addr;
             reparse_letrec(bindings->op.addr, code, bindings-1);
#ifdef DEBUG_LETREC
             if (debug) {
               outstring(stdscr, "\n\rREPARSING A LETREC EXPRESSION:");
               wrefresh(stdscr);
               print_mem(stdscr, code, temp);
             }
#endif       
             write_mem(--code, 0, OPEN_PAREN, NULL);
             --bindings;
           } break;
      case 44:
# line 324 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 45:
# line 328 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Letrec expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 48:
# line 346 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LETREC, &oper);
              *(bindings+1) = *bindings;
              bindings->type = LETREC; bindings->op.addr = code;
              ++bindings;
              write_mem(--code, 0, OPEN_PAREN, NULL);
            } break;
      case 49:
# line 354 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 51:
# line 357 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Letrec!",
                  yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 52:
# line 371 "compiler.Y"
      { write_mem(++bindings, 0, 0, NULL); } break;
      case 53:
# line 373 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 54:
# line 375 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 55:
# line 379 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Let* expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 58:
# line 397 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LETSTAR, &oper);
              write_mem(--code, 0, OPEN_PAREN, NULL); 
            } break;
      case 59:
# line 402 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); 
              oper.sym = yypvt[-2].sym;
              write_mem(++bindings, 0, LAMBDA, &oper);
            } break;
      case 61:
# line 408 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let*!",
                     yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 62:
# line 421 "compiler.Y"
      {  oper.sym = nil;
                  write_mem(--code, APPLY, oper.sym->typ, &oper);
                  while (list_depth-- > 0) {
                     write_mem(--code, 0, CLOSE_PAREN, NULL);
                     bindings--;
                  }
#ifdef DEBUG_FIND_INDEX
      				if (debug) {
      					foutstring(stdscr, "\n\rExiting LIST, popped bindings to %p", bindings);
      					wrefresh(stdscr);
      				}
#endif
                  list_depth = (stack--)->intval;
               } break;
      case 63:
# line 439 "compiler.Y"
      {
      				while (list_depth-- > 0) {
                  	write_mem(--code, 0, CLOSE_PAREN, NULL);
                     bindings--;
                  }
#ifdef DEBUG_FIND_INDEX
      				if (debug) {
      					foutstring(stdscr, "\n\rExiting LIST, popped bindings to %p", bindings);
      					wrefresh(stdscr);
      				}
#endif
                  list_depth = (stack--)->intval;
               } break;
      case 64:
# line 454 "compiler.Y"
      {  oper.sym = nil;
               write_mem(--code, APPLY, oper.sym->typ, &oper);
            } break;
      case 65:
# line 462 "compiler.Y"
      {
#ifdef DEBUG_FIND_INDEX
      				if (debug) {
      					foutstring(stdscr, "\n\rEntering LIST, bindings at %p", bindings);
      					wrefresh(stdscr);
      				}
#endif
      				(++stack)->intval = list_depth;
                  list_depth = 1;
                  write_mem(--code, 0, OPEN_PAREN, NULL);
                  oper.sym = pair;
                  write_mem(--code, PAIR, LAMBDA, &oper);
                  write_mem(++bindings, 0, LAMBDA, NULL);
                  oper.index = 0;
                  write_mem(--code, HEAD, VAR, &oper);
               } break;
      case 67:
# line 482 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
                  oper.sym = pair;
                  write_mem(--code, PAIR, LAMBDA, &oper);
                  write_mem(++bindings, 0, LAMBDA, NULL);
                  oper.index = 0;
                  write_mem(--code, HEAD, VAR, &oper);
                  ++list_depth;
                 } break;
      case 70:
# line 498 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
                 oper.sym = yypvt[-0].sym;
                 write_mem(--code, PAIR, LAMBDA, &oper);
                 write_mem(++bindings, 0, LAMBDA, NULL);
                 oper.index = 0;
                 write_mem(--code, HEAD, VAR, &oper);
               } break;
      case 71:
# line 507 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
                 bindings--;
               } break;
      case 76:
# line 524 "compiler.Y"
      {  oper.sym = yypvt[-0].sym; write_mem(--code, 0, SYM, &oper); } break;
      case 77:
# line 526 "compiler.Y"
      {  oper.sym = yypvt[-0].sym; write_mem(--code, 0, SYM, &oper); } break;
      case 78:
# line 531 "compiler.Y"
      { oper.intval = yypvt[-0].intval; write_mem(--code, APPLY, INT, &oper); } break;
      case 79:
# line 533 "compiler.Y"
      { oper.floval = yypvt[-0].floval; write_mem(--code, APPLY, FLOAT, &oper); } break;
      case 80:
# line 535 "compiler.Y"
      { int index;
              index = find_index(yypvt[-0].sym, bindings, 0);
              if (index >= 0) {
                  oper.index = index;
                  write_mem(--code, APPLY, VAR, &oper);
              }
              else 
                 { oper.sym = yypvt[-0].sym; write_mem(--code, APPLY, yypvt[-0].sym->typ, &oper); }
            } break;
      case 81:
# line 545 "compiler.Y"
      { int index;
              index = find_index(yypvt[-0].sym, bindings, protect_marks);
              if (index >= 0) {
                  oper.index = index;
                  write_mem(--code, APPLY, VAR, &oper);
              }
              else if (index == -1)
                 { oper.sym = yypvt[-0].sym; write_mem(--code, APPLY, yypvt[-0].sym->typ, &oper); }
              else
                 { protected *protected_alloc();
                   oper.sym = (symbol *) protected_alloc(yypvt[-0].sym, -1 - index);
                   write_mem(--code, APPLY, PROT, &oper);
                 }
            } break;
      case 82:
# line 560 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad usage of binding protector '#' !");
              wrefresh(stdscr);
              return(1);
            } break;
      case 83:
# line 573 "compiler.Y"
      { command = yypvt[-0].sym; comm_switch = NULL; } break;
      case 84:
# line 575 "compiler.Y"
      { command = yypvt[-1].sym; comm_switch = yypvt[-0].sym; } break;    }
    goto enstack;
}
