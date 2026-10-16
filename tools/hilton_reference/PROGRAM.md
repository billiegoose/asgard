# Run Hilton's archived C system

From the repository root:

```sh
uv run python -m tools.hilton_reference.program --expr '(+ 2 3)'
uv run python -m tools.hilton_reference.program \
  --load archives/SNARL/OPT/PAP.LAM --expr '(f 5)'
```

The first prints `5`; the second loads Hilton's archived factorial definitions
and prints `120`. The executable is `build/hilton-horse/horse`. Each invocation
rebuilds it from the archive and writes `horse.c`, `compiler.log`, and a
`manifest.json` containing source/binary hashes and the exact compiler command.
Only a native C compiler and the project's Python environment are required.
Use `--build-only` to build without running and `--file path.lam` for a source
file with a final expression. The input syntax is historical: `(define name
expression)`, and `rec` is the primitive called `Y` in Asgard. Interactive
terminal commands/editor are not provided; use the runner's options.

## Graphs and execution traces

```sh
uv run python -m tools.hilton_reference.program \
  --expr '((lambda (x) (+ x x)) (+ 20 1))' \
  --graphs build/hilton-horse/graphs.jsonl \
  --trace build/hilton-horse/trace.jsonl
```

Graph JSONL contains the compiled graph and reduced/residual graph, their roots,
static definitions, node classes/types/operands, and reduction/memory statistics.
Pointer operands are offsets into the C node arena rather than process addresses.
An offset of `-1` identifies a pointer outside that arena, such as `prim_y`'s
static temporary instruction.
Classes preserve the original `APPLY=1`, `HEAD=2`, and `PAIR=4` bits. Repeated
pointer targets expose sharing directly. The compiler dump excludes the unused
workspace gap following the problem graph.

The instruction trace includes the current instruction, graph workspace,
environment words, `pc`, `ws`, `fs`, `env`, mode and control-stack depth. It is
limited to the first 1,000 instructions by default. `--trace-limit N` changes
that limit; a final record explicitly reports truncation. Trace limits do not
stop execution. Diagnostic snapshots observe memory and do not reclaim it.

```sh
uv run python -m tools.hilton_reference.compare \
  --hilton-expr '((rec (lambda (self n) (if (= n 0) 0 (self (- n 1))))) 100)' \
  --asgard-expr '((Y (LAMBDA (self n) (if (= n 0) 0 (self (- n 1))))) 100)' \
  --memory-words 2048 --output build/hilton-horse-compare/countdown
```

This saves both inputs, compiled/result graphs, instruction/environment traces,
C stdout/stderr, and `comparison.json`. Each machine receives the same arena
size and contraction budget. Layout, static definitions and contraction
accounting can differ: offsets and instruction numbers are local to each
machine. Equal printed results do not prove graph isomorphism or general parity.
The comparison runner currently handles pure computations and one quantum.

## Quantum-driven reconstruction and reuse

```sh
uv run python -m tools.hilton_reference.program \
  --expr '((rec (lambda (self n) (if (= n 0) 0 (self (- n 1))))) 100)' \
  --memory-words 256 --quantum 20 --passes 100 \
  --graphs build/hilton-horse/countdown-quanta.jsonl
```

At quantum exhaustion, archived `red()` continues traversal without further
contractions and returns a residual graph. `--passes` restarts that residual
using the archived `copy_graph` and `shift_memory` sequence from MAIN's
`LAM_RED` branch, then archived `reduce()`. It prints each residual and stops
early when a pass uses less than its budget (or after the requested number of
passes). `--quantum 0` reconstructs without contracting; `--compile-only` skips
the reducer entirely.

The countdown above completes in **31 passes**, peaking at **32 environment
words**, with a 256-word arena. A single quantum of 100,000 exhausts that arena;
with 2,048 words the single-pass C run completes but peaks at **805 environment
words**. Asgard's reference RED2 also finishes in 31 passes at quantum 20 and
256 words, peaking at 22 environment words. Its single-pass 2,048-word run peaks
at 505 environment words. These are observed examples, not general memory
bounds. Asgard reconstruction errors at quanta 5 and 10 remain unresolved.

This confirms that reconstruction/restart is materially involved in memory
reuse. Simply resetting the budget of a live machine bypasses that boundary.

## What is executed and what is adapted

The build reads `archives/THOR/` without modifying it, including its original
node layout, generated PCYACC parser/compiler, reducer, primitives, arithmetic,
prelude, and expression printer. It also includes the archived `rep_loop`,
`copy_graph`, `shift_memory`, `struct_def`, `load_file`, and timing accumulation.
The modern driver supplies process lifecycle, batch output, and observations.
It does not implement a replacement parser or reducer.

Porting changes are applied only to the generated translation unit:

* Combine source files, remove their obsolete includes, select the archived
  `SUN` layout, and compile K&R definitions as GNU89 with correct declarations.
* Replace curses/editor services with headless stderr output. Errors fail the
  process. A syntax error at EOF also returns failure.
* Pass a writable copy to the archived symbol lookup, which uppercases its
  input; historical primitive names include string literals.
* Convert only the printer's `<varargs.h>` entry point to ANSI varargs.
* Add sentinel storage to the PCYACC stacks so their initial `[-1]` pointers
  stay inside allocated storage, and correct its upper-bound overflow guard.
* Insert one observation hook before each archived instruction dispatch.
* Apply the three previously documented PRIMS.C repairs from
  [the fixture harness](README.md#approved-temporary-source-ub-repairs).
  Exercised repairs are reported on stderr. The manifest records all applied
  repairs; this is not an assertion that every archived input is free of UB.

The complete runner is covered by `tests/test_hilton_program.py`; the existing
68-test archived-body harness is unchanged. The 100-step countdown also passes
address/undefined-behavior sanitizers with process-lifetime allocation leak
checking disabled. This port does not yet supply the original curses UI or
host I/O extensions introduced by Asgard.
