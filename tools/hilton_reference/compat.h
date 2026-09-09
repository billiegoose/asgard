/* Headless platform services only; no graph operations or reducer replacements. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdarg.h>
#include <setjmp.h>
#include <sys/types.h>
#include <sys/timeb.h>
#define SUN 1
#define TRUE 1
#define FALSE 0
#define stdscr NULL
#define WINDOW void
static int wrefresh(void *stream) { return 0; }
static void outstring(void *stream, const char *text) { fputs(text, stderr); }
static void outstring_ns(void *stream, const char *text) { fputs(text, stderr); }
static void foutstring(void *stream, const char *format, ...) {
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args);
}
#define foutstring_ns foutstring
void bomb();
void print_node();
void print_mem();
void sum_times();
