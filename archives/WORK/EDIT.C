/* A STRING INPUT ROUTINE THAT ALLOWS EDITING DURING INPUT
/* Mike Hilton, 10 Nov 1989
/*
/* This package requires the use of the CURSES package.
/*
/* This file contains an input line editor with fence matching and
/* a history buffer.  The only exportable procedures are
/* INPUT_LINE_EDITOR, which reads in a line of input,
/* HISTORY_INITIALIZE, which initializes a history to be empty, and
/* ADD_STRING_TO_HISTORY, which inserts a string in the front of the history
/* buffer.
/* COPY_HISTORY_STRING, which copies a string from the history queue to a
/* specified destination string.
/* GET_HISTORY_STRING, which returns the buffer index of the next string
/* beginning at or after a specified place in the buffer.
/* Their prototypes are:
/*
/* char  *input_line_editor(WINDOW *win);
/* void  history_initialize(history *h);
/* void  add_string_to_history(char *str, history *h);
/* char  *copy_history_string(int index, char *dest, history *h);
/* int   get_history_string(int index, history *h);
/*
/* Editor command summary for IBM keyboards:
/* RIGHT ARROW    move cursor right one character
/* CONTROL RIGHT ARROW  move cursor to the beginning of word to the right
/* LEFT ARROW     move cursor left one character
/* CONTROL LEFT ARROW   move cursor to the beginning of word to the left
/* UP ARROW    move cursor one line upwards, or beginning of line
/* DOWN ARROW     move cursor one line downwards, or end of line
/* HOME        move cursor to beginning of line
/* END         move cursor to end of line
/* DELETE      delete the character under the cursor
/* BACKSPACE      delete the character to left of cursor
/* CONTROL K      delete all characters from cursor to end of line
/*
/*
/* History recall
/* CONTROL Y      Yank a string from the input history buffer.
/* CONTROL R      Yank a string from the output history buffer.
/* The history buffers are circular and may be cycled through by
/* repeated ctrl-y's.
/*
/*
/* !!!NOTE!!!  If your driver is to make use of the history buffer, it must
/* add string to the buffer after they are read, using the procedure
/* ADD_STRING_TO_HISTORY.
*/

#undef DEBUG_COPY_HISTORY

#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <curses.h>
#include <setjmp.h>
#ifdef IBM
#include <stdlib.h>
#include <io.h>
#endif
#ifdef SUN
#include <sys/signal.h>
#endif


#ifdef SUN
#define beep()  putchar(0x07)
#endif


#define  NAG_USER    /* if defined, user is beeped when cursor motions  */
#undef   NAG_USER    /*  exceed the boundaries of the input text        */

/* If non-zero, forces the number of open and close fences to be equal  */
/* in order to exit on a carriage return.                               */
#define  FENCE_MATCH 1  

#define FLASH_TIME   50000    /* reps for flash char timer loop */


#define BUFFER_SIZE 1024     /* size of input buffer */
char buffer[BUFFER_SIZE];    /* character buffer for input */


#define HISTORY_SIZE 1024     /* size of history buffers */
typedef struct history {      /* history buffers are implemented as queues */
   int   front;
   int   rear;
   char  queue[HISTORY_SIZE];
} history;



#define  BACK_SPACE  8
#define  CTRL_A      1
#define  CTRL_B      2
#define  CTRL_C      3
#define  CTRL_D      4
#define  CTRL_E      5
#define  CTRL_F      6
#define  CTRL_K      11
#define  CTRL_N      14
#define  CTRL_P      16
#define  CTRL_R      18
#define  CTRL_Y      25
#define  CTRL_Z      26
#define  DEL         127

/* Extended character codes for IBM keyboard */
#ifdef IBM
#define  L_ARROW     KEY_LEFT
#define  C_L_ARROW   KEY_CTRL_LEFT
#define  R_ARROW     KEY_RIGHT
#define  C_R_ARROW   KEY_CTRL_RIGHT
#define  U_ARROW     KEY_UP
#define  D_ARROW     KEY_DOWN
#define  DELETE      KEY_DC
#define  END      KEY_LL
#define  HOME     KEY_HOME
#endif





