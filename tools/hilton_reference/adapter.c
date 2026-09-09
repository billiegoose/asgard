/* Included AFTER the archived bodies by runner.py. Fixtures are explicit nodes.
 * All reducer work is performed by those bodies, not by these observations. */
int debug = 0, stats = 0;
jmp_buf abort_context;
struct timeb start_time, stop_time;
static node arena[256];
static control controls[CONTROL_SIZE];
static symbol symbols[8];
static const char *calls[128];
static int call_count, event_count;
static const char *repair_calls[3];
static int repair_count;
static char alias_buffer[512];

static const char *pointer_alias(int left, int right) {
    if (arena[left].type != PTR || arena[right].type != PTR ||
        arena[left].op.addr != arena[right].op.addr) return "[]";
    snprintf(alias_buffer, sizeof(alias_buffer),
             "[{\"nodes\":[%d,%d],\"target\":%ld}]",
             left, right, (long)(arena[left].op.addr - arena));
    return alias_buffer;
}

void bomb() { fprintf(stderr, "archived bomb\n"); exit(70); }
void print_node() { }
void print_mem() { }
void sum_times() { } /* timing is not a semantic input */
symbol *symbol_lookup(name, type)
char *name;
int type;
{
    /* Only wrap_lambdas requests a name; no parser or symbol definitions. */
    if (strcmp(name, "%gv%") != 0) bomb();
    return &symbols[7];
}

void entered(const char *name) {
    int i;
    for (i = 0; i < call_count; i++) if (!strcmp(calls[i], name)) return;
    if (call_count == 128) bomb();
    calls[call_count++] = name;
}

void repaired(const char *name) {
    int i;
    for (i = 0; i < repair_count; i++) if (!strcmp(repair_calls[i], name)) return;
    if (repair_count == 3) bomb();
    repair_calls[repair_count++] = name;
}

static void event(const char *name) {
    printf("%s{\"at\":\"%s\",\"ws\":%ld,\"fs\":%ld}",
           event_count++ ? "," : "", name, (long)(ws - arena), (long)(fs - arena));
}
#define STEP(name, operation) do { operation; event(name); } while (0)
static void integer(int offset, int class_, long value) {
    arena[offset].class = class_; arena[offset].type = INT;
    arena[offset].op.intval = value;
}
static void pointer(int offset, int class_, int type, int target) {
    arena[offset].class = class_; arena[offset].type = type;
    arena[offset].op.addr = arena + target;
}
static void boolean(int offset, symbol *value) {
    arena[offset].class = APPLY; arena[offset].type = SYM;
    arena[offset].op.sym = value;
}
static void operator_node(int offset, int type, symbol *value) {
    arena[offset].class = HEAD; arena[offset].type = type;
    arena[offset].op.sym = value;
}
static void begin(int working) {
    ws = arena + working; env = fs = arena + 200;
    stack = constack = controls; aux = controls + CONTROL_SIZE - 1;
    mem = arena; mode = PROBLEM; red_limit = 1000; prim_args = -1;
    true = &symbols[0]; false = &symbols[1];
    and = &symbols[2]; and->def.prim = prim_and;
    equal = &symbols[3]; equal->def.prim = prim_equal;
    equal_star = &symbols[4]; equal_star->def.prim = prim_equal_star;
    symbols[5].def.prim = prim_add;
    arena[10].class = CONTROL; arena[10].type = STOP;
    printf("{\"events\":["); event("initial");
}
static void finish(const char *aliases) {
    int i;
    printf(",\"aliases\":%s,\"repairs_exercised\":[", aliases);
    for (i = 0; i < repair_count; i++) printf("%s\"%s\"", i ? "," : "", repair_calls[i]);
    printf("],\"functions\":[");
    for (i = 0; i < call_count; i++) printf("%s\"%s\"", i ? "," : "", calls[i]);
    puts("]}");
}
static void value_result(node *value) {
    if (value->type == INT)
        printf("],\"result\":{\"type\":\"INT\",\"value\":%ld}", value->op.intval);
    else if (value->type == SYM && (value->op.sym == true || value->op.sym == false))
        printf("],\"result\":{\"type\":\"BOOL\",\"value\":%s}", value->op.sym == true ? "true" : "false");
    else bomb();
}
/* Typed snapshots: every value/target is read from the actual C nodes. */
static void graph_nodes_at(node *nodes, int first, int last) {
    int i;
    printf("[");
    for (i = first; i <= last; i++) {
        node *n = nodes + (i - first);
        printf("%s{\"offset\":%d,\"class\":%d,\"type\":%d,\"operand\":",
               i == first ? "" : ",", i, n->class, n->type);
        switch (n->type) {
            case PTR: case LETREC: case JOIN: case MARKER: case CL_PTR: case CL_ENV:
                printf("%ld", (long)(n->op.addr - arena)); break;
            case VAR: case RUP: case UBV: printf("%d", n->op.index); break;
            case INT: printf("%ld", n->op.intval); break;
            case LAMBDA: printf("\"binder\""); break;
            case PRIM_0:
                if (n->op.sym == equal) printf("\"equal\"");
                else if (n->op.sym == equal_star) printf("\"equal_star\"");
                else if (n->op.sym == and) printf("\"and\"");
                else if (n->op.sym == &symbols[6]) printf("\"y\"");
                else bomb();
                break;
            default: bomb();
        }
        printf("}");
    }
    printf("]");
}
static void graph_nodes(int first, int last) {
    graph_nodes_at(arena + first, first, last);
}
static void graph_result(int first, int last) {
    printf("],\"result\":{\"nodes\":");
    graph_nodes(first, last);
    printf("}");
}

