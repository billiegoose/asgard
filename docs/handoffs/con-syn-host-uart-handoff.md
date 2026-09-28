# Concrete + Synthesizable RED2 host UART implementation handoff

Date: 2026-09-27
Branch: `main`
PGC top-level session: `1d19abf498921513`

## User goal

Implement the host interfaces for RED2 I/O in **Concrete (Con)** and **Synthesizable (Syn)** so interactive programs can use the same machine across host calls, with the eventual practical target of running `examples/breakout.thor` on both.

User explicitly deferred floating-point expansion. RISC-V-style float support can be a future extension; this slice should use integer math and must not depend on new FLOAT functionality.

Authoritative intended host primitives:

- `CLOCK`
- `UART-RX`
- `UART-TX`
- `UART-TX-BYTES`

Host calls trap exactly at primitive firing. The same RED2 machine resumes after the host operation. Host-boundary quantum refresh/recharge is allowed and is the intended scheduler behavior.

---

## Critical PGC protocol

For repo/local work, every top-level Poor Girl's Codex request must include:

```json
"session": "1d19abf498921513"
```

Tool requests must be the final content of the assistant response as one fenced `json` block. Local tools execute from the current `billiegoose/asgard` working directory. Do not edit sibling PipelineC repos.

Relevant tools: `read`, `find`, `tree`, `status`, `diff`, `edit`, `write`, `run`, `subagent`.

---

## Working tree state

At the last confirmed status, these files were modified/untracked:

- `.mise.toml`
- `scripts/run_syn.py`
- `src/machines/abstract_red2_machine/io_runtime.py`
- `src/machines/concrete_red2_machine/cli.py`
- `src/machines/concrete_red2_machine/io_runtime.py` (new)
- `src/machines/concrete_red2_machine/machine.py`
- `src/machines/synthesizable_red2_machine/machine.py`
- `src/machines/thor_interpreter/io_runtime.py`

No commit has been made yet.

Before doing anything destructive, run `git status --short --branch` and `git diff --check`.

---

# Implemented pieces

## 1. Abstract host dispatcher made reusable

File: `src/machines/abstract_red2_machine/io_runtime.py`

The private host dispatcher was renamed/publicized as:

```py
dispatch_red2_host_call(machine, call, host)
```

Semantics remain authoritative:

- `CLOCK` -> RED2 `INT(host.clock_ms())`
- `UART-RX` -> `NIL` if no byte ready, else `INT(byte)`
- `UART-TX` -> argument must be INT, emits `arg % 256`, returns NIL
- `UART-TX-BYTES` -> traverses PAIR/NIL RED2 byte list, emits bytes, returns NIL

`UART-TX-BYTES` uses the existing semantic graph traversal helper, including cycle/error checks.

Potential compatibility cleanup before final: search for imports of the old private `_dispatch_host_call`. If external/internal tests still expect it, add a compatibility alias rather than breaking them.

---

## 2. Text host + terminal cbreak support

File: `src/machines/thor_interpreter/io_runtime.py`

Changes landed:

- private `_Red2IoHost` renamed to `TextRed2IoHost`
- added `terminal_input_mode(stream)` context manager
- real TTY input is placed in cbreak mode so `UART-RX` sees keystrokes immediately without requiring Enter
- non-TTY streams are left unchanged

The context manager restores terminal settings in `finally`.

Potential compatibility cleanup: search for imports of `_Red2IoHost`; add alias if necessary.

---

## 3. Shared encoded host dispatcher for Con/Syn

New file: `src/machines/concrete_red2_machine/io_runtime.py`

It translates encoded machine pending-host state to the authoritative abstract host dispatcher:

```py
HOST_NAMES = {
    abi.HOST_CLOCK: "CLOCK",
    abi.HOST_UART_RX: "UART-RX",
    abi.HOST_UART_TX: "UART-TX",
    abi.HOST_UART_TX_BYTES: "UART-TX-BYTES",
}
```

Main helpers:

```py
encoded_host_call(state)

dispatch_encoded_host_call(
    codec,
    state,
    host,
    *,
    working_memory_limit,
)
```

The implementation decodes the architectural state, constructs an `AbstractRED2Machine` view, runs `dispatch_red2_host_call`, and re-encodes the returned atomic RED2 word.

This safely reuses the authoritative byte-list traversal without mutating reducer state.

---