#define  close_fence(ch)   ((ch) == ')' || (ch) == '}' || (ch) == ']')
#define  open_fence(ch)    ((ch) == '(' || (ch) == '{' || (ch) == '[')
#define  delimiter(ch) (open_fence(ch) || close_fence(ch) || isspace(ch))

/* Prototypes */
#ifdef IBM
void  add_string_to_history(char *str, history *q);
char  *copy_history_string(int index, char *dest, history *h);
void  delete_buffer_from_index_to(WINDOW *win, int index, int to, int *eob);
void  delete_char_left(WINDOW *win, int *index, int *eob);
void  delete_char_right(WINDOW *win, int index, int *eob);
void  flash_char(WINDOW *win, int ch, int index);
void  flash_unmatched_fence(WINDOW *win, int index, int eob);
int   get_history_string(int index, history *q);
int   insert_char_left(WINDOW *in, char ch, int *index, int *eob);
int   insert_string_from_index(WINDOW *in, char *str, int *index, int *eob);
char  *input_line_editor(WINDOW *win);
int   matching_fences(char open, char close);
void  move_cursor_to_char(WINDOW *win, int ch, int index);
void  move_index_left_char(WINDOW *win, int *index);
void  move_index_left_word(WINDOW *win, int *index);
void  move_index_right_char(WINDOW *win, int *index, int eob);
void  move_index_right_word(WINDOW *win, int *index, int eob);
void  print_history(FILE *win, history *q);
int   history_empty(history q);
void  history_initialize(history *q);
int   unmatched_open_fence(int start, int bound);
int   unmatched_close_fence(int start, int bound);
void  cursor_left(WINDOW *win, int cols);
void  cursor_right(WINDOW *win, int cols);
void  cursor_up(WINDOW *win, int rows);
void  cursor_down(WINDOW *win, int rows);
void  cursor_goto(WINDOW *win, int row, int col);
void  cursor_erase_to_eol(WINDOW *win);
void  cursor_erase_screen(WINDOW *win);
void  cursor_save(WINDOW *win);
void  cursor_restore(WINDOW *win);
void  highlight_char(WINDOW *win, char ch);
#endif

#ifdef SUN
void  add_string_to_history();
char  *copy_history_string();
void  delete_buffer_from_index_to();
void  delete_char_left();
void  delete_char_right();
void  flash_char();
void  flash_unmatched_fence();
int   get_history_string();
int   insert_char_left();
int   insert_string_from_index();
char  *input_line_editor();
int   matching_fences();
void  move_cursor_to_char();
void  move_index_left_char();
void  move_index_left_word();
void  move_index_right_char();
void  move_index_right_word();
void  print_history();
int   history_empty();
void  history_initialize();
int   unmatched_open_fence();
int   unmatched_close_fence();
void  cursor_left();
void  cursor_right();
void  cursor_up();
void  cursor_down();
void  cursor_goto();
void  cursor_erase_to_eol();
void  cursor_erase_screen();
void  cursor_save();
void  cursor_restore();
void  highlight_char();
#endif

/* Global Variables */

extern jmp_buf abort_context;

int   fences;     /* number of open parens, brackets, or braces */
int   screen_height; /* height of input/output screen in lines */
int   screen_width;  /* width of input/output screen in characters */

history input_history, output_history;
char  history_temp[BUFFER_SIZE];

#ifdef DEBUG
main()
{
   history_initialize(&input_history);
   if (initscr() == ERR) {       /* initialize CURSES */
      fprintf(stderr, "\nUnable to initialize the CURSES package.");
      exit(1);
   }
   scrollok(stdscr, TRUE);
   leaveok(stdscr, FALSE);
   raw();
   noecho();
   nonl();
   keypad(stdscr, TRUE);
   
   while (!feof(stdin)) {
      addstr("\r\ninput>"); refresh();
      input_line_editor(stdscr);
      add_string_to_history(buffer, &input_history);
      addch('\r'); addstr(buffer); refresh();
      if (stricmp(buffer, "exit") == 0) break;
   }
   endwin();
}
#endif


