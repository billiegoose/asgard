
# line 12 "compiler.Y"
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
extern symbol  *string;
extern unsigned long reds_allowed;
extern int  expr_type;
extern node *fs;
extern union control *stack;
extern int debug;
extern char outbuffer[];

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

# line 97 "compiler.Y"
typedef union  {
   char  charval;
   char  *strval;
   long intval;
   float floval;
   symbol *sym;
} YYSTYPE;
#define YYSUNION /* %union occurred */
#define DEFINITION 257
#define DEFSTRUCT 258
#define RDEFINE 259
#define CHARACTER 260
#define STRING 261
#define INTEGER 262
#define FLONUM 263
#define LAM 264
#define LETS 265
#define LETT 266
#define LETR 267
#define PROTECTED 268
#define SYMBOL 269
#define EOS 270
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
   if (oper != NULL) addr->op   = *oper;
}




   
/* 
/* Lexical Analyzer Routines
*/

int delimiter(c)
char c;
{ return((c == '(' || c == ')' || c == '}' || c == '{' || c == '\0' ||
          c == ']' || c == '[' || c == ',' || c == ';' || c == '|'  ||
          c == '\'' || c == '\"')); }

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


/* TRANSLATE_CHAR
/* Decodes backslash-escaped characters and returns it's ascii value,
*/

