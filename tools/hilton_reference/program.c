/* Headless lifecycle and observations; compiler/reducer/printer are archived C. */
history input_history, output_history;
static FILE *graphs_file, *trace_file;
static long trace_limit, trace_count;
static int observing, expression_number;

/* prim_y can execute a static temporary node outside the arena. */
static long node_offset(node *p) {
    uintptr_t address = (uintptr_t)p, base = (uintptr_t)mem;
    if (address < base || address >= base + MEM_SIZE * sizeof(node)) return -1;
    return (long)((address - base) / sizeof(node));
}

symbol *symbol_lookup(char *name, int type) {
    char *writable = strdup(name);
    symbol *answer;
    if (!writable) exit(71);
    answer = archive_symbol_lookup(writable, type);
    free(writable);
    return answer;
}

void repaired(const char *name) {
    static const char *seen[3];
    static int count;
    int i;
    for (i = 0; i < count; i++) if (!strcmp(name, seen[i])) return;
    if (count == 3) bomb();
    seen[count++] = name;
    fprintf(stderr, "\nport repair exercised: %s\n", name);
}
void bomb() { fprintf(stderr, "\narchived HORSE bomb\n"); longjmp(abort_context, 1); }
void print_node() { }
void print_mem() { }
void print_stats() { }
char *input_line_editor() { bomb(); return NULL; }
void add_string_to_history() { bomb(); }
void handle_command() { fprintf(stderr, "\nUse the runner options instead of interactive commands.\n"); bomb(); }

static void json_string(FILE *out, const char *s) {
    unsigned char c;
    fputc('"', out);
    while ((c = (unsigned char)*s++)) {
        if (c == '"' || c == '\\') { fputc('\\', out); fputc(c, out); }
        else if (c < 32 || c >= 127) fprintf(out, "\\u%04x", c);
        else fputc(c, out);
    }
    fputc('"', out);
}

static const char *node_type(int type) {
    switch (type) {
        case LAMBDA: return "LAMBDA"; case PTR: return "PTR";
        case VAR: return "VAR"; case INT: return "INT"; case SYM: return "SYM";
        case PRIM_0: return "PRIM_0"; case PRIM_1: return "PRIM_1";
        case PRIM_2: return "PRIM_2"; case CLOSURE: return "CLOSURE";
        case JOIN: return "JOIN"; case UBV: return "UBV"; case MARKER: return "MARKER";
        case CL_PTR: return "CL_PTR"; case CL_ENV: return "CL_ENV";
        case STRUCT: return "STRUCT"; case FLOAT: return "FLOAT"; case STOP: return "STOP";
        case DEF: return "DEF"; case EOD: return "EOD"; case LET: return "LET";
        case LETSTAR: return "LETSTAR"; case LETREC: return "LETREC";
        case RUP: return "RUP"; case REC: return "REC"; case NOOP: return "NOOP";
        case IP: return "IP"; case CHARAC: return "CHAR"; default: return "UNKNOWN";
    }
}

static void nodes(FILE *out, node *first, node *last) {
    node *n;
    fputc('[', out);
    for (n = first; n <= last; n++) {
        if (n != first) fputc(',', out);
        fprintf(out, "{\"address\":%ld,\"class\":%u,\"type\":\"%s\",\"operand\":",
                node_offset(n), n->class, node_type(n->type));
        switch (n->type) {
            case PTR: case CLOSURE: case JOIN: case MARKER: case CL_PTR: case CL_ENV:
            case STRUCT: case EOD: case LETREC: case REC: case IP:
                fprintf(out, "%ld", node_offset(n->op.addr)); break;
            case LAMBDA: case LET: case LETSTAR: case SYM: case PRIM_0: case PRIM_1:
            case PRIM_2: case DEF: json_string(out, n->op.sym->print_name); break;
            case VAR: case UBV: case RUP: fprintf(out, "%d", n->op.index); break;
            case INT: fprintf(out, "%ld", n->op.intval); break;
            case FLOAT: fprintf(out, "%.9g", n->op.floval); break;
            case CHARAC: fprintf(out, "%u", (unsigned char)n->op.charval); break;
            default: fputs("null", out);
        }
        fputc('}', out);
    }
    fputc(']', out);
}

static void graph_event(const char *stage, node *first, node *last) {
    int reduced = !strcmp(stage, "result");
    if (!graphs_file) return;
    fprintf(graphs_file, "{\"expression\":%d,\"stage\":\"%s\",\"root\":%ld,\"nodes\":",
            expression_number, stage, (long)(first - mem));
    nodes(graphs_file, first, last);
    fputs(",\"definitions\":", graphs_file); nodes(graphs_file, mem, problem-1);
    fprintf(graphs_file, ",\"reductions\":%lu,\"instructions\":%lu,\"peak_environment_words\":%ld}\n",
            reduced ? reductions : 0, reduced ? instructs : 0,
            reduced ? (long)(initial_env - max_env) : 0);
    fflush(graphs_file);
}