/* INPUT_LINE_EDITOR
/* Read a string from an input stream, allowing the input to be edited.
/*
/* If the stream is a terminal, then matching fences are 
/* flashed as they are completed; an incorrectly matching close fence
/* is beeped.  Works for a single line input, which may span several
/* lines on the terminal.
/*
/* Returns a pointer to the string if successful, NULL otherwise.
*/

char *input_line_editor(win)
WINDOW *win;
{
   int ch;              /* character read from stream */
   int last_ch;         /* previous character read in main loop */
   int eob = 0;         /* end of buffer */
   int index = 0;       /* index into buffer, represents cursor position */   
   int yank_start;
   int old_index;

   eob = 0; index = 0;
   buffer[0] = '\0';

   fences = 0; 
   screen_width = COLS;
   screen_height = LINES;
   
   raw();  /* put terminal into raw mode */

   do {
      last_ch = ch;
      ch = (int) getch();

      switch (ch) {
         case EOF:      buffer[++eob] = '\0';
                        noraw();
                        return(buffer);

         case CTRL_C:   noraw(); longjmp(abort_context, 1);
#ifdef SUN
         case CTRL_Z:   kill(getpid(), SIGTSTP);
#endif
         case CTRL_B:
#ifdef IBM
         case L_ARROW:  
#endif
                        move_index_left_char(win, &index);
                        wrefresh(win);
                        break;
#ifdef IBM                       
         case C_L_ARROW:   move_index_left_word(win, &index);
                           wrefresh(win);
                           break;
#endif
         case CTRL_F:
#ifdef IBM
         case R_ARROW:  
#endif
                        move_index_right_char(win, &index, eob);
                        wrefresh(win);
                        break;
         
#ifdef IBM              
         case C_R_ARROW:   move_index_right_word(win, &index, eob);
                           wrefresh(win);
                           break;
#endif

         case CTRL_P:
#ifdef IBM
         case U_ARROW:
#endif
                        if (index - screen_width < 0) {
                           move_cursor_to_char(win, 0, index);
                           index = 0;
                        }
                        else {
                           move_cursor_to_char(win, index-screen_width, index);
                           index = index - screen_width;
                        }
                        wrefresh(win);
                        break;

         case CTRL_N:
#ifdef IBM 
         case D_ARROW:  
#endif
                        if (index + screen_width > eob) {
                           move_cursor_to_char(win, eob, index);
                           index = eob;
                        }
                        else {
                           move_cursor_to_char(win, index+screen_width, index);
                           index = index + screen_width;
                        }
                        wrefresh(win);
                        break;

         case CTRL_D:
#ifdef IBM
         case DELETE:   
#endif
                        delete_char_right(win, index, &eob);
                        wrefresh(win);
                        break;

         case CTRL_A:
#ifdef IBM
         case HOME:
#endif
                        move_cursor_to_char(win, 0, index);
                        wrefresh(win);
                        index = 0;
                        break;

         case CTRL_E:
#ifdef IBM
         case END:
#endif
                        move_cursor_to_char(win, eob, index);
                        wrefresh(win);
                        index = eob;
                        break;
 
         case CTRL_K:   /* Kill rest of buffer from cursor */
                        delete_buffer_from_index_to(win, index, eob, &eob);
                        wrefresh(win);
                        break;

         case CTRL_Y:   /* Yank from input history buffer, cycling through history */
                     {
                        if (last_ch != CTRL_Y) {
                           old_index = index;
                           yank_start = get_history_string(input_history.front, &input_history);
                        }
                        else {
                           move_cursor_to_char(win, old_index, index);
                           index = old_index;
                           delete_buffer_from_index_to(win, index, strlen(&(input_history.queue[yank_start]))+index, &eob);
                           if (yank_start == input_history.rear) yank_start = input_history.front;
                           else yank_start = get_history_string(yank_start-1, &input_history);
                        }
                        copy_history_string(yank_start, &history_temp[0], &input_history);
                        insert_string_from_index(win, &history_temp[0], &index, &eob);
                        wrefresh(win);
                        break;
                     }

         case CTRL_R: /* Yank from output history */
                     {
                        static int yank_start;
                        static int old_index;
                        if (last_ch != CTRL_R) {
                           old_index = index;
                           yank_start = get_history_string(output_history.front, &output_history);
                        }
                        else {
                           move_cursor_to_char(win, old_index, index);
                           index = old_index;
                           delete_buffer_from_index_to(win, index,
										strlen(&(output_history.queue[yank_start]))+index,
										&eob);
                           if (yank_start == output_history.rear) yank_start = output_history.front;
                           else yank_start = get_history_string(yank_start-1, &output_history);
                        }
                        copy_history_string(yank_start, &history_temp[0], &output_history);
                        insert_string_from_index(win, &history_temp[0], &index, &eob);
                        wrefresh(win);
                        break;
                     }

         case '\n':
         case '\r':  if (fences == 0 || !FENCE_MATCH) {
                        buffer[++eob] = '\0';
                        move_cursor_to_char(win, eob, index);
                        wrefresh(win);
                        noraw();
                        crmode();
                        return(buffer);
                     }
                     else {
                        beep();
                        flash_unmatched_fence(win, index, eob);
                        wrefresh(win);
                     }
                     break;

         case BACK_SPACE:
         case DEL:
                     delete_char_left(win, &index, &eob);
                     wrefresh(win);
                     break;

         default:    if (iscntrl((char) ch)) break;
                     if (insert_char_left(win, (char) ch, &index, &eob) == ERR)
                        break;
                     wrefresh(win);
                     if (open_fence(ch)) {
                        int close;
                        fences++;
                        close = unmatched_close_fence(index, eob);
                        if (close < eob) {
                           if (!matching_fences((char)ch, buffer[close])) beep();
                           flash_char(win, close, index);
                        }
                     }
                     else if (close_fence(ch)) {
                        int open;
                        fences--;
                        open = unmatched_open_fence(index-2, 0);
                        if (!matching_fences(buffer[open], (char)ch)) beep();
                        if (open >= 0) flash_char(win, open, index);
                     }
                     break;

      }
   } while (TRUE);
}


