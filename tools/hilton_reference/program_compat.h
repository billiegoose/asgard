/* Platform services for the archived whole-program HORSE build. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <setjmp.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/timeb.h>
#define SUN 1
#define TRUE 1
#define FALSE 0
#define WINDOW void
#define stdscr NULL
#define stricmp strcasecmp
static int parse_failed;
static int wrefresh(void *stream) { return 0; }
static void outstring(void *stream, const char *text) {
    if (strstr(text, "Parse Error")) parse_failed = 1;
    fputs(text, stderr);
}
#define outstring_ns outstring
static void foutstring(void *stream, const char *format, ...) {
    va_list args; va_start(args, format); vfprintf(stderr, format, args); va_end(args);
}
#define foutstring_ns foutstring
void bomb();
void print_node();
void print_mem();