## 4. Concrete resume + host CLI wiring

### Machine

File: `src/machines/concrete_red2_machine/machine.py`

`ConcreteRED2Machine.resume_host_call(result)` already existed and was robust. It validates:

- machine is suspended at FETCH
- pending host operation exists
- q > 0
- returned word is valid supported atomic shape
- reserved bits / closure / definition consistency
- direct host (`CLOCK`, `UART-RX`) shape has no argument
- strict host (`UART-TX`, `UART-TX-BYTES`) shape has matching encoded argument / pc

Resume semantics:

- direct host publishes at `fsp + 1`, decrements q, increments argcnt, resumes reverse
- strict host overwrites argument at pc, sets fsp=pc, decrements q, pc--
- pending host state clears
- capacity failure => graph/env collision

New method added:

```py
refresh_quantum(self, quantum: int) -> int
```

This validates the live machine is at a safe scheduler boundary and resets `q` without reconstructing a new machine.

### CLI

File: `src/machines/concrete_red2_machine/cli.py`

Now:

- accepts `--clock`
- constructs `TextRed2IoHost`
- runs one persistent `ConcreteRED2Machine`
- on HOST_CALL:
  - checkpoint
  - dispatch host call through shared encoded dispatcher
  - `resume_host_call`
  - `refresh_quantum(args.quantum)`
  - continue same machine
- wraps execution in `terminal_input_mode(sys.stdin)`
- suppresses final RED2 result printing if the program performed host output, so UART stdout is not polluted
- pure programs still print their result normally

Known successful Con smokes before the conversation ended:

```sh
uv run con --expr '(UART-TX 65)'
# stdout byte 65, rc 0

uv run con --expr '(+ 2 3)'
# stdout: 5\n, rc 0

uv run con --clock /tmp/red2-clock.txt --expr '(UART-TX (MOD (CLOCK) 256))'
# with clock file containing 65 -> byte 65

uv run con --expr '(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))'
# stdout bytes 65 66
```

Existing `tests/test_concrete_red2_host_calls.py` had 18 tests green after the Con machine changes.

---

# Synthesizable RED2 host work

## 5. Native host constants + CMD_RESUME

File: `src/machines/synthesizable_red2_machine/machine.py`

Added/implemented:

```py
FAULT_INVALID_RESUME = 7
HOST_UART_TX = 3
HOST_UART_TX_BYTES = 4
```

Added host staging registers:

```py
join_host_active: Reg[uint1_t]
join_host_op: Reg[uint3_t]
```

They are reset on RESET / LOAD_STATE / START paths.

`CMD_RESUME` is no longer `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`.

Resume validation now checks:

- packed word valid bit
- opcode/kind is allowed atomic (`INT`, `FLOAT`, `CHAR`, `SYM`)
- literals fit expected width and are nonzero where required
- reserved bits zero
- closure slot zero
- definition-valid consistency
- direct vs strict host pending-call shape
- strict pending argument decodes and matches pc
- machine has no existing red2/hw fault
- microstate is FETCH
- machine not halted
- pending host exists
- q != 0
- direct destination `fsp+1` fits graph and is before free-space

On valid resume:

- direct `CLOCK`/`UART-RX`: publish returned word at `fsp+1`, q--, argcnt++, pc to new result-1, direction reverse
- strict TX/TX_BYTES: publish returned word over pc argument, fsp=pc, q--, pc--
- pending host clears

Invalid resume => `FAULT_INVALID_RESUME`.
Capacity failure => `FAULT_GRAPH_ENV_COLLISION`.

---

## 6. Native strict host primitive firing

Syn metadata dispatch now recognizes host metadata for `UART-TX` and `UART-TX-BYTES`.

Direct scalar / EP-return / JOIN-return strict host cases were wired so host calls suspend at the semantic firing boundary rather than faulting as an unsupported scalar.

Key behavior:

- q==0 suppresses host firing at the primitive boundary
- q>0 stages pending host state
- JOIN host firing waits until result publication/frame restoration is safely complete
- EP-return host firing preserves publication-before-restore ordering

Known successful native checkpoints before later list work:

```text
(UART-TX 65)                         host 3 arg 5  pc 4  fsp 5  q 100
(UART-TX (+ 64 1))                  host 3 arg 9  pc 8  fsp 9  q 99
(UART-TX ((LAMBDA (x) (+ x 1)) 64)) host 3 arg 11 pc 10 fsp 11 q 98
(CLOCK)                              host 1 arg 0
(UART-RX)                            host 2 arg 0
```