/* DELETE_BUFFER_FROM_INDEX_TO
/* Delete all characters in the buffer between INDEX and TO.
*/

void delete_buffer_from_index_to(stream, index, to, eob)
WINDOW *stream;
int index, to, *eob;
{
   while (to-- > index) delete_char_right(stream, index, eob);
}



/* DELETE_CHAR_LEFT
/* Delete the character to the left of INDEX.
*/

void delete_char_left(stream, index, eob)
WINDOW *stream;
int *index, *eob;
{
   int i;

   if (*index <= 0) {
#ifdef NAG_USER
      beep();
#endif      
      return;
   }
   
   /* If a fence was deleted, correct fence count */
   if (open_fence(buffer[*index-1])) fences--;
   else if (close_fence(buffer[*index-1])) fences++;

   /* shift buffer down by one character */
   for (i = *index; i <= *eob; i++) buffer[i-1] = buffer[i];
   *eob -= 1;

   /* update display */
   move_index_left_char(stream, index);
   cursor_save(stream);
   waddstr(stream, &buffer[*index]);
   waddch(stream, ' ');
   cursor_restore(stream);
}


/* DELETE_CHAR_RIGHT
/* Delete the character to the right of INDEX.
*/

void delete_char_right(stream, index, eob)
WINDOW *stream;
int index, *eob;
{
   int i;

   if (index >= *eob) {
#ifdef NAG_USER
      beep();
#endif
      return;
   }

   /* If a fence was deleted, correct fence count */
   if (open_fence(buffer[index])) fences--;
   else if (close_fence(buffer[index])) fences++;

   /* shift buffer down by one character */
   for (i = index; i < *eob; i++) buffer[i] = buffer[i+1];
   *eob -= 1;

   /* update display */
   cursor_save(stream);
   waddstr(stream, &buffer[index]);
   waddch(stream, ' ');
   cursor_restore(stream);
}



/* FLASH_UNMATCHED_FENCE
/* Search for an unmatched fence in the buffer starting at
/* the end of the buffer (EOB), and flash it.
*/

void flash_unmatched_fence(stream, index, eob)
WINDOW *stream;
int index, eob;
{
   int ch;

   ch = unmatched_open_fence(eob, 0);
   if (open_fence(buffer[ch]))
      flash_char(stream, ch, index);
   else {
      ch = unmatched_close_fence(0, eob);
      if (close_fence(buffer[ch]))
         flash_char(stream, ch, index);
   }
}


