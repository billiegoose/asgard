/* PCYACC Generated Parser-Compiler for the Head Order Reduction System
/* Mike Hilton, 10 Jan 1990
/*
/*
/* The compiler calls YYPARSE to transform the expression string into a 
/* token string which starts at location HIGH and continues downward in
/* memory.  The token string is then transformed into a graph rooted at
/* location DEST by BUILD_GRAPH.
*/

%{
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
%}

/* YACC section */

%union {
   char  charval;
   char  *strval;
   long intval;
   float floval;
   symbol *sym;
}

%token DEFINITION DEFSTRUCT RDEFINE
%token CHARACTER STRING
%token INTEGER
%token FLONUM
%token LAM LETS LETT LETR
%token PROTECTED
%token SYMBOL
%token EOS

%type <charval> CHARACTER
%type <strval> STRING
%type <intval> INTEGER
%type <floval> FLONUM
%type <sym> SYMBOL PROTECTED

%start Expr
%%
Expr : 
     Exp 
      { return(LAM_EXP); }
   | '(' 
      DEFINITION 
      SYMBOL      { oper.sym = $3; write_mem(--code, FALSE, SYM, &oper); }
      Exp 
     ')' 
      { return(LAM_DEF); }
   | '('
      RDEFINE
      SYMBOL      { oper.sym = $3; write_mem(--code, FALSE, SYM, &oper);}
      Exp
      ')'
      { return(LAM_RDEF); }
   | '('
      DEFSTRUCT
      SYMBOL      { oper.sym = $3; write_mem(--code, FALSE, SYM, &oper); }
      Symbols
     ')' 
      {  write_mem(--code, 0, CLOSE_PAREN, NULL);
         return(LAM_STRUCT);
      }
   | ',' INTEGER 
      { reds_allowed = $2;
        return(LAM_RED);
      }
   | ',' ',' 
      { reds_allowed = -1;
        return(LAM_RED);
      }
   | ',' Command /* EOS */
     { return(LAM_COM); }
   | 
      { return(-1); }
   | error
      { yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        outstring_ns(stdscr, "Parse Error: Parsing failure!");
        wrefresh(stdscr);
        return(-1);
      }
   ;

Exp :
     Exp Exp1
   | Exp1
   ;

Exp1 :
     '('    { write_mem(--code, 0, OPEN_PAREN, NULL); }
      Exp   
     ')'    { write_mem(--code, 0, CLOSE_PAREN, NULL); }
   | '('    { write_mem(--code, 0, OPEN_PAREN, NULL); }
      Abstraction
     ')'    { write_mem(--code, 0, CLOSE_PAREN, NULL); }
   | '('    { write_mem(--code, 0, OPEN_PAREN, NULL); }
      Let
     ')'    { write_mem(--code, 0, CLOSE_PAREN, NULL); }
   | '('    { write_mem(--code, 0, OPEN_PAREN, NULL); }
      Letstar
     ')'    { write_mem(--code, 0, CLOSE_PAREN, NULL); }
   | '('    { write_mem(--code, 0, OPEN_PAREN, NULL); }
      Letrec
     ')'    { write_mem(--code, 0, CLOSE_PAREN, NULL); }
   | List
   | String
   | Structure
   | Constant
   ;

Abstraction :
      LAM            { write_mem(++bindings, 0, 0, NULL); }
      '(' Bindings ')'
      Exp            { while((bindings--)->type != 0); }
   |  LAM error
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        outstring_ns(stdscr, "Parse Error: Bad Abstraction!");
        wrefresh(stdscr);
        return(-1);
      }
   ;

Bindings :
     Bindings SYMBOL
      { oper.sym = $2;
        write_mem(++bindings, FALSE, LAMBDA, &oper);       
        write_mem(--code, BINDER, LAMBDA, &oper); 
      }
   | SYMBOL
      { oper.sym = $1;
        write_mem(++bindings, FALSE, LAMBDA, &oper);             
        write_mem(--code, BINDER, LAMBDA, &oper); 
      }
   | error 
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        outstring_ns(stdscr, "Parse Error: Bad binding list! ");
        wrefresh(stdscr);
        return(-1);
      }
   ;


   
