/* Header file for the Head Order Reduction System 
/* Developed by Mike Hilton, 10 Jan 1990
/* Copyright 1989, 1990 Mike Hilton, All Rights reserved
/*
*/



/* Place the full path name of the prelude file here.
/* On unix systems, give the name of an environment variable that
/* has the full path name as its value.
*/

#ifdef IBM
#define PRELUDEFILE "prelude.lam"
#endif
#ifdef SUN
#define PRELUDEFILE "horse_prelude"
#endif


/*
/* STRUCTURE AND TYPE DEFINITIONS
*/

/*
/* Symbol Table Definitions
/* These are used mainly by the parser and compiler.
*/

union definiens {       
   struct node *user;         /* pointer to user defined graph */
   void (*prim) ();           /* pointer to builtin function   */
};

typedef struct symbol {
   char *print_name;          /* string representation of symbol     */
   int  typ;                  /* symbol type: SYM, PRIM_x        */
   struct symbol *link;       /* link to next symbol in table       */
   union definiens def;       /* definition associated with symbol   */
} symbol, *symbolptr;

#define HASHSIZE  21    /* size of the symbol table hashing array */
symbolptr symbol_table[HASHSIZE];   /* the symbol table array */

typedef struct protected {
   symbol *sym;
   int marks;
} protected;



/*
/* Abstract Memory Model For Reducer
/*
/* There are two types of memory in the graph reducer:  node memory,
/* which makes up the graphs and environment structures, and control
/* memory, which makes up the control and auxillary stacks.
*/

union operand {
   symbol *sym;
   float  floval;
   long   intval;
   int    index;
   char   charval;
   struct node *addr;
};
   
typedef struct node {
#ifdef IBM
   char waste1;
   char waste2;
#endif
   unsigned char class;   
   unsigned char type;   
   union operand op;
} node, *nodeptr;

/* Class definitions for nodes */
#define  BINDER   0
#define  CONTROL  0
#define  APPLY    1
#define  HEAD     2
#define  PAIR     4

#ifdef SUN
#define MEM_SIZE 100000    /* size of graph reducer memory */
#endif
#ifdef IBM
#define MEM_SIZE 35000
#endif
node *mem;                 /* graph memory array */


typedef union control {
   node *ptr;           /* pointer into graph memory */
   int  intval;         /* miscellaneous integer value */
   symbol *sym;         /* pointer to a symbol, used by printer */
} control;
   
#define CONTROL_SIZE 10000             /* size of control stack memory */
control *constack;                  /* Control stack */


/*
/* History type for input editor
*/

#define HISTORY_SIZE 1024     /* size of history buffers */
typedef struct history {      /* history buffers are implemented as queues */
   int   front;
   int   rear;
   char  queue[HISTORY_SIZE];
} history;



/*
/* GRAPH NODE TYPES
*/
            
#define LAMBDA    1     /* marks a single binding     */
#define PTR       2     /* pointer to an expression     */
#define VAR       3     /* variable binding index  */
#define INT       4     /* integer        */
#define SYM       5     /* user introduced symbol  */
#define PRIM_0    6     /* nonstrict primitive operator */
#define PRIM_1    7     /* unary primitive operator     */
#define PRIM_2    8     /* binary primitive operator    */
#define CLOSURE   9     /* closure        */
#define JOIN    11      /* links operands to AP node  */
#define UBV     12      /* unbound variable in environ   */
#define MARKER  13      /* break in environment context */
#define CL_PTR  14      /* Address pointer of a closure */
#define CL_ENV  15      /* Environment pointer of a closure */
#define STRUCT  16      /* Pointer to a structure       */
#define FLOAT   17      /* Floating point number        */
#define STOP    18      /* Instruction for stopping reduction */
#define DEF     20      /* Definition header */
#define EOD     21      /* End Of Definition pointer */
#define LET     23      /* Let binding */
#define LETSTAR 24      /* Let* binding */
#define LETREC  25      /* Letrec binding */
#define PROT    26      /* protected symbol, only used in parser */
#define RUP     27      /* Recursive UPdate marker, used with Letrecs */
#define REC     28      /* Letrec variable */
#define NOOP    29      /* No-op, location holds data */
#define IP      30      /* Invisible Pointer */
#define CHARAC  31      /* Character type */

/* used in parser-compiler */
#define OPEN_PAREN      100
#define CLOSE_PAREN     101
#define OPEN_BRACKET    102
#define CLOSE_BRACKET   103
#define OPEN_BRACE      104
#define CLOSE_BRACE     105

/* Mode Definitions */

#define PROBLEM   1     /* when traversing down a spine  */
#define RESULT    2     /* when returning up to the root */
#define HEADM     3     /* when at a head node           */


/* Command Definitions */

#define LAM_DEF   1
#define LAM_EXP   2
#define LAM_RED   3
#define LAM_COM   4
#define LAM_STRUCT   5
#define LAM_RDEF  6



/* Prototypes for Shared Functions */

/* COMPILER.Y */
#ifdef IBM
node  *compile_graph(node *start, node *end, node *dest);
node  *parse_expression(char *exp, node *low, node *high);
symbol   *symbol_lookup(char *word, int type);
#endif

#ifdef SUN
extern node *compile_graph();
extern node *parse_expression();
extern symbol *symbol_lookup();
#endif


/* DEBUG.C */
#ifdef IBM
void  bomb();
void  print_mem(WINDOW *stream, node *start, node *end);
void  print_node(WINDOW *stream, node *i);
#endif

#ifdef SUN
extern void bomb();
extern void print_mem();
extern void print_node();
#endif

/* EDIT. C */
#ifdef IBM
void  add_string_to_history(char *str, history *h);
void  history_initialize(history *h);
char  *input_line_editor(WINDOW *win);
#endif

#ifdef SUN
extern void add_string_to_history();
extern void history_initialize();
extern char *input_line_editor();
#endif

/* MAIN.C */
#ifdef IBM
int   load_file(char *name, int line_number, char *file_name);
#endif

#ifdef SUN
extern int load_file();
#endif


/* PRIMS.C */
#ifdef IBM
void  install_primitives(void);
#endif

#ifdef SUN
extern void install_primitives();
#endif


/* PRINTER.C */
#ifdef IBM
char  *sprint_expression(node *addr);
#endif

#ifdef SUN
extern char *print_expression();
extern char *sprint_expression();
#endif


/* RED.C */
#ifdef IBM
node  *reduce(node *start, node *ws, node *fs, int reds, int recursive);
node  *make_suspend(node *code, node *context, int bind_offset);
node  *make_closure(node *code, node *context);
#endif

#ifdef SUN
extern node *reduce();
extern node *make_suspend();
extern node *make_closure();
#endif