/* INSERT_CHAR_LEFT
/* Insert character CH into the input buffer to the left of the index.
/* If the character could not be inserted because the buffer was full,
/* the constant ERR is returned, otherwise OK is returned.
*/

int insert_char_left(stream, ch, index, eob)
WINDOW *stream;
char ch;
int *index, *eob;
{
   int i;

   if (*eob == BUFFER_SIZE-2) {
      /* Tell user buffer length exceeded */
      int before_row, after_row, before_col, after_col;
      move_cursor_to_char(stream, *eob, *index);
      getyx(stream, before_row, before_col);
      beep();
      waddstr(stream, "\n\rINPUT BUFFER LENGTH EXCEEDED! Hit a key to continue.");
      wrefresh(stream);
      fflush(stdin);
      getch();
      fflush(stdin);
      getyx(stream, after_row, after_col);
      cursor_goto(stream, after_row, 0);
      cursor_erase_to_eol(stream);
      cursor_goto(stream, before_row, before_col);
      if (before_row == after_row) cursor_up(stream, 1);
      move_cursor_to_char(stream, *index, *eob);
      wrefresh(stream);
      return(ERR);
   }

   /* make room in buffer for CH */
   *eob += 1;
   for (i = *eob; i > *index; i--) buffer[i] = buffer[i-1];
   buffer[*index] = ch;

   /* update display */
   waddstr(stream, &buffer[*index]);
   *index += 1;
   move_cursor_to_char(stream, *index, *eob);
   return(OK);
}

/* INSERT_STRING_FROM_INDEX
/* Insert STR into the buffer, starting at INDEX.
/* If the entire string cannot be inserted, ERR is returned; otherwise
/* OK is returned.
*/

int insert_string_from_index(win, str, index ,eob)
WINDOW *win;
char *str;
int *index, *eob;
{
   while (*str != '\0') 
      if (insert_char_left(win, *str++, index, eob) == ERR) return(ERR);

   return(OK);
}

/* MATCHING_FENCES
/* Returns 1 if the two characters are matching pairs of fences,
/* 0 otherwise.
*/

int matching_fences(open, close)
char open, close;
{
   return( (open == '(' && close == ')') ||
           (open == '{' && close == '}') ||
           (open == '[' && close == ']') );
}


/* MOVE_INDEX_LEFT_CHAR
/* Move the index left one character.
*/

void move_index_left_char(stream, index)
WINDOW *stream;
int *index;
{
   int row, col;
   
   if (*index == 0) {
#ifdef NAG_USER
      beep();
#endif
      return;
   }
   else {
      *index -= 1;
      getyx(stream, row, col);
      if (col <= 0) {
         if (row <= 0) {
            /* roll screen back if possible */
            row++;
         }
         cursor_goto(stream, row-1, screen_width-1);
      }
      else cursor_left(stream, 1);
   }
}

/* MOVE_INDEX_LEFT_WORD
/* Moves the cursor to the left one word.
*/

void move_index_left_word(stream, index)
WINDOW *stream;
int *index;
{
   while (*index > 0) {
      move_index_left_char(stream, index);
      if (!delimiter(buffer[*index])) break;
   }
   while ((*index > 0) && !delimiter(buffer[*index-1]))
      move_index_left_char(stream, index);
}

      

/* MOVE_INDEX_RIGHT_CHAR
/* Move the index right one character.
*/

void move_index_right_char(stream, index, eob)
WINDOW *stream;
int *index, eob;
{
   int row, col;

   if (*index == eob) {
#ifdef NAG_USER
      beep();
#endif
      return;
   }
   else {
      *index += 1;
      getyx(stream, row, col);
      if (col >= screen_width-1) {
         if (row >= screen_height-1) cursor_goto(stream, row, 0);
         else cursor_goto(stream, row+1, 0); 
      }
      else cursor_right(stream, 1);
   }
}


/* MOVE_INDEX_RIGHT_WORD
/* Moves the cursor to the beginning of the next word to the right.
*/

