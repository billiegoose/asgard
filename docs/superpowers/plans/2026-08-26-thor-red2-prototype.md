# THOR and RED2 Research Prototype Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a faithful research prototype consisting of a Python THOR interpreter, a Python RED2 stack/graph machine, and a PypelineC/Pypeline RED2 stepper artifact that can be compared against the Python models.

**Architecture:** The Python THOR interpreter is the executable semantic reference: parser/AST/printer plus reduction rules from Chapter 3. The Python RED2 machine compiles the same AST into a linear graph/instruction memory and steps instructions from Chapter 4, then parity tests compare RED2 results with the THOR reference. The PypelineC artifact is a hardware-oriented fixed-width RED2 stepper subset with static tests and golden vectors derived from the Python instruction model.

**Tech Stack:** Python 3.14, dataclasses, pytest, ruff, mypy, uv, and Pypeline/PypelineC-style Python HDL source kept dependency-light with optional local validation against `https://github.com/JulianKemmerer/PipelineC`.

**Spec:** `thesis-transcription/src/chapters/chapter3.tex` for THOR syntax/semantics; `thesis-transcription/src/chapters/chapter4.tex` for RED2 machine design; PipelineC/Pypeline reference: `https://github.com/JulianKemmerer/PipelineC`.

## Global Constraints

- Keep the project on Python `>=3.14` as declared in `pyproject.toml`.
- Keep runtime dependencies empty unless a task explicitly proves a dependency is necessary; dev-only checks continue through uv dependency groups.
- Preserve the existing CLI entry point name `thor-spec` from `pyproject.toml`.
- Use `uv run pytest`, `uv run ruff check .`, and `uv run mypy src tests` as final verification commands.
- Implement a faithful research prototype, not a production toolchain: prioritize readable code, deterministic tests, and traceability to `chapter3.tex`/`chapter4.tex` over performance.
- Represent THOR variables internally with De Bruijn indices following Figure 3.1, while preserving source symbol names where needed for printing and diagnostics.
- Treat structures as lazy: creating/reducing a structure must not contract component redexes except for variable substitution effects described by Rule 14.
- Treat RED2 graph memory as an explicit list of instructions with opcode, data, and head flag fields; avoid hiding RED2 behavior behind calls to the THOR interpreter except in tests/parity harnesses.
- PypelineC/Pypeline code is a hardware-oriented prototype artifact; do not require FPGA vendor tools in the default test suite.

**Acceptance:** suite — the committed pytest/ruff/mypy suite plus RED2/THOR parity tests are the verification for this readable research prototype.

---

## File Structure

- `src/thor_spec/ast.py` defines immutable THOR AST nodes, runtime helper nodes (`Closure`, `UBV`, `Rec`, `Block`), predicates, and typed constructors shared by both interpreters.
- `src/thor_spec/parser.py` tokenizes and parses THOR S-expressions, definitions (`NAME == expr` in ASCII form), structure declarations (`TAG |= A B` in ASCII form), list sugar, and source comments.
- `src/thor_spec/pretty.py` renders AST values back to stable THOR text for CLI output and golden tests.
- `src/thor_spec/semantics.py` implements the Chapter 3 abstract interpreter and returns a typed `ReductionResult` with remaining quantum and trace data.
- `src/thor_spec/primitives.py` owns strict arithmetic/predicate primitives, logical primitives, `IF`, structure accessors, `Y`, `LETREC`, and equality behavior.
- `src/thor_spec/red2/instructions.py` defines RED2 opcodes, instruction words, memory images, fixed-width encodings, and golden vector serialization shared by Python RED2 and the Pypeline artifact.
- `src/thor_spec/red2/compiler.py` compiles THOR AST nodes to RED2 linear graph memory using the Chapter 4 compilation rules.
- `src/thor_spec/red2/machine.py` implements RED2 machine state, environment/control stack, `LOOKUP`, and instruction stepping.
- `src/thor_spec/red2/primitives.py` implements RED2 strict/non-strict primitive behavior.
- `src/thor_spec/red2/pipelinec_vectors.py` emits small golden vectors for the Pypeline/PypelineC stepper.
- `pypeline_red2/red2_stepper.py` contains the Pypeline/PypelineC-oriented RED2 stepper subset.
- `pypeline_red2/README.md` documents how the hardware-oriented artifact maps to the Python RED2 model and how to validate it when PypelineC is checked out locally.
- `tests/` gains focused tests for each module plus parity and static Pypeline artifact checks.

---

