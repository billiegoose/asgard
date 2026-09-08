/* Arithmetic Primitive Operators for the Head Order Reduction System
/* Mike Hilton, 11 Jan 1990
/*
/* This file contains the implementation details of the LRS builtin
/* arithmetic operators.
*/

#include <stdio.h>
#include <math.h>
#ifdef IBM
#include <stdlib.h>
#endif
#include <string.h>
#include <curses.h>
#include "lrs.h"

extern node *primitive;
extern node *ws;
extern unsigned long reductions;
extern unsigned long red_limit;

symbol *true;        /* points to the symbol for TRUE  */
symbol *false;       /* points to the symbol for FALSE */
extern symbol *pair; /* points to the symbol for list pairs */
extern symbol *string; /* points to the symbol for string pairs */

/*
/* Strict Binary Arithmetic Operators
/*
/* The strict binary arithmetic operators are invoked after both
/* arguments have been reduced.  If the type of both arguments is not
/* either integer or float, then reduction does not take place.
*/

#define ADD 1
#define SUB 2
#define MUL 3
#define DIV 4
#define MOD 5
#define MAX 6
#define MIN 7
#define EXPT 8

void binary_arithmetic(operator)
int operator;
{
   node *arg1, *arg2;
   long int1, int2, iresult;
   float flo1, flo2, fresult;

   if (reductions == red_limit) return;   
   arg1 = --primitive;
   arg2 = --primitive;

#ifdef DEBUG
   fprintf(stdout, "\nbinary_arithmetic: op = %d, arg1 = ", operator);
   print_node(stdout, arg1);
   fprintf(stdout, ", arg2 = ");
   print_node(stdout, arg2);
#endif
      
   if (arg1->type == INT) {
      int1 = arg1->op.intval;
      if (arg2->type == INT) {
         int2 = arg2->op.intval;
         switch (operator) {
            case ADD:   iresult = int1 + int2; break;
            case SUB:   iresult = int1 - int2; break;
            case MUL:   iresult = int1 * int2; break;
            case DIV:   iresult = int1 / int2; break;
            case MOD:   iresult = int1 % int2; break;
            case MAX:   if (int1 >= int2) iresult = int1; else iresult = int2;
                        break;
            case MIN:   if (int1 <= int2) iresult = int1; else iresult = int2;
                        break;
            case EXPT:  iresult = pow(int1, int2); break;
         }
         arg2->class = HEAD; arg2->type = INT; arg2->op.intval = iresult;
         ws = arg2;
      }
      else if (arg2->type == FLOAT) {
         flo2 = arg2->op.floval;
         switch (operator) {
            case ADD:   fresult = int1 + flo2; break;
            case SUB:   fresult = int1 - flo2; break;
            case MUL:   fresult = int1 * flo2; break;
            case DIV:   fresult = int1 / flo2; break;
            case MAX:   if (int1 >= flo2) {
                           arg2->class = HEAD; arg2->type = INT; 
                           arg2->op.intval = int1;
                           ws = arg2;
                           ++reductions;
                           return;
                        }
                        else fresult = flo2;
                        break;
            case MIN:   if ((float) int1 <= flo2) {
                           arg2->class = HEAD; arg2->type = INT; 
                           arg2->op.intval = int1;
                           ws = arg2;
                           ++reductions;
                           return;
                        }
                        else fresult = flo2;
                        break;
             case EXPT: fresult = pow(int1, flo2); break;
         }
         arg2->class = HEAD; arg2->type = FLOAT; arg2->op.floval = fresult;
         ws = arg2;
      }
      else return;
   }
   else if (arg1->type == FLOAT) {
      flo1 = arg1->op.floval;
      if (arg2->type == INT) {
         int2 = arg2->op.intval;
         switch (operator) {
            case ADD:   fresult = flo1 + int2; break;
            case SUB:   fresult = flo1 - int2; break;
            case MUL:   fresult = flo1 * int2; break;
            case DIV:   fresult = flo1 / int2; break;
            case MAX:   if (flo1 > int2) fresult = flo1; 
                        else {
                           arg2->class = HEAD; arg2->type = INT; 
                           arg2->op.intval = int2;
                           ws = arg2;
                           ++reductions;
                           return;
                        }
                        break;
            case MIN:   if (flo1 <= int2) fresult = flo1; 
                        else {
                           arg2->class = HEAD; arg2->type = INT; 
                           arg2->op.intval = int2;
                           ws = arg2;
                           ++reductions;
                           return;
                        }
                        break;
            case EXPT:  fresult = pow(flo1, int2); break;
         }
         arg2->class = HEAD; arg2->type = FLOAT; arg2->op.floval = fresult;
         ws = arg2;
      }
      else if (arg2->type == FLOAT) {
         flo2 = arg2->op.floval;
         switch (operator) {
            case ADD:   fresult = flo1 + flo2; break;
            case SUB:   fresult = flo1 - flo2; break;
            case MUL:   fresult = flo1 * flo2; break;
            case DIV:   fresult = flo1 / flo2; break;
            case MAX:   if (flo1 >= flo2) fresult = flo1; else fresult = flo2;
                        break;
            case MIN:   if (flo1 <= flo2) fresult = flo1; else fresult = flo2;
                        break;
            case EXPT:  fresult = pow(flo1, flo2); break;
         }
         arg2->class = HEAD; arg2->type = FLOAT; arg2->op.floval = fresult;
         ws = arg2;
      }
      else return;
   }
   else return;
   
   ++reductions;
}


