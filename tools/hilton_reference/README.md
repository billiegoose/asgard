# Executable functional THOR lifetime reference

```sh
uv run pytest -q tests/test_hilton_reference.py
uv run python -c 'from tools.hilton_reference.runner import run_case; print(run_case("atomic-child-return"))'
```

`run_case(case_id: str) -> dict[str, object]` builds and runs C in a **fresh
per-invocation temporary directory**, then removes the build. `CC` names one
compiler executable (default `cc`, not a shell command). Missing compiler,
compilation errors, abnormal exits, malformed output, and unknown IDs raise
`HiltonReferenceError`. Compilation/execution timeouts are failure guards, never
success conditions. No parser, editor, RED2 imports, installed C dependencies,
or cached reference executable are used. Concurrent calls share no mutable
build artifacts. This is verification tooling, **not an execution backend**.

## Authority and compatibility

`runner.py` reads the archived THOR files at invocation time. It includes the
original `LRS.H` layout and the actual `RED.C`, `PRIMS.C`, and `ARITH.C` bodies;
from `MAIN.C` it extracts only `copy_graph` and `shift_memory`. It does not
transcribe their algorithms. Three explicitly approved, narrowly bounded
PRIMS.C repairs are applied only in the temporary translation unit (below).
Function-entry probes report which archived bodies actually ran, including
nested reducer calls. Tests require the expected bodies
and verify that changing the archived JOIN restoration statement changes C
output and fails comparison. The report includes SHA-256 hashes of the original
source bytes. `authority.repairs_applied` lists the temporary-source repairs;
`repairs_exercised` reports repair sites actually reached. `execution` is
`repaired-C` for those cases and `archived-C` for untouched execution paths
(the shared executable still contains the listed repairs). Expected results
are **not available to the C executable**. This is not a blanket claim that
repaired cases execute unchanged historical semantics.

Exhaustive compatibility changes (temporary translation unit only):

* Combine sources into one translation unit, include uppercase `LRS.H` once,
  remove their includes, and use `compat.h` system headers. This avoids historical
  repeated tentative globals and case-sensitive `lrs.h` lookup issues.
* Select the archived SUN node layout, without DOS `huge`/IBM fields. Compile
  K&R definitions as GNU89. Supply forward declarations for void/pointer-returning
  functions; suppress legacy implicit-declaration, deprecated-time, comment,
  missing-return, and unknown-escape diagnostics. No pointer-returning function
  used by fixtures relies on implicit `int`.
* Insert `entered("file:symbol")` at function entry. Apart from the three
  enumerated repairs, no reducer statement is replaced or removed. Probes store at most 128 distinct names;
  overflow is fatal. These are host diagnostics, not a reclamation algorithm.
* Exclude `install_primitives`, interactive MAIN, and parser/prelude integration.
  Fixture symbols explicitly reference the archived primitive bodies.
  `symbol_lookup` accepts **only** the generated `%gv%` lambda name; another name
  aborts rather than silently inventing a definition.
* Replace terminal refresh/printing, statistics-time accumulation and debug-node
  printing with headless services. `debug=0`; `stats=0` except during the REC
  residual return, where archived bounded statistics measure the child fs
  low-water mark. `bomb` exits and the reducer's `longjmp` abort is caught as
  failure. `ftime` remains the platform function.
* Allocate one 256-node fixture arena and the archived-size control array.
  Offsets are within this fixture arena; they are not RED2 addresses.

The complete 20-case corpus passes address and undefined-behavior sanitizers;
these checks are mandatory tests, not optional skips. Four new hazard fixtures
first failed with C exit -11 against the originals. Regression tests disable
repairs and require sanitizer-reported failures for both asymmetric head
promotion directions and equal/unequal UBV indices; repaired runs must match
hand-derived results. Unhandled equality node tags now fail explicitly rather
than fall off a non-void function. This does not certify arbitrary C inputs.
`copy_graph` returns the **last occupied node**, despite its “first available”
source comment; fixtures and caller `shift_memory` use executable behavior.

## Evidence model and hand derivations

`cases.json` commits the result, alias/update relations, and **both** boundaries
at every named observation, including unchanged boundaries. Each record's
`derivation` calculates these without Python RED2. `compare_case` requires exact
result/alias/event equality and archived-body evidence. Tests remove every
output field and mutate every expected ws/fs event independently to show these
are mandatory, including `aliases: []`. Repair-dependent cases also require
exact repair attribution; deleting that evidence fails comparison.

Most fixtures deliberately start at an instruction/primitive boundary, with
explicit C nodes and typed registers/stacks. Events are fixture observation
boundaries, **not an every-instruction trace**. Setup changes between observations
are labelled (e.g. `parent`). `equal-scratch` supplies already-normal application
arguments: EQUAL's scratch reservation is observed, their two saved strict
contexts are removed as fixture setup, then the archived EQUAL callback and
EQUAL* build scratch code. The scratch computation and child return run through
archived `red()`, not an adapter comparison. `reduce-identity` additionally runs
the full `reduce()` entry/dispatch/reset path.