int main(int argc, char **argv) {
    const char *id;
    if (argc != 2) return 64;
    id = argv[1];
    if (setjmp(abort_context)) return 71;
    if (!strcmp(id, "atomic-child-return")) {
        begin(13);
        integer(10, HEAD, 0);
        pointer(12, CONTROL, JOIN, 10); integer(13, HEAD, 42);
        STEP("jump_subgraph", jump_subgraph());
        STEP("make_closure", make_closure(arena + 30, env));
        STEP("push_marker", push_marker());
        pc = arena + 12; mode = RESULT;
        STEP("inst_join", inst_join());
        value_result(arena + 10); finish("[]");
    } else if (!strcmp(id, "closure-sharing")) {
        begin(13);
        pointer(190, HEAD, CL_PTR, 30); pointer(191, HEAD, CL_ENV, 200);
        pointer(10, APPLY, CLOSURE, 190); pointer(11, APPLY, CLOSURE, 190);
        pointer(12, CONTROL, JOIN, 10); integer(13, HEAD, 42);
        /* These are older sharing cells, outside the child [fs, saved-fs). */
        fs = env = arena + 180; event("parent");
        STEP("jump_subgraph", jump_subgraph());
        STEP("make_closure", make_closure(arena + 40, env));
        pc = arena + 12; mode = RESULT;
        STEP("inst_join", inst_join());
        pc = arena + 11;
        STEP("inst_closure", inst_closure());
        printf("],\"result\":{\"destination\":%ld,\"cell\":%ld,\"second_use\":%ld}",
               arena[10].op.intval, arena[190].op.intval, arena[11].op.intval);
        finish(arena[10].type == INT && arena[190].type == INT && arena[11].type == INT &&
               arena[10].op.intval == arena[190].op.intval && arena[11].op.intval == arena[190].op.intval
               ? "[{\"nodes\":[10,11,190],\"relation\":\"shared-value\"}]" : "[]");
    } else if (!strcmp(id, "join-pointer-live")) {
        begin(13); integer(10, HEAD, 0);
        pointer(12, CONTROL, JOIN, 10); pointer(13, HEAD, PTR, 30);
        integer(30, APPLY, 1); integer(31, HEAD, 2);
        STEP("jump_subgraph", jump_subgraph());
        pc = arena + 12; mode = RESULT;
        STEP("inst_join", inst_join());
        graph_result(10, 10);
        finish(pointer_alias(10, 13));
    } else if (!strcmp(id, "lambda-consume")) {
        begin(11); integer(11, APPLY, 42);
        arena[30].type = LAMBDA; pc = arena + 30; argcount = 1;
        STEP("inst_lambda", inst_lambda());
        value_result(env); finish("[]");
    } else if (!strcmp(id, "rup-contract")) {
        begin(12); env = arena + 190; fs = arena + 180; event("parent");
        pointer(190, HEAD, REC, 180); pointer(191, HEAD, REC, 183);
        integer(32, BINDER, 2); arena[32].type = RUP;
        pc = arena + 32; argcount = 2;
        STEP("inst_rup", inst_rup());
        printf("],\"result\":{\"argcount\":%d,\"contexts\":[%ld,%ld],\"recstarts\":[%ld,%ld]}",
               argcount, (long)(arena[181].op.addr-arena), (long)(arena[184].op.addr-arena),
               (long)(arena[182].op.addr-arena), (long)(arena[185].op.addr-arena));
        snprintf(alias_buffer, sizeof(alias_buffer),
                 "[{\"nodes\":[181,184],\"target\":%ld},{\"nodes\":[182,185],\"target\":%ld}]",
                 (long)(arena[181].op.addr-arena), (long)(arena[182].op.addr-arena));
        finish(arena[181].op.addr == arena[184].op.addr &&
               arena[182].op.addr == arena[185].op.addr ? alias_buffer : "[]");
    } else if (!strcmp(id, "primitive-add")) {
        begin(13); integer(11, APPLY, 2); integer(12, APPLY, 40);
        operator_node(13, PRIM_2, &symbols[5]); primitive = arena + 13;
        STEP("prim_add", prim_add()); value_result(arena + 11); finish("[]");
    } else if (!strcmp(id, "if-true") || !strcmp(id, "if-false")) {
        begin(14); pointer(11, APPLY, PTR, 40); pointer(12, APPLY, PTR, 30);
        integer(30, HEAD, 7); integer(40, HEAD, 9);
        boolean(13, !strcmp(id, "if-true") ? true : false);
        (++stack)->ptr = env; (++stack)->ptr = env; (--aux)->intval = 0;
        primitive = arena + 14; pc = arena + 12; mode = RESULT;
        STEP("prim_if", prim_if());
        printf("],\"result\":{\"selected\":%ld,\"value\":%ld,\"stack\":%ld,\"aux\":%ld}",
               (long)(pc-arena), pc->op.intval, (long)(stack-controls), (long)(aux-controls));
        finish("[]");
    } else if (!strcmp(id, "and-discard") || !strcmp(id, "or-discard")) {
        begin(14); pointer(11, APPLY, PTR, 30); pointer(12, APPLY, PTR, 40);
        /* NOOP targets are deliberately not reducible; demanding them bombs. */
        arena[30].type = arena[40].type = NOOP;
        boolean(13, !strcmp(id, "and-discard") ? false : true);
        (++stack)->ptr = env; (++stack)->ptr = env; (--aux)->intval = 2;
        primitive = arena + 14; pc = arena + 12; mode = RESULT;
        if (!strcmp(id, "and-discard")) { STEP("prim_and", prim_and()); }
        else { STEP("prim_or", prim_or()); }
        printf("],\"result\":{\"value\":%s,\"stack\":%ld,\"discarded_types\":[%d,%d]}",
               arena[11].op.sym == true ? "true" : "false", (long)(stack-controls),
               arena[30].type, arena[40].type); finish("[]");
    } else if (!strcmp(id, "y-reconstruct")) {
        node *recursive_argument, *answer;
        char reconstruction[256], resumed[256];
        begin(11); pointer(11, APPLY, PTR, 30); pointer(20, APPLY, PTR, 30);
        symbols[6].def.prim = prim_y; operator_node(21, PRIM_0, &symbols[6]);
        operator_node(30, LAMBDA, &symbols[7]); arena[30].class = BINDER;
        integer(31, HEAD, 42); /* f = lambda x.42: finite, complete code. */
        (++stack)->ptr = env; /* saved by the PTR20 that emitted descriptor11 */
        pc = arena + 21; argcount = 1; mode = HEADM; red_limit = 2;
        STEP("prim_y", prim_y());
        recursive_argument = arena[11].op.addr;
        snprintf(reconstruction, sizeof(reconstruction),
                 "{\"argument_class\":%d,\"argument_type\":%d,\"argument_target\":%ld,"
                 "\"code\":%ld,\"stack\":%ld,\"saved_env\":%ld,\"mode\":%d,\"argcount\":%d}",
                 arena[11].class, arena[11].type, (long)(recursive_argument-arena),
                 (long)(pc-arena), (long)(stack-controls), (long)(stack->ptr-arena), mode, argcount);
        /* Snapshot the sharing relation before red consumes the descriptor. */
        snprintf(alias_buffer, sizeof(alias_buffer),
                 "[{\"nodes\":[20],\"register\":\"pc\",\"target\":%ld}]", (long)(pc-arena));
        if (arena[20].op.addr != pc) strcpy(alias_buffer, "[]");
        STEP("resume_f", answer = red());
        snprintf(resumed, sizeof(resumed),
                 "{\"type\":%d,\"value\":%ld,\"stack\":%ld,\"reductions\":%lu,"
                 "\"binding\":%ld,\"binding_type\":%d,\"binding_target\":%ld,"
                 "\"marker_type\":%d,\"marker_target\":%ld,\"closure_code\":%ld,\"closure_env\":%ld}",
                 answer->type, answer->op.intval, (long)(stack-controls), reductions,
                 (long)(env-arena), env->type, (long)(env->op.addr-arena),
                 arena[197].type, (long)(arena[197].op.addr-arena),
                 (long)(arena[198].op.addr-arena), (long)(arena[199].op.addr-arena));
        /* Traverse the published argument itself, not just f, using the full
         * archived entry/dispatch path and a finite two-contraction quantum. */
        STEP("traverse_argument", answer = reduce(recursive_argument, arena + 60, arena + 200, 2, 0));
        printf("],\"result\":{\"reconstruction\":%s,\"recursive_graph\":", reconstruction);
        graph_nodes(20, 21);
        printf(",\"function_graph\":"); graph_nodes(30, 31);
        printf(",\"resumed\":%s,\"traversed_argument\":{\"type\":%d,\"value\":%ld,"
               "\"stack\":%ld,\"reductions\":%lu,\"limit\":%lu}}",
               resumed, answer->type, answer->op.intval, (long)(stack-controls), reductions, red_limit);
        finish(alias_buffer);
    } else if (!strcmp(id, "rec-q0")) {
        node reconstructed[3], *answer;
        char reconstruction[256], returned[256];
        int i;
        begin(10); pointer(40, HEAD, REC, 180); /* preserve STOP10 */
        pointer(180, HEAD, NOOP, 50); pointer(181, HEAD, NOOP, 190);
        pointer(182, HEAD, NOOP, 30); pointer(190, HEAD, REC, 180);
        pointer(30, BINDER, LETREC, 50); integer(31, BINDER, 1); arena[31].type = RUP;
        operator_node(50, LAMBDA, &symbols[7]); arena[50].class = BINDER;
        integer(51, HEAD, 42); /* complete binding: letrec x=42 in x */
        pc = arena + 40; mode = HEADM; red_limit = 0;
        STEP("inst_rec", inst_rec());
        for (i = 0; i < 3; i++) reconstructed[i] = arena[11 + i];
        snprintf(reconstruction, sizeof(reconstruction),
                 "{\"pc\":%ld,\"mode\":%d,\"stack\":%ld,\"saved_env\":%ld,"
                 "\"env\":%ld,\"binding_offset\":%d,\"marker_target\":%ld}",
                 (long)(pc-arena), mode, (long)(stack-controls), (long)(stack->ptr-arena),
                 (long)(env-arena), binding_offset, (long)(arena[199].op.addr-arena));
        /* Finish the q=0 return through RUP, LETREC, its binding child and JOIN.
         * The saved context198 belongs to LETREC11; JOIN restores exactly fs198. */
        init_stats(); stats = 1; /* archived bounded low-water observation */
        STEP("return_residual", answer = red());
        stats = 0;
        snprintf(returned, sizeof(returned),
                 "{\"root\":%ld,\"stack\":%ld,\"env\":%ld,\"binding_offset\":%d,"
                 "\"reductions\":%lu,\"limit\":%lu,\"minimum_fs\":%ld}",
                 (long)(answer-arena), (long)(stack-controls), (long)(env-arena),
                 binding_offset, reductions, red_limit, (long)(max_env-arena));
        /* Positive quantum traverses the published binding using THOR's atomic
         * LETREC shortcut, which returns42 without a counted contraction. */
        STEP("traverse_residual", answer = reduce(answer, arena + 60, arena + 200, 1, 0));
        printf("],\"result\":{\"nodes\":"); graph_nodes_at(reconstructed, 11, 13);
        printf(",\"reconstruction\":%s,\"binding_graph\":", reconstruction); graph_nodes(50, 51);
        printf(",\"returned_nodes\":"); graph_nodes(11, 13);
        printf(",\"returned_binding\":"); graph_nodes(15, 16);
        printf(",\"returned\":%s,\"traversed\":{\"type\":%d,\"value\":%ld,"
               "\"stack\":%ld,\"reductions\":%lu,\"limit\":%lu}}",
               returned, answer->type, answer->op.intval, (long)(stack-controls), reductions, red_limit);
        finish("[]");
    } else if (!strcmp(id, "equal-scratch")) {
        node *answer;
        begin(12); pointer(11, APPLY, PTR, 40); pointer(12, APPLY, PTR, 30);
        integer(30, APPLY, 1); integer(31, HEAD, 2);
        integer(40, APPLY, 1); integer(41, HEAD, 3);
        operator_node(50, PRIM_0, equal); pc = arena + 50; mode = HEADM; argcount = 2;
        (++stack)->ptr = env; (++stack)->ptr = env;
        STEP("prim_equal", prim_equal());
        /* Strict arguments are already normal graphs; restore their saved contexts
         * exactly as two inst_ptr/inst_join traversals would before EQUAL's callback. */
        stack -= 2; mode = RESULT;
        STEP("equal_convert", prim_equal());
        STEP("equal_star_split", prim_equal_star());
        STEP("red", answer = red());
        value_result(answer); finish("[]");
    } else if (!strcmp(id, "equal-star-wrap")) {
        begin(14); integer(11, APPLY, 1); arena[11].type = VAR;
        integer(12, APPLY, 0); arena[12].type = VAR;
        integer(13, APPLY, 2); operator_node(14, PRIM_0, equal_star);
        pc = primitive = arena + 14; mode = RESULT; red_limit = 0;
        STEP("prim_equal_star", prim_equal_star()); graph_result(11, 20);
        finish(pointer_alias(11, 12));
    } else if (!strcmp(id, "promote-left-pointer") || !strcmp(id, "promote-right-pointer")) {
        begin(14);
        integer(11, APPLY, 7); integer(12, APPLY, 7);
        integer(13, APPLY, 0); operator_node(14, PRIM_0, equal_star);
        if (!strcmp(id, "promote-left-pointer")) {
            pointer(12, APPLY, PTR, 30); integer(30, HEAD, 7);
        } else {
            pointer(11, APPLY, PTR, 30); integer(30, HEAD, 9);
        }
        pc = primitive = arena + 14; mode = RESULT;
        STEP("promote", prim_equal_star());
        STEP("retry", prim_equal_star());
        value_result(arena + 11); finish("[]");
    } else if (!strcmp(id, "ubv-equal") || !strcmp(id, "ubv-unequal")) {
        begin(10); env = fs = arena + 190; binding_offset = 2;
        /* Both labels belong to this one traversal coordinate: absolute 2/1. */
        integer(190, HEAD, 2); arena[190].type = UBV;
        integer(191, HEAD, 1); arena[191].type = UBV;
        integer(30, APPLY, 0); arena[30].type = VAR;
        integer(31, APPLY, !strcmp(id, "ubv-equal") ? 0 : 1); arena[31].type = VAR;
        operator_node(32, PRIM_0, equal); pc = arena + 30;
        event("context");
        STEP("first_variable", inst_var());
        STEP("second_variable", inst_var());
        mode = HEADM;
        STEP("prim_equal", prim_equal());
        if (!strcmp(id, "ubv-equal")) value_result(arena + 11);
        else graph_result(11, 13);
        finish("[]");
    } else if (!strcmp(id, "copy-shift")) {
        node *end;
        begin(50); pointer(10, APPLY, PTR, 30); pointer(11, APPLY, PTR, 30);
        integer(12, HEAD, 9); integer(30, APPLY, 1); integer(31, HEAD, 2);
        integer(40, HEAD, 666);
        STEP("copy_graph", end = copy_graph(arena + 10, arena + 60));
        if (end != arena + 64) bomb();
        STEP("shift_memory", end = shift_memory(arena + 60, end, arena + 80));
        graph_result(80, (int)(end-arena));
        snprintf(alias_buffer, sizeof(alias_buffer),
                 "[{\"nodes\":[30,60,61],\"target\":%ld},{\"nodes\":[80,81],\"target\":%ld}]",
                 (long)(arena[60].op.addr-arena), (long)(arena[80].op.addr-arena));
        finish(arena[80].op.addr == arena[81].op.addr && arena[60].op.addr == arena[61].op.addr &&
               arena[30].type == MARKER && arena[30].op.addr == arena[60].op.addr
               ? alias_buffer : "[]");
    } else if (!strcmp(id, "reduce-identity")) {
        node *answer;
        begin(10); integer(30, APPLY, 42); arena[31].type = LAMBDA;
        integer(32, HEAD, 0); arena[32].type = VAR;
        STEP("reduce", answer = reduce(arena + 30, arena + 10, arena + 200, 10, 0));
        value_result(answer); finish("[]");
    } else return 65;
    return 0;
}
