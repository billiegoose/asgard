# Plan: Synthesizable RED2 to Fibonacci

## Goal

Make the current Synthesizable RED2 Machine execute `examples/fibonacci.thor` wholly through its native RED2 hardware state machine and produce the same result as the THOR, Abstract RED2, and Concrete RED2 implementations.

For the checked-in example:

```thor
fib == (lambda (n)
  (letrec ((fib-iter
            (lambda (i current next)
              (if (= i 0)
                  current
                  (fib-iter (1- i) next (+ current next))))))
    (fib-iter n 0 1)))

fib-six == (fib 6)

fib-six
```

the required result is:

```text
8
```

Fibonacci is the milestone, not the debugging unit. Every missing semantic case discovered on the way must first be reduced to the smallest useful witness and added as a parity regression.

## Starting point

Baseline: post-package-migration `main` at `8641cfe`.

Current source architecture:

```text
src/
  lib/
    thor/
    red2/

  machines/
    thor_interpreter/
    abstract_red2_machine/
    concrete_red2_machine/
    synthesizable_red2_machine/
```

Relevant current files:

```text
src/lib/red2/compiler.py
src/lib/red2/instructions.py

src/machines/abstract_red2_machine/
src/machines/concrete_red2_machine/
src/machines/synthesizable_red2_machine/machine.py

scripts/run_syn.py
scripts/check_syn.py
scripts/check_syn_sim.py

tests/test_concrete_red2_*.py
tests/test_pipelinec_vectors.py
tests/test_synthesizable_red2_static.py

examples/fibonacci.thor
```

The removed `.red2` binary format and compile CLI are not part of this plan and must not be reintroduced.

The architectural roles are fixed:

```text
THOR source
    |
    v
red2.compiler
    |
    +-------------------+
    |                   |
    v                   v
Abstract RED2      Concrete RED2
faithful oracle    architectural oracle
                         |
                         v
                 Synthesizable RED2
                 hardware realization
```

For Synth work, Concrete RED2 is the immediate transition-level oracle. Abstract RED2 remains the semantic authority above it.

`RED2_SYNTH_SEMANTICS_COMPLETE` remains `0`.

The native runner currently also explicitly reports two unrelated unfinished runtime facilities:

* halted-residual quantum recharge/relinearization
* native host-call `CMD_RESUME`

Neither is required merely to establish pure Fibonacci execution if the program is run with a sufficient initial quantum.

The current Synth lookup machinery also still contains explicit `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` fallthroughs for terminal `VAR` and `APP_VAR` bindings that are neither UBV nor currently-shareable atomic values. Closure and recursive bindings are therefore an immediate area to investigate, but the plan must prove the actual first divergence before changing them.

## Scope discipline

This is a semantic-completion plan to a specific pure-program milestone.

Do not use Fibonacci itself as a giant debugging loop. Do not redesign RED2, change the package architecture, restore serialization, work on Basys 3 transport, or broaden this into complete host IO/resume support.

Do not set:

```python
RED2_SYNTH_SEMANTICS_COMPLETE = 1
```

merely because Fibonacci works. That flag requires the complete promised Synth semantic surface, which is a larger acceptance criterion.

PipelineC changes are also out of scope unless a correct RED2 transition cannot be expressed through the currently pinned frontend. A hardware semantic bug and a PipelineC frontend/scalability bug must be diagnosed separately.

---

## Task 1: Freeze the post-migration execution baseline

Before implementing anything, record the actual current behavior rather than carrying forward assumptions from the pre-migration tree.

Run the normal test suite and the canonical implementations over a small execution ladder:

```text
(+ 20 22)

(CAR {PAIR 42 99})

((LAMBDA (x) 7) 41)

((LAMBDA (x) x) 41)

((LAMBDA (x) (+ x 1)) 41)

examples/fibonacci.thor
```

For each relevant program, record:

```text
thor result/status
abs result/status
con result/status
syn result/status
syn red2_fault
syn hw_fault
syn microstate
syn committed-transition count
```

Confirm that the package migration did not itself alter the semantic boundary.