void move_index_right_word(stream, index, eob)
WINDOW *stream;
int *index, eob;
{
   while ((*index < eob) && (!delimiter(buffer[*index+1])))
      move_index_right_char(stream, index, eob);
   while (*index < eob) {
      move_index_right_char(stream, index, eob);
      if (!delimiter(buffer[*index])) break;
   }
}



/* UNMATCHED_OPEN_FENCE
/* Find the first unmatched open fence in the buffer, starting
/* at array index START.
/*
/* Returns the array index of the character.
*/

int unmatched_open_fence(start, bound)
int start, bound;
{
   int fences = 1;

   do {
      if (open_fence(buffer[start]))
         --fences;
      else if (close_fence(buffer[start]))
         ++fences;
   } while (fences > 0 && start-- > bound);
   return(start);
}


/* UNMATCHED_CLOSE_FENCE
/* Find the first unmatched close fence in the buffer, starting
/* at array index START.
/*
/* Returns the array index of the character.
*/

int unmatched_close_fence(start, bound)
int start, bound;
{
   int fences = 1;

   do {
      if (open_fence(buffer[start]))
         ++fences;
      else if (close_fence(buffer[start]))
         --fences;
   } while (fences > 0 && start++ < bound);
   return(start);
}



/*
/* CURSOR CONTROL ROUTINES
/*
*/

void cursor_left(stream,  cols)
WINDOW *stream;
int cols;
{
   int x, y;
   getyx(stream, y, x);
   wmove(stream, y, (x - cols));
}
   
void cursor_right(stream, cols)
WINDOW *stream;
int cols;
{
   int x, y;
   getyx(stream, y, x);
   wmove(stream, y, (x + cols));
}

void cursor_up(stream, rows)
WINDOW *stream;
int rows;
{
   int x, y;
   getyx(stream, y, x);
   wmove(stream, (y - rows), x);
}

void cursor_down(stream, rows)
WINDOW *stream;
int rows;
{
   int x, y;
   getyx(stream, y, x);
   wmove(stream, (y + rows), x);
}


static int saved_cursor_x, saved_cursor_y;

void cursor_save(stream)
WINDOW *stream;
{
   getyx(stream, saved_cursor_y, saved_cursor_x);
}

void cursor_restore(stream)
WINDOW *stream;
{
   wmove(stream, saved_cursor_y, saved_cursor_x);
}


void cursor_goto(stream, row, col)
WINDOW *stream;
int row, col;
{
   wmove(stream, row, col);
}


void cursor_erase_to_eol(stream)
WINDOW *stream;
{
   wclrtoeol(stream);
}

void cursor_erase_screen(stream)
WINDOW *stream;
{
   wclear(stream);
}




/* FLASH_CHAR
/* Flash the screen presentation of the character at index CH in buffer.
*/

void flash_char(stream, ch, index)
WINDOW *stream;
int ch, index;
{
   cursor_save(stream);
   move_cursor_to_char(stream, ch, index);
   highlight_char(stream, buffer[ch]);
   wrefresh(stream);
   { long i; for(i = 0; i < FLASH_TIME; i++); }
   cursor_left(stream, 1);
   waddch(stream, buffer[ch]);
   cursor_restore(stream);
   wrefresh(stream);
}

/* HIGHLIGHT_CHAR
/* Print a character on STREAM in highlighted fashion.
*/

void highlight_char(stream, ch)
WINDOW *stream;
char ch; 
{
   wstandout(stream);
   waddch(stream, ch);
   wstandend(stream);
}


/* MOVE_CURSOR_TO_CHAR
/* Moves the cursor to the screen location where character at array
/* index CH is located.
*/