Key calculations:

* Child entry saves 200; closure takes two words and a path marker/binding takes
  two more: 200 → 198 → 196 → **200**, while HEAD JOIN contracts ws13 → 10.
* Older closure190 is outside child [178,180). JOIN writes42 to it, and the
  second CLOSURE observes that update without executing old code. `shared-value`
  records this update relation, not pointer identity between final scalar copies.
* PTR JOIN keeps ws13; lambda consumes exactly one descriptor and one environment
  slot; RUP consumes two descriptors but preserves two common REC contexts.
* Addition overwrites argument11. IF drops four spine words and balances both
  saved contexts. AND/OR decisive values drop two unused contexts; NOOP targets
  remain undemanded. These are local fixed-live-state fixtures, not general
  bounded-recursion claims.
* Y reuses complete original code20/21 (`PTR30; Y`) and resumes f30/31
  (`lambda x.42`) without tying a knot. Descriptor11 owns saved context200 on
  stack1, as after archived `inst_ptr`; Y retains it and ws11/fs200. The result
  snapshots the reconstructed PTR20, resumed pc30 alias, and retained context
  before consumption. Archived `red()` then consumes that context into closure
  cells198/199, bridges env200 != fs198 with MARKER197, binds CLOSURE196, and
  returns42 at11 with stack0 (Y + lambda = two contractions, fs196). Finally
  archived `reduce()` traverses the published argument20 itself with workspace60
  and quantum2, returning42 at61 with stack0 and restoring fs200. Both complete
  code graphs are reported. Removing either the Y operator or lambda body bombs
  in archived dispatch; changing the saved context changes the captured closure
  and fails comparison. This is a finite constant-function recursion fixture,
  not a claim of general bounded recursion.
* q=0 REC40 preserves workspace STOP10 and copies LETREC/RUP/VAR to11..13,
  bridging environment191 with MARKER199 and UBV198. The immediate snapshot
  retains RESULT/pc12, stack1/context198 and binding_offset1. Its complete
  binding50/51 is `lambda x.42`. Archived `red()` continues through RUP12 and
  LETREC11, pops context198 and enters the binding with JOIN14/saved fs198.
  Lambda50 allocates UBV197, copies to15, and INT42 copies to16. Returning
  through lambda and JOIN balances binding_offset and stack to0, restores
  exactly fs198 and publishes LETREC11->15. Archived bounded statistics report
  minimum fs197, proving the child really allocated before returning. ws16
  retains the non-atomic binding graph; q=0 performs zero contractions and
  returns the residual `letrec x=42 in x`, not a computed recursive value.
  Archived `reduce()` then traverses that published residual with workspace60
  and quantum1: the atomic LETREC shortcut binds42 at199, RUP removes the
  descriptor, and VAR0 returns42 at61 with stack0 and restored fs200 (zero
  counted contractions). Both immediate and returned code graphs are reported;
  removing the binding header or body fails in archived dispatch. This explicit
  REC fixture uses a finite constant binding, not arbitrary recursion.
* Application equality allocates 3 AND spine + 4 + 4 equality + 1 JOIN = 12
  scratch words, then resets to result11. q=0 wrapping allocates 3+3 words and
  yields residual EQUAL, not a Boolean.
* Copy of a three-word spine with two aliases of a two-word child occupies five
  words. Garbage40 is absent; source30 becomes forwarding MARKER→63. Shift to80
  rewrites both aliases to83. Neither routine itself changes ws/fs.

Results separately expose graph snapshots, environment boundary, and selected
control/auxiliary offsets. Diagnostic storage is bounded independently. Empty
aliases mean no shared pointer targets in the fixture's published observations;
scalar outcomes cannot carry graph aliases. Alias targets are read from C
memory, not inferred from Python results.

## Source-site inventory and variants

`reclamation-sites.json` lists path, symbol, arena, trigger, disposition,
representative `case_ids`, and exact line/text locations. `validate_inventory`
checks each location and containing function. Its complete comment/string-aware
source audit checks **every ws/fs mutation** (a superset of all rewinds/resets)
in RED/PRIMS/ARITH/MAIN in all seven snapshots; STRICT has no ARITH.C. Additional
records cover forwarding, relocation, sharing, control pops, focus replacement,
teardown, and non-functional variant state. Peer review should compare the
committed locations with the source, not mistake a source match for runtime proof.