void prim_add()  { binary_arithmetic(ADD); }
void prim_sub()  { binary_arithmetic(SUB); }
void prim_div()  { binary_arithmetic(DIV); }
void prim_mult() { binary_arithmetic(MUL); }
void prim_mod()  { binary_arithmetic(MOD); }
void prim_max()  { binary_arithmetic(MAX); }
void prim_min()  { binary_arithmetic(MIN); }
void prim_expt() { binary_arithmetic(EXPT); }            
   

/*
/* Strict Relational Operators
/*
/* The strict relational operators are invoked after both
/* arguments have been reduced.  If the type of both arguments is not
/* either integer or float, then reduction does not take place.
*/

#define GT  1
#define GTE 2
#define LT  3
#define LTE 4
#define EQ  5
#define NEQ 6

void binary_relational(operator)
int operator;
{
   node *arg1, *arg2;
   long int1, int2;
   float flo1, flo2;
   int result;

   if (reductions == red_limit) return;   
   arg1 = --primitive;
   arg2 = --primitive;

#ifdef DEBUG
   fprintf(stdout, "\nbinary_relational: op = %d, arg1 = ", operator);
   print_node(stdout, arg1);
   fprintf(stdout, ", arg2 = ");
   print_node(stdout, arg2);
#endif
      
   if (arg1->type == INT) {
      int1 = arg1->op.intval;
      if (arg2->type == INT) {
         int2 = arg2->op.intval;
         switch (operator) {
            case GT:    result = int1 >  int2; break;
            case GTE:   result = int1 >= int2; break;
            case LT:    result = int1 <  int2; break;
            case LTE:   result = int1 <= int2; break;
            case EQ:    result = int1 == int2; break;
            case NEQ:   result = int1 != int2; break;            
         }
         arg2->class = HEAD; arg2->type = SYM;
         if (result) arg2->op.sym = true; else arg2->op.sym = false;
         ws = arg2;
      }
      else if (arg2->type == FLOAT) {
         flo2 = arg2->op.floval;
         switch (operator) {
            case GT:    result = int1 >  flo2; break;
            case GTE:   result = int1 >= flo2; break;
            case LT:    result = int1 <  flo2; break;
            case LTE:   result = int1 <= flo2; break;
            case EQ:    result = int1 == flo2; break;
            case NEQ:   result = int1 != flo2; break;            
         }
         arg2->class = HEAD; arg2->type = SYM;
         if (result) arg2->op.sym = true; else arg2->op.sym = false;
         ws = arg2;
      }
      else return;
   }
   else if (arg1->type == FLOAT) {
      flo1 = arg1->op.floval;
      if (arg2->type == INT) {
         int2 = arg2->op.intval;
         switch (operator) {
            case GT:    result = flo1 >  int2; break;
            case GTE:   result = flo1 >= int2; break;
            case LT:    result = flo1 <  int2; break;
            case LTE:   result = flo1 <= int2; break;
            case EQ:    result = flo1 == int2; break;
            case NEQ:   result = flo1 != int2; break;            
         }
         arg2->class = HEAD; arg2->type = SYM;
         if (result) arg2->op.sym = true; else arg2->op.sym = false;
         ws = arg2;
      }
      else if (arg2->type == FLOAT) {
         flo2 = arg2->op.floval;
         switch (operator) {
            case GT:    result = flo1 >  flo2; break;
            case GTE:   result = flo1 >= flo2; break;
            case LT:    result = flo1 <  flo2; break;
            case LTE:   result = flo1 <= flo2; break;
            case EQ:    result = flo1 == flo2; break;
            case NEQ:   result = flo1 != flo2; break;            
         }
         arg2->class = HEAD; arg2->type = SYM; 
         if (result) arg2->op.sym = true; else arg2->op.sym = false;
         ws = arg2;
      }
      else return;
   }
   else return;
   
   ++reductions;
}