char translate_char(c)
char c;
{
   switch (c) {
      case 'n': return('\n');
      case 't': return('\t');
      case 'b': return('\b');
      case 'r': return('\r');
      case 'f': return('\f');
      case '\'': return('\'');
      case '\"': return('\"');
      case '\\': return('\\');
      default: return(c);
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

   if (ch == '\'') {             /* character constant */
      ch = nextchar();
      if (ch == '\\') ch = translate_char(nextchar());
      yylval.charval = ch;
      ch = nextchar();
      if (ch != '\'') return(ch);
      else return(CHARACTER);
   }      


   if (ch == '\"') {          /* character string */
      char *str = &outbuffer[0];  /* borrow the output buffer for storage */
      ch = nextchar();
      if (ch == '\"') {
         unnextchar (ch);
         return ('\"');
      }
      while (ch != '\"') {
         if (ch == '\\') ch = translate_char(nextchar());
         *str++ = ch;
         ch = nextchar();
      }
      *str = '\0';
      yylval.strval = &outbuffer[0];
      return(STRING);
   }


       
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
      else if (stricmp(lex_buffer, "RDEFINE") == 0) return (RDEFINE);
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

   while (addr->type != STOP) {
      if (addr->type == MARKER)
         addr = addr->op.addr;
      else {
         if (((addr->type != LETREC) && (addr->op.sym == sym)) ||
             ((addr->type == LETREC) && (addr->op.addr->op.sym == sym))) {
            if (protects == 0) {
               return(index);
            }
            else  --protects;
         }
         if (addr->type != 0) ++index;
         --addr;
      }
   }
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
  264, 17,
  265, 21,
  266, 19,
  267, 23,
  -2, 15,
  -1, 23,
  264, 17,
  265, 21,
  266, 19,
  267, 23,
  -2, 15,
  -1, 57,
  93, 72,
  124, 72,
  -2, 70,
  0,
};

#define YYNPROD 91
#define YYLAST 265

int yyact[] = {
      13,      21,     117,     107,      93,      33,       3,      97,
     114,     111,       4,      13,      21,      83,      54,      13,
      21,      23,      92,      44,      96,      23,      91,      43,
      42,      13,      21,      41,      53,      13,      21,      23,
      62,      49,      51,      23,      47,      24,      26,      25,
     127,     124,     121,      74,      71,      68,      65,       6,
      89,      36,      22,     102,     105,      99,      56,     106,
     115,      12,      75,     139,      38,     103,     112,     100,
     109,     138,     137,      72,      12,      69,       6,      66,
      12,      63,       2,     106,     103,     100,      87,      86,
      37,      85,      12,      84,      40,      55,      12,      57,
      78,      15,      77,      58,      76,      22,      39,      11,
     135,     123,     122,     101,      15,      70,      45,      39,
      15,      78,      79,     136,     126,     125,     104,      73,
     134,     120,      15,     119,      98,      67,      15,      95,
      59,      64,      10,       9,      57,       8,      90,      76,
      22,      22,       7,      88,      52,      31,      80,      81,
      50,      30,      80,      48,      29,      46,      28,      56,
      27,      34,      82,      61,      60,      59,       1,       0,
     110,     113,       0,      60,     107,     116,       0,       0,
       0,       0,       0,       0,      99,     102,      22,       0,
       0,     105,       0,       0,       0,       0,       0,       0,
      22,      22,      22,      22,      22,      22,     118,       0,
       0,       0,       0,       0,       0,       0,       0,       0,
       0,     119,     128,     129,       0,     130,     131,       0,
     132,     133,       0,     120,     122,     123,     125,     126,
       2,       0,       0,       0,       0,       0,       0,       0,
       0,       0,       0,       0,       0,       0,       5,      32,
       0,       0,      16,      14,      17,      18,      35,     108,
      94,       0,      20,      19,       0,      16,      14,      17,
      18,      16,      14,      17,      18,      20,      19,       0,
       0,      20,      19,      16,      14,      17,      18,      16,
      14,      17,      18,      20,      19,       0,       0,      20,
      19,
};

int yypact[] = {
     -34,   -1000,      -5,    -220,     -39,   -1000,   -1000,   -1000,
   -1000,   -1000,   -1000,     -44,     -33,      50,   -1000,    -242,
   -1000,   -1000,   -1000,   -1000,   -1000,   -1000,   -1000,   -1000,
    -245,    -246,    -250,      -5,    -228,    -233,    -231,    -239,
   -1000,   -1000,   -1000,    -255,   -1000,      -5,   -1000,      -5,
   -1000,   -1000,   -1000,   -1000,   -1000,      -9,      32,    -210,
      30,    -211,      28,    -212,      26,    -213,   -1000,     -35,
   -1000,   -1000,      -5,      -5,      -5,    -256,   -1000,   -1000,
      43,   -1000,   -1000,      41,   -1000,   -1000,      39,   -1000,
   -1000,      38,   -1000,   -1000,      -5,     -77,      -5,   -1000,
     -19,     -23,     -37,   -1000,    -249,      37,      36,      35,
   -1000,   -1000,   -1000,   -1000,   -1000,   -1000,   -1000,     -38,
   -1000,   -1000,      23,   -1000,    -260,      21,   -1000,    -261,
      15,   -1000,    -267,      -5,   -1000,   -1000,   -1000,    -214,
   -1000,   -1000,    -215,   -1000,   -1000,    -216,      -5,      -5,
      -5,   -1000,      -5,      -5,   -1000,      -5,      -5,   -1000,
      -5,      -5,      -5,      -5,      -5,      -5,      25,      24,
      18,   -1000,   -1000,   -1000,
};

int yypgo[] = {
       0,     150,      74,     149,     148,     147,     146,     145,
      47,     144,     142,     141,     140,     139,     137,     136,
     133,     132,     130,     125,     123,     122,     121,     119,
     117,     116,     115,      53,     113,     112,     111,     110,
     109,      52,     108,     107,     101,      99,      98,      51,
      97,      96,      95,      94,      54,      92,      91,      90,
      88,
};

int yyr1[] = {
       0,       1,       3,       1,       4,       1,       5,       1,
       1,       1,       1,       1,       1,       2,       2,       9,
       8,      10,       8,      12,       8,      14,       8,      16,
       8,       8,       8,       8,       8,      22,      11,      11,
      23,      23,      23,      24,      26,      13,      13,      25,
      25,      28,      29,      27,      27,      30,      32,      17,
      17,      31,      31,      34,      35,      33,      33,      36,
      38,      15,      15,      37,      37,      40,      41,      39,
      39,      18,      18,      18,      43,      42,      45,      44,
      44,      19,      19,      46,      20,      47,      47,      48,
      48,       6,       6,      21,      21,      21,      21,      21,
      21,       7,       7,
};

int yyr2[] = {
       2,       1,       0,       6,       0,       6,       0,       6,
       2,       2,       2,       0,       1,       2,       1,       0,
       4,       0,       4,       0,       4,       0,       4,       0,
       4,       1,       1,       1,       1,       0,       6,       2,
       2,       1,       1,       0,       0,       7,       2,       2,
       1,       0,       0,       6,       3,       0,       0,       7,
       2,       2,       1,       0,       0,       6,       3,       0,
       0,       7,       2,       2,       1,       0,       0,       6,
       3,       2,       4,       2,       0,       3,       0,       3,
       1,       2,       1,       0,       5,       0,       1,       2,
       1,       2,       1,       1,       1,       1,       1,       1,
       1,       1,       2,
};

int yychk[] = {
   -1000,      -1,      -2,      40,      44,     256,      -8,     -18,
     -19,     -20,     -21,     -42,      91,      34,     261,     123,
     260,     262,     263,     269,     268,      35,      -8,      40,
     257,     259,     258,      -9,     -10,     -12,     -14,     -16,
     262,      44,      -7,     269,      93,     124,      93,     -43,
      34,     269,     269,     269,     269,      -2,     -11,     264,
     -13,     266,     -15,     265,     -17,     267,     269,      -8,
     -44,      -8,     -46,      -3,      -4,      -5,      41,      41,
     -22,     256,      41,     -24,     256,      41,     -36,     256,
      41,     -30,     256,      93,     -45,     -47,     -48,      -8,
      -2,      -2,      -6,     269,      40,      40,      40,      40,
     -44,     125,      -8,      41,      41,      41,     269,     -23,
     269,     256,     -25,     -27,      40,     -37,     -39,      40,
     -31,     -33,      40,      41,     269,      41,     -27,     269,
      41,     -39,     269,      41,     -33,     269,      -2,     -26,
     -28,     256,     -38,     -40,     256,     -32,     -34,     256,
      -2,      -2,      -2,      -2,      -2,      -2,     -29,     -41,
     -35,      41,      41,      41,
};

int yydef[] = {
      11,      -2,       1,      -2,       0,      12,      14,      25,
      26,      27,      28,       0,      68,       0,      74,       0,
      83,      84,      85,      86,      87,      88,      13,      -2,
       0,       0,       0,       0,       0,       0,       0,       0,
       8,       9,      10,      89,      65,       0,      67,       0,
      73,      75,       2,       4,       6,       0,       0,      29,
       0,      35,       0,      55,       0,      45,      90,       0,
      69,      -2,      77,       0,       0,       0,      16,      18,
       0,      31,      20,       0,      38,      22,       0,      58,
      24,       0,      48,      66,       0,       0,      78,      80,
       0,       0,       0,      82,       0,       0,       0,       0,
      71,      76,      79,       3,       5,       7,      81,       0,
      33,      34,       0,      40,       0,       0,      60,       0,
       0,      50,       0,       0,      32,      36,      39,      41,
      56,      59,      61,      46,      49,      51,      30,       0,
       0,      44,       0,       0,      64,       0,       0,      54,
      37,      42,      57,      62,      47,      52,       0,       0,
       0,      43,      63,      53,
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
# line 124 "compiler.Y"
      { return(LAM_EXP); } break;
      case 2:
# line 127 "compiler.Y"
      { oper.sym = yypvt[-0].sym; write_mem(--code, FALSE, SYM, &oper); } break;
      case 3:
# line 130 "compiler.Y"
      { return(LAM_DEF); } break;
      case 4:
# line 133 "compiler.Y"
      { oper.sym = yypvt[-0].sym; write_mem(--code, FALSE, SYM, &oper);} break;
      case 5:
# line 136 "compiler.Y"
      { return(LAM_RDEF); } break;
      case 6:
# line 139 "compiler.Y"
      { oper.sym = yypvt[-0].sym; write_mem(--code, FALSE, SYM, &oper); } break;
      case 7:
# line 142 "compiler.Y"
      {  write_mem(--code, 0, CLOSE_PAREN, NULL);
               return(LAM_STRUCT);
            } break;
      case 8:
# line 146 "compiler.Y"
      { reds_allowed = yypvt[-0].intval;
              return(LAM_RED);
            } break;
      case 9:
# line 150 "compiler.Y"
      { reds_allowed = -1;
              return(LAM_RED);
            } break;
      case 10:
# line 154 "compiler.Y"
      { return(LAM_COM); } break;
      case 11:
# line 156 "compiler.Y"
      { return(-1); } break;
      case 12:
# line 158 "compiler.Y"
      { yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Parsing failure!");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 15:
# line 174 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 16:
# line 176 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 17:
# line 177 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 18:
# line 179 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 19:
# line 180 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 20:
# line 182 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 21:
# line 183 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 22:
# line 185 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 23:
# line 186 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 24:
# line 188 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 29:
# line 196 "compiler.Y"
      { write_mem(++bindings, 0, 0, NULL); } break;
      case 30:
# line 198 "compiler.Y"
      { while((bindings--)->type != 0); } break;
      case 31:
# line 200 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad Abstraction!");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 32:
# line 212 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(++bindings, FALSE, LAMBDA, &oper);       
              write_mem(--code, BINDER, LAMBDA, &oper); 
            } break;
      case 33:
# line 217 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(++bindings, FALSE, LAMBDA, &oper);             
              write_mem(--code, BINDER, LAMBDA, &oper); 
            } break;
      case 34:
# line 222 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad binding list! ");
              wrefresh(stdscr);
              return(-1);
            } break;
      case 35:
# line 236 "compiler.Y"
      {
             write_mem(++bindings, 0, 0, NULL);
             oper.addr = bindings-1;
             write_mem(++bindings, 0, MARKER, &oper);
           } break;
      case 36:
# line 242 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
             --bindings;
           } break;
      case 37:
# line 246 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 38:
# line 250 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Let expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 41:
# line 268 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LET, &oper);
              *(bindings+1) = *bindings;
              *bindings++ = *code;
              write_mem(--code, 0, OPEN_PAREN, NULL);
            } break;
      case 42:
# line 275 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 44:
# line 278 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let!",
                     yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 45:
# line 294 "compiler.Y"
      {
             write_mem(++bindings, 0, 0, NULL);
             oper.addr = code-1;
             write_mem(++bindings, 0, STOP, &oper);
           } break;
      case 46:
# line 300 "compiler.Y"
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
      case 47:
# line 314 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 48:
# line 318 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Letrec expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 51:
# line 336 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LETREC, &oper);
              *(bindings+1) = *bindings;
              bindings->type = LETREC; bindings->op.addr = code;
              ++bindings;
              write_mem(--code, 0, OPEN_PAREN, NULL);
            } break;
      case 52:
# line 344 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); } break;
      case 54:
# line 347 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Letrec!",
                  yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 55:
# line 361 "compiler.Y"
      { write_mem(++bindings, 0, 0, NULL); } break;
      case 56:
# line 363 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL); } break;
      case 57:
# line 365 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
             while((bindings--)->type != 0);
           } break;
      case 58:
# line 369 "compiler.Y"
      { yyclearin; yyerrok;
             if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
             else outstring_ns(stdscr, "\n\r");
             outstring_ns(stdscr, "Parse Error: Bad Let* expression!");
             wrefresh(stdscr);
             return(-1);
           } break;
      case 61:
# line 387 "compiler.Y"
      { oper.sym = yypvt[-0].sym;
              write_mem(--code, BINDER, LETSTAR, &oper);
              write_mem(--code, 0, OPEN_PAREN, NULL); 
            } break;
      case 62:
# line 392 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL); 
              oper.sym = yypvt[-2].sym;
              write_mem(++bindings, 0, LAMBDA, &oper);
            } break;
      case 64:
# line 398 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let*!",
                     yypvt[-1].sym->print_name);
              wrefresh(stdscr);
              return(-1);
            } break;
      case 65:
# line 411 "compiler.Y"
      {  oper.sym = nil;
                  write_mem(--code, APPLY, oper.sym->typ, &oper);
                  while (list_depth-- > 0) {
                     write_mem(--code, 0, CLOSE_PAREN, NULL);
                     bindings--;
                  }
                  list_depth = (stack--)->intval;
               } break;
      case 66:
# line 422 "compiler.Y"
      {  while (list_depth-- > 0) {
                        write_mem(--code, 0, CLOSE_PAREN, NULL);
                        bindings--;
                     }
                     list_depth = (stack--)->intval;
                  } break;
      case 67:
# line 430 "compiler.Y"
      {  oper.sym = nil;
               write_mem(--code, APPLY, oper.sym->typ, &oper);
            } break;
      case 68:
# line 437 "compiler.Y"
      {  (++stack)->intval = list_depth;
                  list_depth = 1;
                  write_mem(--code, 0, OPEN_PAREN, NULL);
                  oper.sym = pair;
                  write_mem(--code, PAIR, LAMBDA, &oper);
                  write_mem(++bindings, 0, LAMBDA, NULL);
                  oper.index = 0;
                  write_mem(--code, HEAD, VAR, &oper);
               } break;
      case 70:
# line 450 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
                  oper.sym = pair;
                  write_mem(--code, PAIR, LAMBDA, &oper);
                  write_mem(++bindings, 0, LAMBDA, NULL);
                  oper.index = 0;
                  write_mem(--code, HEAD, VAR, &oper);
                  ++list_depth;
                 } break;
      case 73:
# line 465 "compiler.Y"
      { oper.sym = nil; write_mem(--code, APPLY, SYM, &oper);} break;
      case 74:
# line 467 "compiler.Y"
      {
               char *str = yypvt[-0].strval;
               (++stack)->intval = list_depth;
               list_depth = 0;
               while (*str != '\0') {
                  write_mem(--code, 0, OPEN_PAREN, NULL);
                  oper.sym = string;
                  write_mem(--code, PAIR, LAMBDA, &oper);
                  write_mem(++bindings, 0, LAMBDA, NULL);
                  oper.index = 0;
                  write_mem(--code, HEAD, VAR, &oper);
                  oper.charval = *str;
                  write_mem(--code, APPLY, CHARAC, &oper);
                  ++list_depth;
                  ++str;
               }
               oper.sym = nil;
               write_mem(--code, APPLY, oper.sym->typ, &oper);
               while (list_depth-- > 0) {
                  write_mem(--code, 0, CLOSE_PAREN, NULL);
                  bindings--;
               }
               list_depth = (stack--)->intval;
            } break;
      case 75:
# line 496 "compiler.Y"
      { write_mem(--code, 0, OPEN_PAREN, NULL);
                 oper.sym = yypvt[-0].sym;
                 write_mem(--code, PAIR, LAMBDA, &oper);
                 write_mem(++bindings, 0, LAMBDA, NULL);
                 oper.index = 0;
                 write_mem(--code, HEAD, VAR, &oper);
               } break;
      case 76:
# line 505 "compiler.Y"
      { write_mem(--code, 0, CLOSE_PAREN, NULL);
                 bindings--;
               } break;
      case 81:
# line 522 "compiler.Y"
      {  oper.sym = yypvt[-0].sym; write_mem(--code, 0, SYM, &oper); } break;
      case 82:
# line 524 "compiler.Y"
      {  oper.sym = yypvt[-0].sym; write_mem(--code, 0, SYM, &oper); } break;
      case 83:
# line 529 "compiler.Y"
      { oper.charval = yypvt[-0].charval; write_mem(--code, APPLY, CHARAC, &oper); } break;
      case 84:
# line 531 "compiler.Y"
      { oper.intval = yypvt[-0].intval; write_mem(--code, APPLY, INT, &oper); } break;
      case 85:
# line 533 "compiler.Y"
      { oper.floval = yypvt[-0].floval; write_mem(--code, APPLY, FLOAT, &oper); } break;
      case 86:
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
      case 87:
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
      case 88:
# line 560 "compiler.Y"
      { yyclearin; yyerrok;
              if (source == FILE_IO)
                foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
              else outstring_ns(stdscr, "\n\r");
              outstring_ns(stdscr, "Parse Error: Bad usage of binding protector '#' !");
              wrefresh(stdscr);
              return(1);
            } break;
      case 89:
# line 573 "compiler.Y"
      { command = yypvt[-0].sym; comm_switch = NULL; } break;
      case 90:
# line 575 "compiler.Y"
      { command = yypvt[-1].sym; comm_switch = yypvt[-0].sym; } break;    }
    goto enstack;
}