### Task 1: THOR AST, Parser, and Pretty Printer

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/ast.py`
- Create: `src/thor_spec/parser.py`
- Create: `src/thor_spec/pretty.py`
- Modify: `src/thor_spec/__init__.py`
- Create: `tests/test_parser_ast_pretty.py`

**Interfaces:**
- Consumes: none
- Produces: `parse_expr(source: str) -> Expr`; `parse_program(source: str) -> Program`; `to_source(expr: Expr) -> str`; AST classes `Var(index: int, name: str | None = None)`, `Lambda(params: tuple[str, ...], body: Expr)`, `App(items: tuple[Expr, ...])`, `LetRec(bindings: tuple[Binding, ...], body: Expr)`, `StructLit(tag: str, fields: tuple[Expr, ...])`, `Symbol(name: str)`, `Integer(value: int)`, `Float(value: float)`, `Char(value: str)`, `Definition(name: str, expr: Expr)`, `StructDef(tag: str, accessors: tuple[str, ...])`, `Program(forms: tuple[TopLevel, ...])`.

**Parallelization rationale:** This task establishes data contracts that let the semantic interpreter, RED2 compiler, and Pypeline vector work proceed against stable types without waiting on reduction behavior.

- [ ] **Step 1: Write failing parser/AST/pretty tests**

Add `tests/test_parser_ast_pretty.py` with these exact coverage points:

```python
from thor_spec.ast import App, Binding, Integer, Lambda, LetRec, StructDef, StructLit, Symbol
from thor_spec.parser import parse_expr, parse_program
from thor_spec.pretty import to_source


def test_lambda_application_round_trips() -> None:
    expr = parse_expr("((LAMBDA (X Y) X) 1 2)")
    assert isinstance(expr, App)
    assert to_source(expr) == "((LAMBDA (X Y) X) 1 2)"


def test_list_sugar_parses_to_pair_structure() -> None:
    expr = parse_expr("[1 2]")
    assert expr == StructLit("PAIR", (Integer(1), StructLit("PAIR", (Integer(2), Symbol("NIL")))))
    assert to_source(expr) == "[1 2]"


def test_dotted_pair_sugar_parses_to_pair_structure() -> None:
    expr = parse_expr("[1 | X]")
    assert expr == StructLit("PAIR", (Integer(1), Symbol("X")))
    assert to_source(expr) == "[1 | X]"


def test_letrec_and_top_level_forms_parse() -> None:
    program = parse_program(
        """
        PAIR |= CAR CDR
        fact == (LAMBDA (N) (IF (= N 0) 1 (* N (fact (1- N)))))
        (LETREC ((x [1 | y]) (y [2 | x])) x)
        """
    )
    assert isinstance(program.forms[0], StructDef)
    assert program.forms[0].tag == "PAIR"
    expr = program.forms[2]
    assert isinstance(expr, LetRec)
    assert expr.bindings[0] == Binding("x", StructLit("PAIR", (Integer(1), Symbol("y"))))
```

- [ ] **Step 2: Run parser tests and verify they fail**

Run: `uv run pytest tests/test_parser_ast_pretty.py -v`

Expected: FAIL because `thor_spec.ast`, `thor_spec.parser`, and `thor_spec.pretty` do not exist yet.

- [ ] **Step 3: Implement AST, parser, and pretty printer**

Create frozen dataclasses and parser code matching the interfaces. Implement these syntax choices exactly:

- Parenthesized forms parse as `Lambda` when first symbol is `LAMBDA`, `LetRec` when first symbol is `LETREC`, otherwise `App(items)`.
- Braced forms parse as `StructLit(tag, fields)`.
- `[a b c]` parses to `{PAIR a {PAIR b {PAIR c NIL}}}`; `[a | b]` parses to `{PAIR a b}`.
- Top-level `NAME == expr` parses to `Definition`; top-level `TAG |= A B` parses to `StructDef`.
- `to_source()` prints stable uppercase special forms and preserves ordinary symbol spelling.

- [ ] **Step 4: Run parser tests and verify they pass**

Run: `uv run pytest tests/test_parser_ast_pretty.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused lint/type checks**

Run: `uv run ruff check src/thor_spec/ast.py src/thor_spec/parser.py src/thor_spec/pretty.py tests/test_parser_ast_pretty.py && uv run mypy src/thor_spec/ast.py src/thor_spec/parser.py src/thor_spec/pretty.py tests/test_parser_ast_pretty.py`

Expected: PASS.

---

### Task 2: Chapter 3 Core THOR Abstract Interpreter

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/semantics.py`
- Modify: `src/thor_spec/__init__.py`
- Create: `tests/test_semantics_core.py`

**Interfaces:**
- Consumes: `Expr`, `Lambda`, `App`, `Var`, `Symbol`, `Integer`, `parse_expr(source: str) -> Expr`, `to_source(expr: Expr) -> str` from Task 1.
- Produces: `ReductionResult(expr: Expr, remaining: int, phi: int, steps: int)`; `translate(expr: Expr, scope: tuple[str, ...] = ()) -> Expr`; `reduce_expr(expr: Expr, *, quantum: int, definitions: Mapping[str, Expr] | None = None) -> ReductionResult`.

- [ ] **Step 1: Write failing tests for translation, beta reduction, abstraction, definitions, and quantum expiry**

Add `tests/test_semantics_core.py`:

```python
from thor_spec.ast import App, Integer, Lambda, Symbol, Var
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.semantics import reduce_expr, translate


def test_translation_converts_bound_symbols_to_debruijn_vars() -> None:
    expr = translate(parse_expr("(LAMBDA (X Y) X Y)"))
    assert expr == Lambda(("X", "Y"), App((Var(0, "X"), Var(1, "Y"))))


def test_beta_reduction_substitutes_argument_through_closure() -> None:
    result = reduce_expr(parse_expr("((LAMBDA (X) X) 42)"), quantum=10)
    assert result.expr == Integer(42)
    assert result.remaining == 9
    assert result.steps == 1