These matched Concrete scalar checkpoints/status.

---

## 7. Syn CLI host loop

File: `scripts/run_syn.py`

Now intended to:

- accept real `--clock`
- use `TextRed2IoHost`
- use one persistent SynthesizableRED2Machine simulation
- on `STATUS_RUNNING`, issue `CMD_CLOCK`
- on `STATUS_HOST_CALL`:
  - checkpoint RAM/state
  - dispatch host call through `dispatch_encoded_host_call`
  - issue `CMD_RESUME` with encoded returned word
  - then `CMD_RECHARGE(value=args.quantum)`
  - continue
- pure programs print result
- programs with host calls suppress final result text
- wrap stdin in `terminal_input_mode`

Known smokes that had worked before import-path instability:

- `(UART-TX 65)` -> byte 65
- `(UART-TX (+ 64 1))` -> byte 65
- `(+ 2 3)` -> `5`
- `CLOCK` feeding UART -> expected byte

The remaining operational issue is **pypeline import resolution** described below.

---

# CONS / nested byte-list semantic repair

`UART-TX-BYTES` exposed a pre-existing Synthesizable RED2 gap: native `CONS` contraction was not implemented, so even pure `(CONS 65 NIL)` faulted before host dispatch.

This was not a host-dispatch bug.

## 8. Metadata representation for CONS

`red2_literal_meta_t` already has structural metadata fields.

Constants:

```py
STRUCT_ROLE_NONE = 0
STRUCT_ROLE_SELECTOR = 1
STRUCT_ROLE_CONS = 2
STRUCT_ROLE_SELECTOR_RESULT = 3
```

But `scripts/run_syn.py::_literal_metadata()` was not emitting a CONS metadata row.

Patch added:

```py
cons = entry("CONS")
cons["struct_role"] = STRUCT_ROLE_CONS
cons["struct_tag_id"] = codec.literal_id("PAIR")
```

Also imported `STRUCT_ROLE_CONS` in `run_syn.py`.

This is important: before this patch a saved `CONS` primitive scanned the whole table and fell through to unsupported native execution.

---

## 9. Native CONS contraction implementation

Added private register:

```py
struct_cons_active: Reg[uint1_t]
```

Reset on RESET / LOAD_STATE / START.

Metadata scan now recognizes:

```py
join_meta_is_struct_cons = join_meta_struct_role == STRUCT_ROLE_CONS
```

For a saved binary CONS at q>0, native Syn now reconstructs the same PAIR layout as Concrete.

Concrete reference semantics for `(CONS left right)` at the firing boundary:

```text
base        = STRUCT PAIR
base + 1    = right/CDR descriptor
base + 2    = left/CAR descriptor
base + 3    = head VAR 0 terminator
```

Inline/non-pointer operands are materialized as head values in fresh roots, with descriptors pointing at them.
APP stays APP(target).
APP_VAR becomes APP_VAR(index+1).
q decrements once.

The Syn implementation reuses STRUCT copy microstates transactionally for this bounded 4/5-write construction.

### Proven behavior after patch

```text
(CONS 65 NIL)                    rc 0, prints [65]
(CONS 65 (CONS 66 NIL))          rc 0, prints [65 66]
(UART-TX-BYTES (CONS 65 NIL))    rc 0, outputs byte 65
```

Initially nested TX-BYTES still faulted during publication of the already-built nested STRUCT; that was repaired separately below.

---

## 10. CONS scratch parity fix (`s_a`)

The first post-CONS lockstep mismatch was only `s_a`.

Concrete leaves:

- inner CONS contraction: `s_a = 24`
- outer CONS contraction: `s_a = 20`

Rule is the ordinary JOIN publication scratch result (`join_result_address + 1` in this path).

Patch added at CONS completion:

```py
s_a = join_result_address + 1
```

After this, commits 19 and 20 of the nested UART byte-list program matched Concrete exactly in scalar architectural state.

---

# Generic publication repair for nested host byte lists

## 11. Root cause of nested UART-TX-BYTES failure

Program:

```thor
(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))
```

After CONS fixes, both list contractions succeeded.

Concrete at commit 21 did only this architectural parent change:

```text
memory[12]: APP(2) -> APP(15)
pc=12
fsp=25
c=0
q=1998
s_a=16
pending_host_op=4
pending_host_argument=13
```

The full list graph rooted at address 15 was already valid and preserved.

Syn instead routed the multiword STRUCT through the older narrow `MICRO_JOIN_STRUCT_PREFLIGHT_*` publisher. It failed at:

```text
MICRO_JOIN_STRUCT_PREFLIGHT_TARGET = 105
hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
```

because a nested STRUCT target was treated as requiring the later generic walker.

This was exactly the wrong path for the host boundary.

## 12. Host JOIN result now uses generic publication

A patch was applied to route the host JOIN result through the already-existing generic transactional publication engine (`MICRO_PUB_EXEC`, `PUB_RESUME_JOIN`) instead of the narrow STRUCT-specific publisher when needed.

The generic launch template mirrors existing launch sites and sets:

```py
pub_generation += 1
pub_sp = 1
pub_value = 0
pub_launch_root = join_result_address
pub_interval_start = free_space
pub_interval_stop = join_frame_free_space
pub_phi = phi
pub_resume_kind = PUB_RESUME_JOIN
pub_current_task = PUB_TASK_GRAPH(join_result_address)
...
pub_destination = fsp + 1
join_preserve_fsp = 1
join_published_root = join_result_address
microstate = MICRO_PUB_EXEC
```

Do not replace this with a host-specific unchecked pointer shortcut. The generic walker preserves the established transaction/failure-atomicity model.

### Strong acceptance evidence

After the generic-publication patch, lockstep reached the **exact same suspended host-call checkpoint** as Concrete for:

```thor
(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))
```

Observed final lockstep state:

```text
pc=12
fsp=25
env=247
c=0
direction=reverse
q=1998
phi=0
free_space=247
argcnt=2
prim_id=0
fire=0
s_a=16
s_d=0
halted=0
pending_host_op=4              # UART-TX-BYTES
pending_host_argument=13       # encoded optional address for arg at 12
```

The lockstep runner reported success through program commit 21.

This is the most important latest semantic checkpoint.

---

# Remaining immediate blocker: `run_syn.py` pypeline import instability

There are two things named `pypeline` in the pinned sibling checkout:

Correct runtime module:

```text
../PipelineC-pypeline-red2-pinned/src/pypeline.py
```

It contains `sim_call` and `sim_reset`.

Wrong package shadowing it:

```text
../PipelineC-pypeline-red2-pinned/include/pypeline/__init__.py
```

It does **not** export `sim_call`.

Failure seen repeatedly:

```text
ImportError: cannot import name 'sim_call' from 'pypeline'
(.../PipelineC-pypeline-red2-pinned/include/pypeline/__init__.py)
```

Current `scripts/run_syn.py` bootstrap had been observed as:

```py
checkout_paths = [
    str(root / "src"),
    str(root / "include"),
    str(root / "include" / "pypeline"),
]
sys.path[:0] = [value for value in checkout_paths if value not in sys.path]
```

In some clean probes this correctly resolved `src/pypeline.py`; in other launcher environments an existing `PYTHONPATH` / already-present path caused the include package to win.

### Required next fix

Make bootstrap deterministic.

Preferred simple direction:

1. remove existing occurrences of the pinned checkout's `src`, `include`, and `include/pypeline` from `sys.path`
2. insert `root/src` at index 0
3. add only the include path(s) actually needed by native imports, **after** `src`
4. do not put `include/pypeline` itself ahead of `src`
5. immediately verify:

```py
import pypeline
assert Path(pypeline.__file__).resolve() == (root / "src" / "pypeline.py").resolve()
assert hasattr(pypeline, "sim_call")
```

Do not edit the pinned PipelineC sibling repo.

A previous direct probe with explicit ordering showed:

```text
/Users/billie/code/billiegoose/PipelineC-pypeline-red2-pinned/src/pypeline.py
sim_call True
```

---

# Tests / acceptance work still needed

## 13. Add regression coverage

### Syn semantic regression

Add a focused regression for nested CONS publication into host suspension:

```thor
(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))
```

Expected pre-dispatch host checkpoint must match Concrete:

```text
pending_host_op == HOST_UART_TX_BYTES
pending_host_argument == encode_optional_address(12) == 13
pc == 12
fsp == 25
c == 0
q == 1998
s_a == 16
```