Also run the existing native hardware parity checker and PipelineC frontend-only gate.

Acceptance:

```text
- ordinary pytest baseline is green
- existing Synth native parity remains green
- PipelineC still accepts and emits the current hardware top
- smallest currently failing pure THOR witness is known exactly
- failure is localized to a particular committed transition or pre-commit microstate
```

No semantic implementation changes belong in this task.

---

## Task 2: Add program-level Concrete ↔ Synth committed-state lockstep

Extend the existing native simulator harness in `scripts/check_syn_sim.py` rather than inventing a second hardware test framework.

The script already knows how to:

```text
encode Abstract/Concrete RED2 state
load native memories and registers
clock Synth to its next commit
compare individual architectural checkpoints
detect RED2 faults and hardware faults
```

Add a helper that accepts a THOR expression/program, builds the normal compiled RED2 machine, and advances Concrete and Synth commit-by-commit.

At each commit compare all architecturally meaningful state represented by the ABI, including at least:

```text
pc
fsp
env
free_space
q
phi
argcnt
direction
prim
fire
halted/status
control_top
pending host state
published graph changes
published control changes
```

The failure diagnostic must identify the **first differing commit** and, when Synth faults before that commit, the failing microstate and relevant fetched/binding words.

The program-level harness must use the normal `red2.compiler` / machine loading path. It must not hand-construct a special graph for the milestone tests.

Acceptance:

```text
((LAMBDA (x) 7) 41)
```

can be driven through complete Concrete ↔ Synth program lockstep, and the current smallest failing bound-variable program produces a useful first-divergence report.

---

## Task 3: Complete bound-variable lookup for real lambda bodies

Start from the smallest failing witness established by Tasks 1–2.

The important progression is expected to include cases like:

```text
((LAMBDA (x) x) 41)

((LAMBDA (x) (+ x 1)) 41)

((LAMBDA (x) (+ x x)) 21)

(((LAMBDA (x)
    (LAMBDA (y) (+ x y)))
  20)
 22)
```

Do not implement these by special-casing their compiled shapes.

Use the Concrete machine to derive the exact required semantics for terminal `VAR` and `APP_VAR` lookup when the resolved binding is:

```text
UBV
atomic scalar
undefined/passive symbol
closure
recursive binding / RECP-related value
environment-path indirection
```

The current Synth code already handles UBV and shareable atomics and explicitly faults for remaining binding classes. Implement only the cases demonstrated by Concrete, preserving:

```text
PNP traversal
environment lookup depth
scratch publication
sharing semantics
direction changes
q charging
phi/argcnt changes
control-stack behavior
failure atomicity
graph/environment collision checks
```

Each newly supported binding class gets a minimal native parity regression before moving on.

Acceptance:

```text
((LAMBDA (x) (+ x 1)) 41)
```

returns `42` in Synth and matches Concrete at every committed architectural checkpoint.

The lexical-capture example above must also return `42`.

---

## Task 4: Prove nested application and closure re-entry

Fibonacci does not merely read a scalar variable. It repeatedly invokes functions reached through environments.

Add a small ladder that distinguishes:

```text
bound scalar lookup
bound closure lookup
closure capture
closure invocation
closure invocation whose argument is itself a looked-up variable
multiple invocations of the same closure
```

Useful witnesses should include equivalents of:

```thor
((lambda (f) (f 41))
 (lambda (x) (+ x 1)))
```

and:

```thor
(((lambda (x)
    (lambda (f) (f x)))
  41)
 (lambda (n) (+ n 1)))
```

The exact normalized spelling should follow the existing parser/compiler conventions.

Exercise both `VAR` and `APP_VAR` paths where the compiler produces them.

Acceptance:

```text
- closure-valued variables no longer enter HW_FAULT_EXECUTION_NOT_IMPLEMENTED
- captured environments survive subgraph entry/JOIN correctly
- repeated closure calls do not corrupt/reclaim live environments
- all cases remain commit-lockstep identical to Concrete
```

---