void prim_gt()  { binary_relational(GT);  }
void prim_gte() { binary_relational(GTE); }
void prim_lt()  { binary_relational(LT);  }
void prim_lte() { binary_relational(LTE); }
void prim_eq()  { binary_relational(EQ);  }
void prim_neq() { binary_relational(NEQ); }




/*
/* Strict Unary Arithetic Operators
*/


#define ABS    1
#define SQRT   2
#define MINUS  3
#define INC    4
#define DEC    5
#define FLOOR  6
#define CEIL   7

void unary_arithmetic(operator)
int operator;
{
   node  *arg;
   
   if (reductions == red_limit) return;
   arg = --primitive;
   
   if ((arg->type != INT) && (arg->type != FLOAT)) return;
   
   switch (operator) {
      case ABS:   if (arg->type == INT) {
                     if (arg->op.intval < 0) 
                         arg->op.intval = -1 * arg->op.intval;
                  }
                  else {
                     if (arg->op.floval < 0.0) 
                        arg->op.floval = -1.0 * arg->op.floval;
                  }
                  break;
#ifdef IBM                  
      case SQRT:  if (arg->type == INT) {
                     arg->type = FLOAT;
                     arg->op.floval = sqrt(arg->op.intval);
                  }
                  else {
                     arg->op.floval = sqrt(arg->op.floval);
                  }
                  break;
#endif
      case MINUS: if (arg->type == INT)
                     arg->op.intval = -1 * arg->op.intval;
                  else
                     arg->op.floval = -1.0 * arg->op.floval;
                  break;
                  
      case INC:   if (arg->type == INT) arg->op.intval += 1;
                  else arg->op.floval += 1.0;
                  break;
                  
      case DEC:   if (arg->type == INT) arg->op.intval -= 1;
                  else arg->op.floval -= 1.0;
                  break;

      case FLOOR: if (arg->type == FLOAT) {
                     arg->op.intval = floor(arg->op.floval);
                     arg->type = INT;
                  }
                  break;

      case CEIL:  if (arg->type == FLOAT) {
                     arg->op.intval = ceil(arg->op.floval);
                     arg->type = INT;
                  }
                  break;
   }
   arg->class = HEAD;
   ws = arg;
   ++reductions;
}


void prim_abs()  { unary_arithmetic(ABS); }          
void prim_sqrt() { unary_arithmetic(SQRT); } 
void prim_minus() { unary_arithmetic(MINUS); }
void prim_inc()  { unary_arithmetic(INC); }          
void prim_dec()  { unary_arithmetic(DEC); }          
void prim_floor() { unary_arithmetic(FLOOR); }
void prim_ceiling() { unary_arithmetic(CEIL); }