Also keep direct pure CONS regressions:

```thor
(CONS 65 NIL)
(CONS 65 (CONS 66 NIL))
```

### Native resume tests

Add/verify low-level tests for:

- direct CLOCK resume with INT result
- strict UART-TX resume
- strict UART-TX-BYTES resume
- invalid CMD_RESUME when no pending host -> `FAULT_INVALID_RESUME`
- invalid strict resume with mismatched argument/pc
- capacity fault for direct resume destination

### CLI tests

Con and Syn should cover:

- pure result still prints normally
- `UART-TX` outputs exact byte and no trailing result
- `UART-TX-BYTES` outputs exact bytes
- deterministic `CLOCK` via temp latest-value file
- `UART-RX` echo using an IO expression / piped stdin

Likely echo expression to verify from existing examples/primitives before hardcoding:

```thor
(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))
```

Search existing tests/examples for canonical syntax first.

---

# Ruff / formatting issue

Targeted Ruff had one known remaining issue in `scripts/run_syn.py`:

```text
B905 zip() without explicit strict=
line ~274
```

Code was approximately:

```py
zip(original_call.__code__.co_freevars, original_call.__closure__ or ())
```

Use `strict=True` if those lengths are an invariant (likely), or `strict=False` if intentionally tolerant. This looked pre-existing but became part of the targeted lint surface.

Do not mass-format/rewrite historical `ConcreteRED2Machine` lint backlog.

Run at minimum:

```sh
uv run ruff check \
  scripts/run_syn.py \
  src/machines/abstract_red2_machine/io_runtime.py \
  src/machines/concrete_red2_machine/cli.py \
  src/machines/concrete_red2_machine/io_runtime.py \
  src/machines/thor_interpreter/io_runtime.py

git diff --check
```

For `machine.py`, prefer focused checks / py_compile unless the repo's historical lint baseline is known clean.

---

# `.mise.toml`

Tasks were updated so Con/Syn expose `--clock`.

Last observed relevant entries:

```toml
[tasks.con]
...
flag "--clock <path>" help="latest-value millisecond clock source"
...
uv run con "${usage_file?}" --quantum "${usage_quantum?}" ${usage_verbose:+--verbose} ${usage_clock:+--clock "$usage_clock"}

[tasks.syn]
...
flag "--clock <path>" help="latest-value millisecond clock source"
...
uv run python scripts/run_syn.py ${usage_file:+"$usage_file"} ${usage_expr:+--expr "$usage_expr"} --quantum "${usage_quantum?}" ${usage_verbose:+--verbose} ${usage_clock:+--clock "$usage_clock"}
```

Thor already has shell `stty` handling; Con/Syn CLIs use `terminal_input_mode` directly.

Validate TOML/task syntax before final commit.

---

# Breakout blocker: Synthesizable graph size

Even with host I/O complete, current Syn fixed graph RAM is too small to load Breakout.

Current machine constants were:

```py
GRAPH_WORDS = 256
CONTROL_WORDS = 256
GRAPH_ADDR_BITS = 8
```

Measured loader behavior for `examples/breakout.thor`:

```text
256 words   -> FAIL
512         -> FAIL
1024        -> FAIL
4096        -> succeeds, but only ~366 working words left
8192        -> succeeds, ~4462 working words available
```

For 4096:

```text
working_limit ~366
root_fsp ~59
metadata rows ~50
```

For 8192:

```text
working_limit ~4462
root_fsp ~59
```

Important hardware-resource caveat: Syn has more graph-sized scratch RAMs than just graph RAM, including publication/task/memo structures. Blindly raising `GRAPH_WORDS` to 8192 may exceed Basys 3 resources.

The Basys 3 Artix-7 has limited BRAM, and 8192 x 128-bit graph RAM alone is ~1 Mbit before scratch structures.

Therefore separate these acceptance levels:

1. **Simulator functional target:** enough graph capacity to load/run Breakout.
2. **Basys 3 synthesis target:** resource-aware redesign/sizing may be required.

Do not claim physical-board Breakout fit until an actual synthesis/resource report exists.

Also audit this known hardcoded graph-size assumption before changing `GRAPH_ADDR_BITS`:

```py
has_successor = fsp[GRAPH_ADDR_BITS - 1 : 0] != 255
```