def test_normal_order_reduces_operator_before_operand() -> None:
    result = reduce_expr(parse_expr("(((LAMBDA (X) (LAMBDA (Y) X)) 7) (BAD BAD))"), quantum=3)
    assert to_source(result.expr) == "7"


def test_exhausted_quantum_preserves_application_shape() -> None:
    result = reduce_expr(parse_expr("((LAMBDA (X) X) 42)"), quantum=0)
    assert to_source(result.expr) == "((LAMBDA (X) X) 42)"
    assert result.remaining == 0


def test_symbol_definition_costs_one_contraction() -> None:
    result = reduce_expr(Symbol("ANSWER"), quantum=2, definitions={"ANSWER": Integer(42)})
    assert result.expr == Integer(42)
    assert result.remaining == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_semantics_core.py -v`

Expected: FAIL because `thor_spec.semantics` does not exist.

- [ ] **Step 3: Implement Chapter 3 Rules 1-9**

Implement `translate()` per Figure 3.1. Implement an environment/redex store as immutable tuples of runtime values and apply these rules:

- Rule 1: `((lambda e0) e1)` with `q > 0` adds `Closure(e1, rho)` to the redex store, decrements quantum, reduces `e0`, and returns the reduced body while cutting back to the caller store.
- Rule 2: applications reduce the operator first, then the reconstructed application.
- Rule 3: unapplied lambdas reduce their body under `UBV(phi + 1)`.
- Rule 4: `Var(i)` dereferences the redex store.
- Rule 5: `UBV(i)` becomes `Var(phi - i)`.
- Rule 6: `Closure(e, rho1)` reduces `e` in `rho1` but returns to caller store.
- Rules 7-9: integers/floats/chars are passive; undefined symbols or exhausted quantum are passive; defined symbols cost one contraction.

- [ ] **Step 4: Run core semantic tests**

Run: `uv run pytest tests/test_semantics_core.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused lint/type checks**

Run: `uv run ruff check src/thor_spec/semantics.py tests/test_semantics_core.py && uv run mypy src/thor_spec/semantics.py tests/test_semantics_core.py`

Expected: PASS.

---

### Task 3: THOR Data Objects, Primitives, Structures, and Recursion

**Type:** implementation
**Depends-on:** 1, 2
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/semantics.py`
- Modify: `src/thor_spec/ast.py`
- Create: `tests/test_semantics_primitives.py`
- Create: `tests/test_semantics_recursion.py`

**Interfaces:**
- Consumes: `reduce_expr(expr: Expr, *, quantum: int, definitions: Mapping[str, Expr] | None = None) -> ReductionResult`; AST classes from Task 1.
- Produces: `install_struct_accessors(tag: str, accessors: tuple[str, ...], definitions: MutableMapping[str, Expr]) -> None`; `try_reduce_primitive(app: App, state: EvalState) -> Expr | None`; runtime nodes `Block(expressions: tuple[Expr, ...])` and `Rec(index: int, store: RedexStore, block: Block)`.

- [ ] **Step 1: Write failing tests for constants, strict primitives, partial predicates, lazy structures, IF, Y, and LETREC**

Add `tests/test_semantics_primitives.py`:

```python
from thor_spec.ast import Integer, StructLit, Symbol
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.primitives import install_struct_accessors
from thor_spec.semantics import reduce_expr


def reduced(source: str, quantum: int = 20) -> str:
    return to_source(reduce_expr(parse_expr(source), quantum=quantum).expr)


def test_integer_arithmetic_and_predicates() -> None:
    assert reduced("(+ 2 3)") == "5"
    assert reduced("(1- 5)") == "4"
    assert reduced("(= 5 5)") == "TRUE"
    assert reduced("(INTEGER? 5)") == "TRUE"
    assert reduced("(INTEGER? (LAMBDA (X) X))") == "FALSE"


def test_type_predicate_keeps_irreducible_application() -> None:
    assert reduced("(INTEGER? (FOO X))") == "(INTEGER? (FOO X))"


def test_structure_is_lazy_but_accessor_reduces_component() -> None:
    defs: dict[str, object] = {}
    install_struct_accessors("PAIR", ("CAR", "CDR"), defs)  # type: ignore[arg-type]
    expr = parse_expr("(CAR {PAIR (+ 2 3) (BAD BAD)})")
    assert reduce_expr(expr, quantum=20, definitions=defs).expr == Integer(5)


def test_if_reduces_only_selected_branch() -> None:
    assert reduced("(IF TRUE (+ 1 2) (BAD BAD))") == "3"
    assert reduced("(IF FALSE (BAD BAD) (+ 4 5))") == "9"
    assert reduced("(IF (FOO X) (+ 1 2) (+ 3 4))") == "(IF (FOO X) (+ 1 2) (+ 3 4))"
```

Add `tests/test_semantics_recursion.py`:

```python
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.semantics import reduce_expr


def test_y_operator_retains_identity_under_small_quantum() -> None:
    expr = parse_expr("((Y (LAMBDA (FACT N) (IF (= N 0) 1 (* N (FACT (1- N)))))) 3)")
    result = reduce_expr(expr, quantum=2)
    assert "Y" in to_source(result.expr)
    assert "FACT" in to_source(result.expr)