void trace_step(void) {
    if (!observing || !trace_file) return;
    if (trace_count++ >= trace_limit) return;
    fprintf(trace_file, "{\"expression\":%d,\"step\":%ld,\"pc\":%ld,\"ws\":%ld,\"fs\":%ld,\"env\":%ld,\"mode\":%d,\"stack\":%ld,\"reductions\":%lu,\"graph\":",
            expression_number, trace_count, node_offset(pc), (long)(ws-mem),
            (long)(fs-mem), (long)(env-mem), mode, (long)(stack-constack), reductions);
    nodes(trace_file, result, ws);
    fputs(",\"instruction\":", trace_file); nodes(trace_file, pc, pc);
    fputs(",\"environment\":", trace_file); nodes(trace_file, fs, high-1);
    fputs("}\n", trace_file);
}

int main(int argc, char **argv) {
    int quantum, memory_words, compile_only, passes, pass;
    node *workspace;
    if (argc != 10) {
        fprintf(stderr, "Usage: horse PRELUDE INPUT QUANTUM MEMORY GRAPHS|- TRACE|- TRACE_LIMIT COMPILE_ONLY PASSES\n");
        return 64;
    }
    quantum = atoi(argv[3]); memory_words = atoi(argv[4]);
    trace_limit = atol(argv[7]); compile_only = atoi(argv[8]);
    passes = atoi(argv[9]);
    if (memory_words < 256 || memory_words > MEM_SIZE || quantum < 0 || trace_limit < 0 || passes < 1) return 64;
    mem = calloc(MEM_SIZE, sizeof(node));
    constack = calloc(CONTROL_SIZE, sizeof(control));
    if (!mem || !constack) return 71;
    high = mem + memory_words - 1; low = mem; fs = high; ws = low;
    stack = constack; aux = constack + CONTROL_SIZE - 1;
    focus = NONE; force = 0; stats = 1; step = 1; line_number = 1; file_name = "";
    if (setjmp(abort_context)) {
        fprintf(stderr, "\nHORSE execution failed\n");
        if (trace_file) {
            fprintf(trace_file, "{\"stage\":\"fault\",\"observed_steps\":%ld}\n", trace_count);
            fclose(trace_file);
        }
        return 70;
    }
    if (setenv(PRELUDEFILE, argv[1], 1)) return 71;
    install_primitives();
    if (parse_failed) return 65;
    input_file = fopen(argv[2], "r"); file_name = argv[2]; line_number = 1;
    if (!input_file) { perror(argv[2]); return 66; }
    if (strcmp(argv[5], "-")) graphs_file = fopen(argv[5], "w");
    if (strcmp(argv[6], "-")) trace_file = fopen(argv[6], "w");
    if ((strcmp(argv[5], "-") && !graphs_file) || (strcmp(argv[6], "-") && !trace_file)) return 73;
    while (!feof(input_file)) {
        observing = 1;
        rep_loop(input_file);
        observing = 0;
        if (parse_failed) return 65;
        if (expr_type < 0) {
            if (!feof(input_file)) { fprintf(stderr, "\nParse failed at line %d\n", line_number); return 65; }
            break;
        }
        if (expr_type == LAM_RED && focus == OLD) {
            graph_event("result", result, ws);
            puts(sprint_expression(result));
            continue;
        }
        if (expr_type != LAM_EXP) continue;
        ++expression_number;
        graph_event("compiled", problem, result-2);
        if (compile_only) { puts(sprint_expression(problem)); continue; }
        for (pass = 0; pass < passes; pass++) {
            if (pass) {
                /* Same copy/shift/restart sequence as archived MAIN's LAM_RED. */
                result = copy_graph(result, ws+1);
                result = shift_memory(ws+1, result, problem) + 1;
                graph_event("restarted", problem, result-1);
            }
            observing = 1;
            workspace = result;
            result = reduce(problem, result, high, quantum, FALSE);
            observing = 0;
            graph_event("result", result, ws);
            puts(sprint_expression(result));
            fprintf(stderr, "\n%lu reductions; peak graph %ld words; peak environment %ld words\n",
                    reductions, (long)(max_graph - workspace), (long)(initial_env-max_env));
            if (reductions < (unsigned long)quantum || quantum == 0) break;
        }
        focus = OLD;
    }
    if (trace_file) {
        fprintf(trace_file, "{\"stage\":\"trace-end\",\"observed_steps\":%ld,\"written_steps\":%ld,\"truncated\":%s}\n",
                trace_count, trace_count < trace_limit ? trace_count : trace_limit,
                trace_count > trace_limit ? "true" : "false");
        fclose(trace_file);
    }
    if (graphs_file) fclose(graphs_file);
    fclose(input_file);
    return 0;
}