Let:
     LETT
     {
       write_mem(++bindings, 0, 0, NULL);
       oper.addr = bindings-1;
       write_mem(++bindings, 0, MARKER, &oper);
     }
     '(' Let_bindings ')'
     { write_mem(--code, 0, OPEN_PAREN, NULL);
       --bindings;
     }
     Exp       
     { write_mem(--code, 0, CLOSE_PAREN, NULL);
       while((bindings--)->type != 0);
     }
   | LETT error
     { yyclearin; yyerrok;
       if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
       else outstring_ns(stdscr, "\n\r");
       outstring_ns(stdscr, "Parse Error: Bad Let expression!");
       wrefresh(stdscr);
       return(-1);
     }
   ;

Let_bindings:
     Let_bindings Let_binding
   | Let_binding
   ;

Let_binding:
     '('
      SYMBOL   
      { oper.sym = $2;
        write_mem(--code, BINDER, LET, &oper);
        *(bindings+1) = *bindings;
        *bindings++ = *code;
        write_mem(--code, 0, OPEN_PAREN, NULL);
      }
      Exp
      { write_mem(--code, 0, CLOSE_PAREN, NULL); }
     ')'
   | '(' SYMBOL error
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let!",
               $2->print_name);
        wrefresh(stdscr);
        return(-1);
      }
   ;



      
Letrec:
     LETR
     {
       write_mem(++bindings, 0, 0, NULL);
       oper.addr = code-1;
       write_mem(++bindings, 0, STOP, &oper);
     }
     '(' Letrec_bindings ')'
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
     }
     Exp       
     { write_mem(--code, 0, CLOSE_PAREN, NULL);
       while((bindings--)->type != 0);
     }
   | LETR error
     { yyclearin; yyerrok;
       if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
       else outstring_ns(stdscr, "\n\r");
       outstring_ns(stdscr, "Parse Error: Bad Letrec expression!");
       wrefresh(stdscr);
       return(-1);
     }
   ;

Letrec_bindings:
     Letrec_bindings Letrec_binding
   | Letrec_binding
   ;

Letrec_binding:
     '('
      SYMBOL   
      { oper.sym = $2;
        write_mem(--code, BINDER, LETREC, &oper);
        *(bindings+1) = *bindings;
        bindings->type = LETREC; bindings->op.addr = code;
        ++bindings;
        write_mem(--code, 0, OPEN_PAREN, NULL);
      }
      Exp
      { write_mem(--code, 0, CLOSE_PAREN, NULL); }
     ')'
   | '(' SYMBOL error
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Letrec!",
            $2->print_name);
        wrefresh(stdscr);
        return(-1);
      }
   ;
   
   
Letstar:
     LETS
     { write_mem(++bindings, 0, 0, NULL); }    
     '(' Letstar_bindings ')'
     { write_mem(--code, 0, OPEN_PAREN, NULL); }
     Exp       
     { write_mem(--code, 0, CLOSE_PAREN, NULL);
       while((bindings--)->type != 0);
     }
   | LETS error
     { yyclearin; yyerrok;
       if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
       else outstring_ns(stdscr, "\n\r");
       outstring_ns(stdscr, "Parse Error: Bad Let* expression!");
       wrefresh(stdscr);
       return(-1);
     }
   ;

Letstar_bindings:
     Letstar_bindings Letstar_binding
   | Letstar_binding
   ;

Letstar_binding:
     '('
      SYMBOL   
      { oper.sym = $2;
        write_mem(--code, BINDER, LETSTAR, &oper);
        write_mem(--code, 0, OPEN_PAREN, NULL); 
      }
      Exp
      { write_mem(--code, 0, CLOSE_PAREN, NULL); 
        oper.sym = $2;
        write_mem(++bindings, 0, LAMBDA, &oper);
      }
     ')'
   | '(' SYMBOL error
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        foutstring_ns(stdscr, "Parse Error:  Bad binding for %s in Let*!",
               $2->print_name);
        wrefresh(stdscr);
        return(-1);
      }
   ;