def test_letrec_infinite_pair_prefix_reconstructs_when_quantum_expires() -> None:
    expr = parse_expr("(LETREC ((x [1 | y]) (y [2 | x])) x)")
    result = reduce_expr(expr, quantum=1)
    assert to_source(result.expr) == "[1 | (LETREC ((x [1 | y]) (y [2 | x])) y)]"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_semantics_primitives.py tests/test_semantics_recursion.py -v`

Expected: FAIL because primitives/recursion are not implemented.

- [ ] **Step 3: Implement Chapter 3 Rules 10-29**

Implement primitives and extend `semantics.py` exactly enough for the tests and thesis examples:

- Unary: `1-`, `INTEGER?`, `FLOAT?`, `CHAR?`, `SYMBOL?`, `STRUCTURE?`, `NOT`, `TAG`.
- Binary: `+`, `-`, `*`, `/`, `<`, `>`, `=`, `EQUAL?` for the prototype subset.
- N-ary logical forms: `AND` and `OR` with partial-evaluation behavior matching Rules 19-21 and the symmetric OR cases.
- `IF` strict only in the condition; if the condition remains non-boolean, reduce branches with quantum zero only.
- `Y` transforms `(Y f)` to `(f (Y f))` and costs one contraction when quantum is available.
- `LETREC` creates `Block`/`Rec` runtime values when quantum is available; with exhausted quantum reconstructs LETREC wrappers around recursive variables per Rules 27-29.
- `install_struct_accessors()` must create selector definitions equivalent to the PAIR example in Chapter 4: `(LAMBDA (PAIR) (PAIR (LAMBDA (CAR CDR) CAR)))`.

- [ ] **Step 4: Run primitive/recursion tests**

Run: `uv run pytest tests/test_semantics_primitives.py tests/test_semantics_recursion.py -v`

Expected: PASS.

- [ ] **Step 5: Run semantic regression suite**

Run: `uv run pytest tests/test_semantics_core.py tests/test_semantics_primitives.py tests/test_semantics_recursion.py -v`

Expected: PASS.

---

### Task 4: RED2 Instruction Contracts, Encodings, and Compiler Skeleton

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/red2/__init__.py`
- Create: `src/thor_spec/red2/instructions.py`
- Create: `src/thor_spec/red2/compiler.py`
- Create: `tests/test_red2_compiler.py`

**Interfaces:**
- Consumes: `Expr`, `Lambda`, `App`, `StructLit`, `LetRec`, `Var`, `Symbol`, `Integer`, `parse_expr(source: str) -> Expr` from Task 1.
- Produces: `Opcode` enum with `APP`, `LAMBDA`, `VAR`, `STOP`, `INT`, `FLOAT`, `CHAR`, `SYM`, `PRIM_0`, `PRIM_1`, `PRIM_2`, `STRUCT`, `RBLOCK`, `RUP`, `RECP`, `JOIN`, `CLOSURE`, `UBV`, `PNP`, `REC`; `Instruction(opcode: Opcode, data: int | str | float | None = None, head: bool = False)`; `ProgramImage(instructions: tuple[Instruction, ...], entry: int, symbol_table: Mapping[str, int])`; `compile_expr(expr: Expr) -> ProgramImage`; `encode_instruction(inst: Instruction) -> int`; `decode_instruction(word: int) -> Instruction`.

**Parallelization rationale:** The RED2 compiler/encoding contract lets the Python RED2 machine and PypelineC stepper build independently against the same instruction-word model.

- [ ] **Step 1: Write failing compiler/encoding tests**

Add `tests/test_red2_compiler.py`:

```python
from thor_spec.parser import parse_expr
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.instructions import Instruction, Opcode, decode_instruction, encode_instruction


def opcodes(source: str) -> list[Opcode]:
    return [inst.opcode for inst in compile_expr(parse_expr(source)).instructions]


def test_instruction_encoding_round_trips_head_opcode_and_small_data() -> None:
    inst = Instruction(Opcode.INT, 42, head=True)
    assert decode_instruction(encode_instruction(inst)) == inst


def test_lambda_application_compiles_to_linear_spine_with_stop() -> None:
    image = compile_expr(parse_expr("((LAMBDA (X) X) 42)"))
    assert image.entry == 0
    assert image.instructions[-1].opcode is Opcode.STOP
    assert opcodes("((LAMBDA (X) X) 42)")[:4] == [Opcode.APP, Opcode.LAMBDA, Opcode.VAR, Opcode.INT]


def test_head_flag_marks_spine_head() -> None:
    image = compile_expr(parse_expr("(LAMBDA (A B) A B)"))
    assert [(i.opcode, i.head) for i in image.instructions[:4]] == [
        (Opcode.LAMBDA, False),
        (Opcode.LAMBDA, False),
        (Opcode.VAR, False),
        (Opcode.VAR, True),
    ]


def test_structure_and_letrec_compile_to_red2_specific_opcodes() -> None:
    assert Opcode.STRUCT in opcodes("{PAIR 1 2}")
    letrec_ops = opcodes("(LETREC ((x [1 | y]) (y [2 | x])) x)")
    assert letrec_ops.count(Opcode.RBLOCK) == 2
    assert Opcode.RUP in letrec_ops
```