Dispositions classify the mechanism, **not test coverage of every source arm**:
`parity` is the functional mechanism (or unchanged sibling body),
`representation-equivalent` denotes copying/relocation or host lifecycle rather
than an identical RED2 instruction, and `variant-out-of-scope` excludes differing
historical semantics. `case_ids` link representative technique evidence; an
empty list explicitly means no executed fixture. A primitive-add fixture does
not claim every arithmetic type combination was executed. REC reconstruction
now traverses LETREC's RESULT arm and its positive-quantum atomic binding arm,
not the allocating non-atomic REC-closure arm. Actual executed functions are
reported independently.

* **THOR** is the functional authority. Environment MARKER path bridges are not
  MAIN's temporary destructive copy-forwarding MARKER.
* **SNARL/SNARL** has the same functional reducer bodies, with branding/startup
  differences. Identical bodies are catalogued, not separately executed.
* **SNARL/EXPERIME** adds RPTR traversal without ordinary PTR context handling;
  that difference is excluded.
* **SNARL/OPT** changes nested lazy-structure equality to construct EQUAL* directly
  (different scratch size, with unchecked operand-pointer tests). Excluded, not
  silently substituted for THOR.
* **STRICT** uses the early `head`/SUSPEND representation. `jump_subgraph` does not
  save fs, JOIN does not restore it, and `reduce` has no final fs reset. These are
  substantive differences, not evidence for THOR return semantics.
* **DEC6/WORK** add existential variables, RESET/trails and unification heaps.
  Even their JOIN scalar tail rule differs (always subtract two, lacking THOR's
  HEAD-destination reset). Identical arithmetic functions are catalogued, but
  logic/unification/backtracking mechanisms are not imported or executed.

Archive and thesis originals remain read-only. This corpus proves the named
local C cases; it does not establish Python parity, arbitrary-input safety,
whole-program constant memory, or execution of the interactive lifecycle.

## Approved temporary-source UB repairs

`runner.REPAIRS` below is the exact original/replacement text log. Each original
fragment must match once, otherwise building fails. Tests undo precisely these
replacements and entry probes, then require every selected archived function
body to remain present verbatim. The archives themselves are never patched.

1. **equal-star-head-promotion**, PRIMS.C:730/735: the outer condition says
   *either* argument is PTR-to-HEAD; it does not make both operands pointers.
   Guard each individual dereference by its own tag. This preserves promotion,
   retry and context-pop behavior for valid pointer operands, while making the
   two previously undefined asymmetric inputs defined. `promote-left-pointer`
   compares PTR(INT7) with INT7 and gets true; `promote-right-pointer` compares
   INT7 with PTR(INT9) and gets false. Both preserve ws14/fs200 during promotion
   then contract to ws11 on retry. These outputs require repaired-C evidence.

2. **ubv-index-equality**, PRIMS.C:1003–1004: compare `op.index`, not an address
   manufactured from that index. Scope justification comes from THOR itself:
   RED.C:375/395/446/629 store absolute labels in `op.index`; :759/:764 convert
   them to relative VARs using `binding_offset - op.index`; :784–786 copy the
   UBV type/union unchanged in `inst_var`. The fixtures place both operands in
   **one traversal coordinate** (`binding_offset=2`, same environment190), then
   execute `inst_var` twice. Equal label2 yields true. Different free labels2/1
   retain residual EQUAL (they must not become false). This repair does not
   assert identity of labels from unrelated saved scopes; no cross-scope UBV
   comparison fixture is authorized here. DEC6/WORK:1154 also use `op.index`,
   but no logic semantics are imported; the THOR representation is the basis.

3. **nodes-equal-unsupported-tag**, PRIMS.C:1026–1029: add a fatal default to
   the existing switch, leaving all handled tags untouched. A fixture mutation
   replaces the two UBVs with NOOP29 and must fail with a diagnostic/exit72,
   never return an invented equality value. This trap has no successful
   `run_case` result. Repair diagnostics are bounded to three distinct names.

Exact replacements (including diagnostic probes):

### `equal-star-head-promotion`

Original:

```c
if (arg1->op.addr->class == HEAD) {
```

Replacement:

```c
repaired("equal-star-head-promotion");
      if ((arg1->type == PTR) && (arg1->op.addr->class == HEAD)) {
```

Original:

```c
if (arg2->op.addr->class == HEAD) {
```

Replacement:

```c
if ((arg2->type == PTR) && (arg2->op.addr->class == HEAD)) {
```

### `ubv-index-equality`

Original:

```c
case UBV:      return(((*arg1)->op.addr->op.index ==
                             (*arg2)->op.addr->op.index));
```

Replacement:

```c
case UBV:      repaired("ubv-index-equality");
                     return(((*arg1)->op.index == (*arg2)->op.index));
```

### `nodes-equal-unsupported-tag`

Original:

```c
                     else return(FALSE);

   }
}
```

Replacement:

```c
                     else return(FALSE);

      default: repaired("nodes-equal-unsupported-tag");
               fprintf(stderr, "reference: unsupported nodes_equal tag %d\n",
                       (*arg1)->type);
               exit(72);
   }
}
```