void move_cursor_to_char(stream, ch, index)
WINDOW *stream;
int ch, index;
{
   int rows, cols;         /* difference in screen locations of CH and INDEX */
   int currow, curcol;     /* current cursor position */
   int diff;               /* number of chars between index and ch */

   getyx(stream, currow, curcol);
   diff = index - ch;
   if (((diff >= 0) && (diff <= curcol)) ||
       ((diff < 0) && (curcol - diff <= screen_width))) {
      rows = 0;
      cols = diff;
   }
   else {
      rows = (diff / screen_width);
      cols = diff - (screen_width * rows);
      if ((diff >= 0) && (cols > curcol)) {
         rows++;
         cols -= screen_width;
      }
      if ((diff < 0) && (curcol - cols > screen_width)) {
         rows--;
         cols += screen_width;
      }
   }

   if (rows > 0) cursor_up(stream, rows);
   else cursor_down(stream, abs(rows));

   if (cols > 0) cursor_left(stream, cols);
   else cursor_right(stream, abs(cols));
}



/* HISTORY MANAGEMENT ROUTINES
/*
/* A history of strings is maintained as a circular queue of characters.
/* The front of the queue points to the last character in the most
/* recent string.  The rear of the queue points to the first character
/* of the oldest string in the queue.
*/

void history_initialize(q)
history *q;
{
   q->front = 0;
   q->rear = 0;
}

int history_empty(q)
history q;
{ return( q.front == q.rear); }

void queue_increment(x)
int *x;
{
   *x += 1;
   if (*x == HISTORY_SIZE) *x = 0;
}

void queue_decrement(x)
int *x;
{
   if (*x == 0) *x = HISTORY_SIZE - 1;
   else *x -= 1;
}

int room_in_queue(q)
history *q;
{
   if (q->front >= q->rear)
      return(HISTORY_SIZE - (q->front - q->rear) - 1);
   else
      return(q->rear - q->front - 1);
}


/* ADD_STRING_TO_HISTORY
/* Copies STR onto the front of the history queue.  If the string is longer
/* than the history buffer, it is ignored.
*/

void add_string_to_history(str, q)
char *str;
history *q;
{
   int length = strlen(str) + 1;

   if (length > HISTORY_SIZE) return;
   
   while (room_in_queue(q) <= length) {
      while (q->queue[q->rear] != '\0')
         queue_increment(&q->rear);
      if (q->rear == q->front) break;
      queue_increment(&q->rear);
   }

   if (q->rear == q->front) queue_increment(&q->rear);
   for(; *str != '\0'; str++) {
      queue_increment(&q->front);
      q->queue[q->front] = *str;
   }
   queue_increment(&q->front);
   q->queue[q->front] = '\0';
}


/* COPY_HISTORY_STRING
/* Copies the string starting at index START in a history buffer to
/* DEST.  This is necessary for external functions to use in order
/* to avoid problems with queue wrap around.
/*
/* Returns a pointer to the NULL character ending the string.
*/

char *copy_history_string(start, dest, hist)
int start;
char *dest;
history *hist;
{
	char *ch = &(hist->queue[start]);
	char *temp = dest;
	
	while (*ch) {
		*(dest++) = *(ch++);
		if (ch >= hist->queue + HISTORY_SIZE) ch = &(hist->queue[0]);
	}
	*dest = '\0';
#ifdef DEBUG_COPY_HISTORY
	foutstring(stdscr, "\n\n\rcopied history string: %s\n\n\r", temp);
	wrefresh(stdscr);
#endif
	return(dest);
}

/* GET_HISTORY_STRING
/* Finds and returns an index to the start of the string beginning
/* at element INDEX in the history buffer.
*/

int get_history_string(index, q)
int index;
history *q;
{
   while(index != q->rear) {
      queue_decrement(&index);
      if (q->queue[index] == '\0') {
         queue_increment(&index);
         break;
      }
   }
   return(index);
}

/* PRINT_HISTORY
/* Prints the contents of the history buffer in reverse chronological
/* order.
*/

void print_history(stream, q)
FILE *stream;
history *q;
{
   int index = q->front;
   int i = 0;
   int j;

   fprintf(stream, "\nHISTORY:");
#ifdef DEBUG
   fprintf(stream, " rear = %d, front = %d, size = %d", q->rear, q->front, room_in_queue(q));
#endif
   do {
      index = get_history_string(index, q);
      fprintf(stream, "\n%d. ", ++i);
      j = index; 
      while (q->queue[j] != '\0') {
         putc(q->queue[j], stream);
         queue_increment(&j);
      }
      if (index == q->rear) break;
      queue_decrement(&index);
   }  while (TRUE);
}