/*
/* Unary Relational Operators
*/

#define EVEN   1
#define ODD    2
#define POS    3
#define NEG    4
#define ATOM   5
#define FIXP   6
#define FLOP   7
#define SYMP   8
#define PAIRP  9
#define STRUCTP 10
#define STRINGP 11


void unary_relational(operator)
int operator;
{
   node   *arg;
   symbol *result;
   
   if (reductions == red_limit) return;
   arg = --primitive;
   if (arg->type == VAR) return;
   
   switch (operator) {
      case EVEN:  if (arg->type == INT) {
                     if ((arg->op.intval % 2) == 0) result = true;
                     else result = false;
                  }
                  else return;
                  break;
                  
      case ODD:   if (arg->type == INT) {
                     if ((arg->op.intval % 2) == 0) result = false;
                     else result = true;
                  }
                  else return;
                  break;

      case POS:   if (arg->type == INT) {
                     if (arg->op.intval >= 0) result = true;
                     else result = false;
                  }
                  else if (arg->type == FLOAT) {
                     if (arg->op.floval >= 0) result = true;
                     else result = false;
                  }
                  else return;
                  break;
                  
      case NEG:  if (arg->type == INT) {
                     if (arg->op.intval >= 0) result = false;
                     else result = true;
                  }
                  else if (arg->type == FLOAT) {
                     if (arg->op.floval >= 0) result = false;
                     else result = true;
                  }
                  else return;
                  break;

      case ATOM:  switch (arg->type) {
                     case CHARAC: case INT: case FLOAT:
                     case SYM:
                     case PRIM_0: case PRIM_1: case PRIM_2:
                        { result = true; break; }
                     default: { result = false; break; }
                  }
                  break;

      case FIXP:  if (arg->type == INT) result = true;
                  else result = false;
                  break;

      case FLOP:  if (arg->type == FLOAT) result = true;
                  else result = false;
                  break;

      case SYMP:  if (arg->type == SYM) result = true;
                  else result = false;
                  break;

      case PAIRP: if (arg->type == PTR 
                      && arg->op.addr->type == LAMBDA
                      && arg->op.addr->class & PAIR
                      && arg->op.addr->op.sym == pair)
                     result = true;
                  else result = false;
                  break;

      case STRINGP: if (arg->type == PTR 
                      && arg->op.addr->type == LAMBDA
                      && arg->op.addr->class & PAIR
                      && arg->op.addr->op.sym == string)
                     result = true;
                  else result = false;
                  break;



      case STRUCTP:  if (arg->type == PTR 
                         && arg->op.addr->type == LAMBDA
                         && arg->op.addr->class & PAIR
                         && arg->op.addr->op.sym != pair)
                        result = true;
                     else result = false;
                     break;

            
   }
   arg->class = HEAD; arg->type = SYM; arg->op.sym = result;
   ++reductions;
   ws = arg;
}


void prim_even()     { unary_relational(EVEN); }
void prim_odd()      { unary_relational(ODD); }
void prim_pos()      { unary_relational(POS); }
void prim_neg()      { unary_relational(NEG); }
void prim_atom()     { unary_relational(ATOM); }
void prim_intp()     { unary_relational(FIXP); }
void prim_floatp()   { unary_relational(FLOP); }
void prim_symp()     { unary_relational(SYMP); }
void prim_pairp()    { unary_relational(PAIRP); } 
void prim_structp()  { unary_relational(STRUCTP); } 
void prim_stringp()  { unary_relational(STRINGP); }


/* STRUCT_TAG
/* Returns the tag name of a structure.
*/

void prim_struct_tag()
{
   node   *arg;
   
   if (reductions == red_limit) return;
   arg = --primitive;

   if (arg->type == PTR 
       && arg->op.addr->type == LAMBDA
       && arg->op.addr->class & PAIR
       && arg->op.addr->op.sym != pair) {
      arg->class = HEAD; arg->type = SYM; arg->op.sym = arg->op.addr->op.sym;
      ++reductions;
      ws = arg;
   }
}