That must become parameterized (`GRAPH_WORDS - 1` or equivalent width-safe logic).

Many other slices already use `GRAPH_ADDR_BITS` correctly.

---

# Latest semantic trace for nested UART bytes

For:

```thor
(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))
```

Concrete/Syn matched through the two CONS contractions after fixes.

Important commits:

### Commit 19: inner CONS

Expected / matched:

```text
pc=18
fsp=24
c=2
q=1999
s_a=24
```

Concrete memory changes:

```text
19 -> STRUCT PAIR
20 -> APP 23
21 -> APP 24
22 -> VAR 0 head
24 -> INT 66 head
```

### Commit 20: outer CONS

Expected / matched after s_a fix:

```text
pc=14
fsp=25
c=1
q=1998
s_a=20
```

Concrete memory changes:

```text
15 -> STRUCT PAIR
16 -> APP 19
17 -> APP 25
18 -> VAR 0 head
25 -> INT 65 head
```

### Commit 21: host boundary publication

Concrete only changes:

```text
12: APP 2 -> APP 15
```

and suspends:

```text
pc=12
fsp=25
c=0
q=1998
s_a=16
pending_host_op=4
pending_host_argument=13
```

After the generic publication routing patch, Syn lockstep reached this exact checkpoint successfully.

This proves the reducer-side nested byte-list + strict host suspension semantics are now essentially correct at this boundary.

---

# Immediate next sequence

1. **Fix `scripts/run_syn.py` pypeline import bootstrap deterministically.**
2. Run actual CLI smoke:

```sh
env -u PYTHONPATH uv run python scripts/run_syn.py --expr '(UART-TX 65)'
env -u PYTHONPATH uv run python scripts/run_syn.py --expr '(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))'
env -u PYTHONPATH uv run python scripts/run_syn.py --expr '(+ 2 3)'
```

Expected byte-list stdout is exactly bytes `65 66` and rc 0.
3. Verify `CMD_RESUME` after nested host dispatch actually resumes and reaches COMPLETE without corrupting the list graph.
4. Add permanent regressions for nested CONS + host publication + resume.
5. Run focused existing Syn suites, especially struct/publication/quantum/host-related tests.
6. Run Con host tests.
7. Search and optionally preserve aliases for renamed private host classes/functions.
8. Fix Ruff B905 and `git diff --check`.
9. Decide how to handle Syn graph size for Breakout simulator acceptance. If changing graph size in this same commit becomes risky/resource-heavy, it may deserve a clearly separated follow-up, but user explicitly wants to reach playable Breakout eventually.
10. Once green, inspect full diff carefully and commit. Suggested commit message:

```text
Implement RED2 host UART interfaces
```

---

# Useful commands / environment notes

Correct pinned Pypeline runtime lives at:

```text
../PipelineC-pypeline-red2-pinned/src/pypeline.py
```

A manual environment that previously worked for direct probes was:

```sh
export PYTHONPATH="../PipelineC-pypeline-red2-pinned/src:src/machines:src/lib:scripts${PYTHONPATH:+:$PYTHONPATH}"
```

But the final CLI must not require this workaround; fix bootstrap in `run_syn.py`.

When testing raw bytes, use something like:

```sh
... >/tmp/out 2>/tmp/err
od -An -t u1 /tmp/out
cat /tmp/err
```

Avoid shell command substitution for arbitrary binary UART output.

---

# Design principles to preserve

- One RED2 machine per run; do not recreate the machine around every host call.
- Host call is a semantic trap at primitive firing.
- Resume must be validated and failure-atomic.
- Publication-before-restore ordering matters for JOIN/EP paths.
- q==0 reaches the primitive boundary but suppresses semantic host firing.
- Use the existing generic transactional publication walker for complex graph publication rather than unchecked host-specific shortcuts.
- Keep FLOAT expansion out of scope for this slice; existing bounded float handling may remain.
- Do not modify sibling PipelineC repositories.

---

## Final known-good milestone

The strongest latest result is:

> Synthesizable RED2 now constructs nested CONS/PAIR lists correctly and, after routing the complex host argument through the generic publication walker, reaches the exact same `UART-TX-BYTES` suspended architectural checkpoint as Concrete for `(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))`.

The next chat should start with the `run_syn.py` import-bootstrap fix, then execute the real host dispatch/resume path and turn the proven lockstep behavior into permanent tests.