## Task 5: Establish Fibonacci's primitive/control prerequisites

Before adding recursion, establish the pure computation inside one Fibonacci iteration.

Test the actual primitive/control combination used by `examples/fibonacci.thor`:

```text
=
1-
+
IF
```

Use bound variables rather than only literal primitive arguments.

Construct a non-recursive equivalent of a single iteration, e.g. behavior corresponding to:

```text
i       = 3
current = 5
next    = 8

(1- i)            => 2
(+ current next)  => 13
(= i 0)           => false
```

Then exercise both branches of:

```thor
(if (= i 0)
    current
    ...)
```

This task is complete only if the primitive operands arrive through the same variable/environment machinery Fibonacci uses.

Acceptance:

```text
- decrement of looked-up integer matches Concrete
- addition of two looked-up integers matches Concrete
- equality of looked-up integer with zero matches Concrete
- IF selects each branch correctly
- unselected branch remains lazy
- every test reaches the same committed states as Concrete
```

---

## Task 6: Cross the recursive-call boundary with the smallest letrec

Do not jump directly to Fibonacci.

Introduce a one-binding recursive countdown whose result is constant:

```thor
loop == (lambda (n)
  (if (= n 0)
      42
      (loop (1- n))))

(loop 3)
```

Also test the equivalent local `letrec` form, because Fibonacci uses a nested recursive binding:

```thor
((lambda (n)
   (letrec ((loop
             (lambda (i)
               (if (= i 0)
                   42
                   (loop (1- i))))))
     (loop n)))
 3)
```

This deliberately combines:

```text
RBLOCK/RUP
REC/RECP
recursive closure/environment construction
APP_VAR recursion
IF laziness
JOIN return
reverse reconstruction
```

Use the existing Concrete recursive test suite as the transition-level oracle. Do not create an alternate recursion encoding for Synth.

Every divergence must again be reduced to the smallest transition fixture possible before fixing hardware.

Acceptance:

```text
(loop 0) => 42
(loop 1) => 42
(loop 3) => 42
```

for the local recursive form, with full Concrete ↔ Synth commit parity.

---

## Task 7: Add changing recursive state

A constant-result countdown proves recursive control flow but not Fibonacci's evolving arguments.

Next implement/test a recursive accumulator:

```thor
((lambda (n)
   (letrec ((sum
             (lambda (i acc)
               (if (= i 0)
                   acc
                   (sum (1- i) (+ acc i))))))
     (sum n 0)))
 4)
```

Expected result:

```text
10
```

This forces each recursive call to construct a fresh argument set from values produced by the current invocation.

Then add a three-argument state-transition loop mirroring Fibonacci's calling shape:

```text
(i, current, next)
    ->
(i - 1, next, current + next)
```

without yet relying on the checked-in `fib` definition.

Acceptance:

```text
- recursive arguments are published in the correct order
- old environments remain valid for as long as Concrete keeps them live
- JOIN restores the correct caller state
- recursive residual/reconstruction behavior matches Concrete
- accumulated result matches across Abstract, Concrete, and Synth
```

---

## Task 8: Execute Fibonacci

Now make the real checked-in program the test:

```text
examples/fibonacci.thor
```

The first required milestone is exactly the existing `fib-six` entry.

Expected output:

```text
8
```

Also exercise small boundary inputs through equivalent source fixtures:

```text
fib 0 => 0
fib 1 => 1
fib 2 => 1
fib 6 => 8
```

Use an initial quantum high enough that native recharge is not required for this milestone. If Fibonacci unexpectedly exhausts the representable/useful initial quantum, diagnose whether that exposes a genuine reducer bug before expanding scope into native recharge support.

For every Fibonacci case compare:

```text
THOR result
Abstract RED2 result
Concrete RED2 result
Synthesizable RED2 result
```

For at least `fib 6`, Concrete and Synth must additionally match at every committed architectural checkpoint.

Acceptance:

```text
scripts/run_syn.py examples/fibonacci.thor
```

prints:

```text
8
```

and exits successfully with:

```text
STATUS_COMPLETE
red2_fault == FAULT_NONE
hw_fault == HW_FAULT_NONE
```

No Python reducer may be invoked as a fallback after the Synth machine is loaded.

---

## Task 9: Hardware/frontend regression gate

After Fibonacci is green in the native simulator, rerun the actual PipelineC/Pypeline path.

Required gates:

```text
full Asgard pytest suite

native Synth parity:
scripts/check_syn_sim.py

real PipelineC frontend + HDL emission:
scripts/check_syn.py --frontend-only

direct Synth Fibonacci execution:
scripts/run_syn.py examples/fibonacci.thor
```

`check_syn.py --frontend-only` must still emit the `SynthesizableRED2Machine` VHDL and complete its native parity gate.

Do not weaken or bypass the PipelineC frontend merely to keep Python simulation green.

If a newly correct semantic path breaks PipelineC lowering, simplify/restructure the hardware source while preserving the same architecture. Only modify PipelineC itself if the required construct is demonstrably a frontend/compiler defect rather than an Asgard coding-shape problem.

---

## Task 10: Record the milestone without overclaiming completeness

Once Fibonacci passes, document the new boundary:

```text
Synthesizable RED2 can execute recursive, closure-using, primitive-using
pure THOR programs through at least the Fibonacci workload.
```

Do **not** automatically change:

```python
RED2_SYNTH_SEMANTICS_COMPLETE = 0
```

to `1`.

Before that flag can become `1`, separately audit the remaining promised semantics, including at minimum the unfinished runtime surfaces already exposed by the current runner:

```text
quantum-exhaustion recharge/resume
host-call CMD_RESUME
any remaining HW_FAULT_EXECUTION_NOT_IMPLEMENTED semantic branches
full pure-value/recursive/equality coverage promised by the processor ABI
```

Fibonacci completion closes this plan even if those larger completion items remain.

---

## Final acceptance

This plan is complete when all of the following are true:

```text
1. The post-migration architecture remains intact:
   thor / red2 / peer machine packages.

2. No .red2 serialization or compile CLI is restored.

3. Every semantic bug encountered on the road to Fibonacci has a
   minimized Concrete ↔ Synth regression.

4. Bound-variable primitive use works:
   ((LAMBDA (x) (+ x 1)) 41) => 42.

5. Closure capture and closure-valued variable invocation work.

6. A local recursive countdown works.

7. A recursive accumulator with changing arguments works.

8. examples/fibonacci.thor executes entirely on Synthesizable RED2
   and produces 8.

9. fib 0, fib 1, fib 2, and fib 6 agree across the reference layers.

10. Concrete ↔ Synth committed architectural state remains identical
    throughout fib 6.

11. Existing Asgard tests stay green.

12. The native Synth parity checker stays green.

13. The real PipelineC frontend still accepts the hardware and emits
    the SynthesizableRED2Machine HDL.

14. RED2_SYNTH_SEMANTICS_COMPLETE remains 0 unless a separate complete
    semantic audit establishes that every withheld capability is done.

15. Basys 3 transport remains deferred.
```

## Execution strategy

Work strictly left-to-right through the capability ladder:

```text
literal lambda
    ↓
bound scalar
    ↓
bound scalar in primitive
    ↓
captured variable
    ↓
closure-valued variable
    ↓
nested application
    ↓
IF + Fibonacci scalar operations
    ↓
minimal letrec countdown
    ↓
recursive changing accumulator
    ↓
three-state recursive loop
    ↓
Fibonacci
```

At every red step:

```text
reproduce
→ find first Concrete/Synth divergence
→ minimize
→ add regression
→ implement exact Concrete semantics
→ native parity
→ PipelineC frontend check
→ advance one rung
```

The next implementation target after writing this plan is therefore **not Fibonacci itself**. It is the first failing rung between:

```thor
((LAMBDA (x) x) 41)
```

and:

```thor
((LAMBDA (x) (+ x 1)) 41)
```

with the current terminal `VAR` / `APP_VAR` binding fallthroughs as the first code paths to investigate.