- [ ] **Step 2: Run compiler tests and verify failure**

Run: `uv run pytest tests/test_red2_compiler.py -v`

Expected: FAIL because `thor_spec.red2` does not exist.

- [ ] **Step 3: Implement RED2 instruction contracts and compiler skeleton**

Implement a deterministic compiler following Chapter 4:

- Applications compile as `APP` pointing to each argument body, followed by operator spine code.
- The last instruction in each contiguous spine has `head=True`, matching the head flag concept.
- Lambdas compile as one `LAMBDA` per parameter with data storing the parameter name.
- Structures compile as `STRUCT tag`, then APPs to components from last to first, then `VAR 0` as described in Section 4.6.
- LETREC compiles using one `RBLOCK` per binding, an `RUP n`, then the body under the extended scope.
- `encode_instruction()`/`decode_instruction()` use a documented prototype 32-bit integer layout: bit 31 head flag, bits 24-30 opcode, bits 0-23 unsigned data. For string/float data in tests, allocate small stable symbol-table IDs; reject unencodable values with `ValueError`.

- [ ] **Step 4: Run compiler tests**

Run: `uv run pytest tests/test_red2_compiler.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused lint/type checks**

Run: `uv run ruff check src/thor_spec/red2 tests/test_red2_compiler.py && uv run mypy src/thor_spec/red2 tests/test_red2_compiler.py`

Expected: PASS.

---

### Task 5: Python RED2 Machine Core and μRED Instructions

**Type:** implementation
**Depends-on:** 4
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/red2/machine.py`
- Create: `tests/test_red2_machine_core.py`

**Interfaces:**
- Consumes: `Opcode`, `Instruction`, `ProgramImage`, `compile_expr(expr: Expr) -> ProgramImage` from Task 4; `parse_expr(source: str) -> Expr` from Task 1.
- Produces: `Direction` enum with `F` and `B`; `MachineState(memory: list[Instruction], pc: int, fsp: int, cstack: list[int], env: int | None, q: int, phi: int, direction: Direction, halted: bool)`; `Red2Machine(image: ProgramImage, quantum: int)`; `Red2Machine.step() -> MachineState`; `Red2Machine.run(max_steps: int = 10000) -> MachineState`; `lookup(index: int, state: MachineState) -> int`.

- [ ] **Step 1: Write failing RED2 core tests**

Add `tests/test_red2_machine_core.py`:

```python
from thor_spec.parser import parse_expr
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.instructions import Opcode
from thor_spec.red2.machine import Direction, Red2Machine


def machine(source: str, quantum: int = 10) -> Red2Machine:
    return Red2Machine(compile_expr(parse_expr(source)), quantum=quantum)


def test_machine_initializes_problem_graph_with_stop_and_forward_direction() -> None:
    m = machine("42")
    assert m.state.pc == 0
    assert m.state.direction is Direction.F
    assert m.state.memory[-1].opcode is Opcode.STOP


def test_int_head_switches_to_reverse_and_stop_halts() -> None:
    m = machine("42")
    m.run()
    assert m.state.halted is True
    assert m.result_instructions()[0].opcode is Opcode.INT
    assert m.result_instructions()[0].data == 42


def test_beta_reduction_on_lambda_application_consumes_quantum() -> None:
    m = machine("((LAMBDA (X) X) 42)", quantum=10)
    m.run()
    assert m.state.q == 9
    assert [(i.opcode, i.data) for i in m.result_instructions()] == [(Opcode.INT, 42)]


def test_exhausted_quantum_keeps_application_spine() -> None:
    m = machine("((LAMBDA (X) X) 42)", quantum=0)
    m.run()
    assert [i.opcode for i in m.result_instructions()] == [Opcode.APP, Opcode.LAMBDA, Opcode.INT]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_red2_machine_core.py -v`

Expected: FAIL because `red2.machine` does not exist.

- [ ] **Step 3: Implement machine state, LOOKUP, and base instruction stepping**

Implement Chapter 4 execution model for `APP`, `CLOSURE`, `JOIN`, `LAMBDA`, `STOP`, `UBV`, `VAR`, and passive constants:

- Initial memory is problem graph plus `STOP`, result graph space grows after `fsp`.
- Forward execution walks down contiguous spines; reverse execution walks up copied result spines.
- `APP` forward copies itself and pushes current `env`; `APP` reverse cuts back environment, emits `JOIN`, and reduces the argument.
- `LAMBDA` contracts beta-redexes when `q > 0` and the copied top result instruction is `APP`; otherwise emits a lambda and adds `UBV`.
- `VAR` calls `lookup`; `UBV` emits corrected `VAR(phi - ubv_data)` and changes direction to reverse.
- `result_instructions()` returns the result graph excluding `JOIN`, `STOP`, environment cells, and reclaimed cells.

- [ ] **Step 4: Run RED2 core tests**