List:
     Listhead
     ']' {  oper.sym = nil;
            write_mem(--code, APPLY, oper.sym->typ, &oper);
            while (list_depth-- > 0) {
               write_mem(--code, 0, CLOSE_PAREN, NULL);
               bindings--;
            }
            list_depth = (stack--)->intval;
         }
     | Listhead
      '|'
      Exp1
      ']'   {  while (list_depth-- > 0) {
                  write_mem(--code, 0, CLOSE_PAREN, NULL);
                  bindings--;
               }
               list_depth = (stack--)->intval;
            } 

   | '[' ']'
      {  oper.sym = nil;
         write_mem(--code, APPLY, oper.sym->typ, &oper);
      }
   ;


Listhead:
     '[' {  (++stack)->intval = list_depth;
            list_depth = 1;
            write_mem(--code, 0, OPEN_PAREN, NULL);
            oper.sym = pair;
            write_mem(--code, PAIR, LAMBDA, &oper);
            write_mem(++bindings, 0, LAMBDA, NULL);
            oper.index = 0;
            write_mem(--code, HEAD, VAR, &oper);
         }
      Listelems
   ;
   
Listelems:
     Exp1 { write_mem(--code, 0, OPEN_PAREN, NULL);
            oper.sym = pair;
            write_mem(--code, PAIR, LAMBDA, &oper);
            write_mem(++bindings, 0, LAMBDA, NULL);
            oper.index = 0;
            write_mem(--code, HEAD, VAR, &oper);
            ++list_depth;
           }
     Listelems 
   | Exp1
   ;


String:
     '\"' '\"'
      { oper.sym = nil; write_mem(--code, APPLY, SYM, &oper);}
   | STRING
      {
         char *str = $1;
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
      }
   ;
   
Structure:
     '{' 
     SYMBOL
         { write_mem(--code, 0, OPEN_PAREN, NULL);
           oper.sym = $2;
           write_mem(--code, PAIR, LAMBDA, &oper);
           write_mem(++bindings, 0, LAMBDA, NULL);
           oper.index = 0;
           write_mem(--code, HEAD, VAR, &oper);
         }
     Struct_elements
     '}' 
         { write_mem(--code, 0, CLOSE_PAREN, NULL);
           bindings--;
         }
   ;

Struct_elements:
   | Struct_elems
   ;

Struct_elems:  
     Struct_elems Exp1
   | Exp1
   ;


Symbols:
     Symbols SYMBOL
      {  oper.sym = $2; write_mem(--code, 0, SYM, &oper); }
   | SYMBOL
      {  oper.sym = $1; write_mem(--code, 0, SYM, &oper); }
   ;
   
Constant :
     CHARACTER
      { oper.charval = $1; write_mem(--code, APPLY, CHARAC, &oper); }
   | INTEGER
      { oper.intval = $1; write_mem(--code, APPLY, INT, &oper); }
   | FLONUM
      { oper.floval = $1; write_mem(--code, APPLY, FLOAT, &oper); }
   | SYMBOL
      { int index;
        index = find_index($1, bindings, 0);
        if (index >= 0) {
            oper.index = index;
            write_mem(--code, APPLY, VAR, &oper);
        }
        else 
           { oper.sym = $1; write_mem(--code, APPLY, $1->typ, &oper); }
      }
   | PROTECTED
      { int index;
        index = find_index($1, bindings, protect_marks);
        if (index >= 0) {
            oper.index = index;
            write_mem(--code, APPLY, VAR, &oper);
        }
        else if (index == -1)
           { oper.sym = $1; write_mem(--code, APPLY, $1->typ, &oper); }
        else
           { protected *protected_alloc();
             oper.sym = (symbol *) protected_alloc($1, -1 - index);
             write_mem(--code, APPLY, PROT, &oper);
           }
      }
   | '#'
      { yyclearin; yyerrok;
        if (source == FILE_IO)
          foutstring_ns(stdscr, "\n\r%s, line %d: ", file_name, line_number);
        else outstring_ns(stdscr, "\n\r");
        outstring_ns(stdscr, "Parse Error: Bad usage of binding protector '#' !");
        wrefresh(stdscr);
        return(1);
      }
   ;


Command :
     SYMBOL
      { command = $1; comm_switch = NULL; }
   | SYMBOL SYMBOL
      { command = $1; comm_switch = $2; }
   ;
   
  
 

%%
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

   
