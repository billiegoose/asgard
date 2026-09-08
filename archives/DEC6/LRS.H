/* Header file for the Lambda Reduction System  */
/* Mike Hilton, 18 Oct 1989 */

/* Place the full path name of the list primitives file here.
/* This should be changed whenever porting to a new system.
*/

#ifdef IBM
#define LISTFILE "lists.lam"
#endif
#ifdef SUN
#define LISTFILE "/home/hilton/horse/lists.lam"
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
   struct node *addr;
   struct reset *rptr;
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
#define  UNBOUND	8
#define 	EXISTS	16


unsigned long MEM_SIZE;		/* number of graph nodes */
node *mem;        /* graph memory array */

unsigned long HEAP_SIZE;	/* The heap is used to store graphs reduced 	*/
node *heap_space;				/* during unification for later use.			*/


/* Reset_list contains information to undo unification bindings */
typedef struct reset {
	int val;	 		/* initial binding index value of variable */
	node *addr;		/* pointer to the variable in environment */
} reset;

unsigned long RESET_SIZE;			/* size of reset list memory */
reset *reset_list;		


/* STACK and AUX are control stacks */
typedef union control {
   node *ptr;           /* pointer into graph memory */
   int  intval;         /* miscellaneous integer value */
   symbol *sym;         /* pointer to a symbol, used by printer */
   reset *rptr;			/* pointer into the reset list */
} control;
   
unsigned long CONTROL_SIZE;       /* number of control stack nodes */
control *constack;      /* Control stack */



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
#define EX_LAMBDA 31		/* Lambda that has been instantiated by unification */
#define RESET	32			/* Undoes unification bindings */
#define EP		33			/* Pointer into environment */
#define EX_LIST	34		/* Pointer to list of existential lifted variables */
#define	EX_SCOPE	35		/* index contains bn of outermost scope for lifting */

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

#define atomic(ptr) (((ptr)->type != PTR) && ((ptr)->type != CLOSURE))


/* Command Definitions */

#define LAM_DEF   1
#define LAM_EXP   2
#define LAM_RED   3
#define LAM_COM   4
#define LAM_STRUCT   5




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
char  *copy_history_string(int index, char *dest, history *h);
int	get_history_string(int index, history *h);
void  history_initialize(history *h);
char  *input_line_editor(WINDOW *win);
#endif

#ifdef SUN
extern void add_string_to_history();
extern char *copy_history_string();
extern int  get_history_string();
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
node	*lookup(node *env, int index);
#endif

#ifdef SUN
extern node *reduce();
extern node *make_suspend();
extern node *make_closure();
extern node *lookup();
#endif


/* UNIFY.C */
#ifdef IBM
void bind_var(node *var, node *val, node *env);
node *insert_binding_pairs(reset *ptr, node *anchor, node *head, int before);
void make_result(node *addr, symbol *value);
void undo_bindings(reset *ptr);
#endif

#ifdef SUN
extern void bind_var();
extern node *insert_binding_pairs();
extern void make_result();
extern void undo_bindings();
#endif