Run: `uv run pytest tests/test_red2_machine_core.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused lint/type checks**

Run: `uv run ruff check src/thor_spec/red2/machine.py tests/test_red2_machine_core.py && uv run mypy src/thor_spec/red2/machine.py tests/test_red2_machine_core.py`

Expected: PASS.

---

### Task 6: RED2 Constants, Symbols, Primitives, Structures, and LETREC

**Type:** implementation
**Depends-on:** 3, 5
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/red2/primitives.py`
- Modify: `src/thor_spec/red2/machine.py`
- Modify: `src/thor_spec/red2/compiler.py`
- Create: `tests/test_red2_machine_extended.py`

**Interfaces:**
- Consumes: `Red2Machine`, `MachineState`, `Opcode`, `Instruction`, `install_struct_accessors()` from Task 3, compiler interfaces from Task 4.
- Produces: `fire_primitive(name: str, args: tuple[Instruction, ...], quantum: int) -> tuple[Instruction | None, int]`; RED2 support for `SYM`, `PRIM_0`, `PRIM_1`, `PRIM_2`, `STRUCT`, `RBLOCK`, `RUP`, and `RECP`.

- [ ] **Step 1: Write failing extended RED2 and parity tests**

Add `tests/test_red2_machine_extended.py`:

```python
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.machine import Red2Machine
from thor_spec.red2.primitives import instructions_to_expr
from thor_spec.semantics import reduce_expr


def run_red2(source: str, quantum: int = 30) -> str:
    machine = Red2Machine(compile_expr(parse_expr(source)), quantum=quantum)
    machine.run()
    return to_source(instructions_to_expr(machine.result_instructions()))


def test_red2_addition_matches_thor_reference() -> None:
    assert run_red2("(+ 2 3)") == "5"
    assert run_red2("(+ 2 3)") == to_source(reduce_expr(parse_expr("(+ 2 3)"), quantum=30).expr)


def test_red2_if_does_not_reduce_unselected_branch() -> None:
    assert run_red2("(IF TRUE (+ 1 2) (BAD BAD))") == "3"


def test_red2_pair_accessor_matches_thor_reference() -> None:
    assert run_red2("(CAR {PAIR (+ 2 3) (BAD BAD)})") == "5"


def test_red2_letrec_prefix_matches_thor_reference() -> None:
    source = "(LETREC ((x [1 | y]) (y [2 | x])) x)"
    assert run_red2(source, quantum=1) == to_source(reduce_expr(parse_expr(source), quantum=1).expr)
```

- [ ] **Step 2: Run extended tests and verify failure**

Run: `uv run pytest tests/test_red2_machine_extended.py -v`

Expected: FAIL because RED2 extended primitives are not implemented.

- [ ] **Step 3: Implement RED2 extended instruction behavior**

Extend RED2 from μRED to RED2 following Chapter 4 Section 4.5 onward:

- Constants: `INT`, `FLOAT`, `CHAR` copy passively and switch to reverse when `head=True`.
- `SYM`: copy if non-head, undefined, or quantum expired; otherwise jump to definition and decrement quantum.
- Strict primitive mechanism: use `argcnt`, `prim`, and `fire` fields on `MachineState`; save/restore `prim` and `fire` on control stack around argument reductions.
- Primitive firing: implement `+`, `-`, `*`, `/`, `1-`, `<`, `>`, `=`, `INTEGER?`, `NOT`, `AND`, `OR`, `IF`, `TAG`, `CAR`, `CDR`, and `Y` for the prototype subset.
- `STRUCT`: acts like `LAMBDA` when applied, but sets quantum to zero while traversing components when unapplied.
- `RBLOCK`, `RUP`, `RECP`: implement enough of the thesis algorithm to satisfy LETREC prefix reconstruction parity tests.
- `instructions_to_expr()` decompiles result instructions to AST for tests and CLI use.

- [ ] **Step 4: Run RED2 extended tests**

Run: `uv run pytest tests/test_red2_machine_extended.py -v`

Expected: PASS.

- [ ] **Step 5: Run all Python reference and RED2 tests together**

Run: `uv run pytest tests/test_semantics_core.py tests/test_semantics_primitives.py tests/test_semantics_recursion.py tests/test_red2_compiler.py tests/test_red2_machine_core.py tests/test_red2_machine_extended.py -v`

Expected: PASS.

---

### Task 7: CLI, Golden Corpus, and THOR/RED2 Parity Harness

**Type:** implementation
**Depends-on:** 3, 6

**Files:**
- Modify: `src/thor_spec/cli.py`
- Modify: `src/thor_spec/core.py`
- Create: `src/thor_spec/golden.py`
- Create: `tests/golden/thor_examples.thor`
- Create: `tests/test_cli_models.py`
- Create: `tests/test_golden_parity.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `parse_program(source: str) -> Program`; `reduce_expr(...) -> ReductionResult`; `Red2Machine`; `compile_expr`; `instructions_to_expr`.
- Produces: `run_source(source: str, *, model: Literal["thor", "red2"], quantum: int) -> str`; CLI flags `--model thor|red2`, `--quantum N`, `--expr SOURCE`, `--file PATH`, and `--trace`.

- [ ] **Step 1: Write failing CLI and parity tests**

Add `tests/test_cli_models.py`:

```python
from thor_spec.cli import main


def test_cli_runs_thor_model_expr(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--model", "thor", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"


def test_cli_runs_red2_model_expr(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--model", "red2", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"
```

Add `tests/test_golden_parity.py`:

```python
from pathlib import Path

from thor_spec.golden import run_source


def test_golden_examples_match_between_thor_and_red2() -> None:
    source = Path("tests/golden/thor_examples.thor").read_text()
    cases = [line for line in source.splitlines() if line.strip() and not line.startswith("#")]
    for case in cases:
        thor = run_source(case, model="thor", quantum=40)
        red2 = run_source(case, model="red2", quantum=40)
        assert red2 == thor, case
```

Create `tests/golden/thor_examples.thor` with:

```text
# One expression per non-comment line.
((LAMBDA (X) X) 42)
(+ 2 3)
(IF TRUE (+ 1 2) (BAD BAD))
(CAR {PAIR (+ 2 3) (BAD BAD)})
(LETREC ((x [1 | y]) (y [2 | x])) x)
```

- [ ] **Step 2: Run CLI/parity tests and verify failure**

Run: `uv run pytest tests/test_cli_models.py tests/test_golden_parity.py -v`

Expected: FAIL because CLI flags and golden harness do not exist.

- [ ] **Step 3: Implement CLI and golden harness**

Update CLI behavior:

- `thor-spec --expr SOURCE` prints the reduced expression using the THOR model by default.
- `thor-spec --model red2 --expr SOURCE` compiles and runs RED2, then decompiles result instructions.
- `--file PATH` reads one or more forms; definitions and struct declarations update context; expression forms print one result per line.
- `--trace` prints deterministic trace lines to stderr and keeps stdout as result-only text.
- Return code `2` for parse/evaluation errors; return code `0` for successful reductions.

Update `README.md` with concise examples for both models and the prototype scope.

- [ ] **Step 4: Run CLI and parity tests**

Run: `uv run pytest tests/test_cli_models.py tests/test_golden_parity.py -v`

Expected: PASS.

- [ ] **Step 5: Run README-adjacent smoke command**

Run: `uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"`

Expected stdout: `5`

---

### Task 8: PypelineC/Pypeline RED2 Stepper Artifact and Golden Vectors

**Type:** implementation
**Depends-on:** 4
**Review:** adversarial

**Files:**
- Create: `pypeline_red2/__init__.py`
- Create: `pypeline_red2/red2_stepper.py`
- Create: `pypeline_red2/README.md`
- Create: `src/thor_spec/red2/pipelinec_vectors.py`
- Create: `tests/test_pipelinec_vectors.py`
- Create: `tests/test_pypeline_red2_static.py`

**Interfaces:**
- Consumes: `Instruction`, `Opcode`, `encode_instruction(inst: Instruction) -> int`, `decode_instruction(word: int) -> Instruction` from Task 4.
- Produces: `emit_stepper_vectors() -> list[StepperVector]`; `StepperVector(name: str, before: int, after: int)`; Pypeline-facing functions in `pypeline_red2/red2_stepper.py`: `decode_opcode(word)`, `encode_word(head, opcode, data)`, and `red2_step_word(pc_word, q, direction)`.

**Parallelization rationale:** The hardware-oriented artifact only needs the instruction word contract, so it can be built before the full Python RED2 machine is complete and later checked through parity vectors.

- [ ] **Step 1: Write failing vector and static artifact tests**

Add `tests/test_pipelinec_vectors.py`:

```python
from thor_spec.red2.instructions import Instruction, Opcode, encode_instruction
from thor_spec.red2.pipelinec_vectors import emit_stepper_vectors


def test_stepper_vectors_include_passive_int_and_stop() -> None:
    vectors = {v.name: v for v in emit_stepper_vectors()}
    assert vectors["int_head"].before == encode_instruction(Instruction(Opcode.INT, 42, head=True))
    assert vectors["stop"].before == encode_instruction(Instruction(Opcode.STOP, 0, head=True))
```

Add `tests/test_pypeline_red2_static.py`:

```python
from pathlib import Path


def test_pypeline_stepper_artifact_has_expected_entry_points() -> None:
    source = Path("pypeline_red2/red2_stepper.py").read_text()
    assert "def decode_opcode" in source
    assert "def encode_word" in source
    assert "def red2_step_word" in source
    assert "@MAIN" in source or "# PypelineC entry" in source


def test_pypeline_readme_names_validation_path() -> None:
    text = Path("pypeline_red2/README.md").read_text()
    assert "PipelineC" in text
    assert "golden vectors" in text
    assert "uv run pytest tests/test_pipelinec_vectors.py" in text
```

- [ ] **Step 2: Run vector/static tests and verify failure**

Run: `uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py -v`

Expected: FAIL because the Pypeline artifact and vector module do not exist.

- [ ] **Step 3: Implement golden vector emitter**

Create `pipelinec_vectors.py` with a frozen `StepperVector` dataclass and vectors for:

- `int_head`: input `Instruction(Opcode.INT, 42, head=True)` and expected output word preserving INT data while changing model direction metadata according to the stepper convention.
- `int_non_head`: input `Instruction(Opcode.INT, 42, head=False)`.
- `app`: input `Instruction(Opcode.APP, 7, head=False)`.
- `lambda`: input `Instruction(Opcode.LAMBDA, 1, head=True)`.
- `stop`: input `Instruction(Opcode.STOP, 0, head=True)`.

Document in code comments that vectors validate word-level decode/encode behavior and are not a replacement for full RED2 parity tests.

- [ ] **Step 4: Implement PypelineC/Pypeline stepper subset**

Create `pypeline_red2/red2_stepper.py` as a hardware-oriented, side-effect-light stepper:

- Keep constants for the same 32-bit layout used by Task 4.
- Implement `decode_opcode(word)` and `encode_word(head, opcode, data)` using integer bit operations only.
- Implement `red2_step_word(pc_word, q, direction)` for the first prototype subset: `STOP`, passive constants, `APP`, `VAR`, and `LAMBDA` classification. The function may return a packed status word rather than mutate graph memory.
- Include a clear `# PypelineC entry` comment and, if Pypeline imports are available without adding project dependencies, annotate a small top-level wrapper. If Pypeline imports are not available locally, keep the artifact syntactically valid Python and document the external checkout validation path.

- [ ] **Step 5: Document the PypelineC validation path**

Create `pypeline_red2/README.md` with:

- Scope: fixed-width RED2 stepper subset for hardware exploration, not a complete FPGA reducer.
- Mapping: instruction word layout and opcode names match `thor_spec.red2.instructions`.
- Local checks: `uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py`.
- Optional external validation: clone `https://github.com/JulianKemmerer/PipelineC`, copy or symlink `pypeline_red2/red2_stepper.py` into an examples workspace, then run Pypeline/PipelineC commands from that checkout's current docs.

- [ ] **Step 6: Run Pypeline artifact tests**

Run: `uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py -v`

Expected: PASS.

---

### Task 9: Integrated Examples, Documentation, and Traceability Notes

**Type:** implementation
**Depends-on:** 7, 8

**Files:**
- Create: `docs/thor-red2-prototype.md`
- Modify: `README.md`
- Create: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: CLI flags from Task 7; Pypeline README from Task 8.
- Produces: user-facing documentation that maps prototype features to thesis sections and names known omissions.

- [ ] **Step 1: Write failing docs example test**

Add `tests/test_docs_examples.py`:

```python
from pathlib import Path


def test_traceability_doc_names_models_and_thesis_chapters() -> None:
    text = Path("docs/thor-red2-prototype.md").read_text()
    assert "Chapter 3" in text
    assert "Chapter 4" in text
    assert "THOR interpreter" in text
    assert "RED2 machine" in text
    assert "PypelineC" in text
    assert "faithful research prototype" in text


def test_readme_mentions_both_models() -> None:
    text = Path("README.md").read_text()
    assert "--model thor" in text
    assert "--model red2" in text
```

- [ ] **Step 2: Run docs tests and verify failure**

Run: `uv run pytest tests/test_docs_examples.py -v`

Expected: FAIL because `docs/thor-red2-prototype.md` does not exist or README lacks the new examples.

- [ ] **Step 3: Write traceability documentation**

Create `docs/thor-red2-prototype.md` with sections:

- `## Scope`: state that this is a faithful research prototype.
- `## Thesis Traceability`: map parser/AST to Chapter 3 syntax and Figure 3.1; map `semantics.py` to Chapter 3 Rules 1-29; map RED2 compiler/machine to Chapter 4 execution model and RED2 sections; map PypelineC artifact to the instruction encoding and stepper subset.
- `## Known Omissions`: full floating-point coercions, all character operators, FPGA synthesis automation, performance-accurate memory reclamation, and vendor tool integration are out of scope for this milestone.
- `## Example Commands`: include `uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"` and `uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"`.

Update `README.md` to link this doc and show both model commands.

- [ ] **Step 4: Run docs tests**

Run: `uv run pytest tests/test_docs_examples.py -v`

Expected: PASS.

- [ ] **Step 5: Run documentation smoke commands**

Run: `uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)" && uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"`

Expected stdout contains two lines, both `5`.

---

### Task 10: Final Verification Gate

**Type:** gate
**Depends-on:** 2, 3, 4, 5, 6, 7, 8, 9

**Files:**
- Test: `tests/`
- Test: `src/`
- Test: `pypeline_red2/`

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: verified green suite and static checks.

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest`

Expected: PASS.

- [ ] **Step 2: Run ruff**

Run: `uv run ruff check .`

Expected: PASS.

- [ ] **Step 3: Run mypy**

Run: `uv run mypy src tests`

Expected: PASS.

- [ ] **Step 4: Run CLI smoke tests manually**

Run:

```bash
uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"
uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"
```

Expected: each command prints exactly `5`.

---

## Operator smoke

- do: `uv run thor-spec --model thor --quantum 20 --expr "((LAMBDA (X) X) 42)"`
- see: stdout is exactly `42`.

- do: `uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"`
- see: stdout is exactly `5`.

- do: `uv run thor-spec --model thor --quantum 1 --expr "(LETREC ((x [1 | y]) (y [2 | x])) x)"`
- see: stdout starts with `[1 | (LETREC` and contains both `x [1 | y]` and `y [2 | x]`.

- do: `uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py -v`
- see: tests pass without requiring FPGA vendor tools.
