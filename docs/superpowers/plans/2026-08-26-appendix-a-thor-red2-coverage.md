# Appendix A THOR/RED2 Coverage Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the THOR interpreter and RED2 VM enough to run richer Fibonacci programs and Appendix A SINE/GAME benchmark fragments with THOR/RED2 parity.

**Architecture:** Add Appendix A language surface incrementally: source normalization/desugaring, missing primitive forms, list/structure helpers, and then RED2 native top-level definitions. Keep the THOR interpreter as reference and make RED2 consume the same definition context instead of conservative source inlining. Finish with fixture-based parity tests for Fibonacci and executable Appendix A benchmark subsets.

**Tech Stack:** Python 3.14, pytest, ruff, mypy, uv.

**Spec:** `thesis-transcription/src/chapters/chapter3.tex`, especially Rules 8-9, 14-29 and recursion via symbol definitions; `thesis-transcription/src/chapters/chapter4.tex`, especially RED2 `SYM`, primitive, structure, and LETREC behavior; `thesis-transcription/src/appendices/appendix-a.tex` for benchmark source forms.

## Global Constraints

- Keep Python `>=3.14` and the existing empty runtime dependency policy.
- Preserve CLI command `thor-spec` and existing `--model thor|red2`, `--quantum`, `--expr`, `--file`, and `--trace` flags.
- Do not require FPGA, PipelineC, or vendor HDL tools for default verification.
- Keep THOR as the semantic reference; every new RED2 behavior must be parity-tested against THOR unless explicitly documented as a RED2-only representation detail.
- Prefer THOR-source definitions for Appendix A library functions (`map`, `reduce`, `redtree`, `reptree`) over Python builtins; implement Python primitives only for base operations Appendix A assumes are primitive or metalinguistic.
- Treat top-level recursive symbol definitions as first-class in RED2; do not rely on recursive source inlining for RED2 execution.
- Use ASCII source forms in fixtures: `==` for `\equiv`, `|=` for `\vDash`, uppercase or normalized aliases for special forms.
- Final verification commands: `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`, and CLI parity smoke commands for Fibonacci and Appendix A fixtures.

**Acceptance:** suite — expanded pytest parity fixtures and CLI smoke commands are the verification.

---

## File Structure

- `src/thor_spec/normalization.py` will normalize source-level aliases and desugar `let` to lambda application before reduction/compilation.
- `src/thor_spec/parser.py` will parse lowercase forms and `let` syntax into AST without losing existing behavior.
- `src/thor_spec/primitives.py` will add scalar primitives and list helpers required by Appendix A.
- `src/thor_spec/golden.py` will stop RED2 recursive source inlining and pass definition contexts into RED2.
- `src/thor_spec/red2/compiler.py`, `instructions.py`, `machine.py`, and `primitives.py` will support RED2 symbol definitions natively.
- `tests/fixtures/appendix_a/` will contain ASCII THOR fixture files transcribed from Appendix A in supported syntax.
- `tests/test_appendix_a_*` files will cover normalization, primitives, recursive definitions, and parity.

---

### Task 1: Source Normalization and LET Desugaring

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/normalization.py`
- Modify: `src/thor_spec/parser.py`
- Modify: `src/thor_spec/golden.py`
- Create: `tests/test_source_normalization.py`

**Interfaces:**
- Consumes: AST classes from `src/thor_spec/ast.py`; `parse_expr(source: str) -> Expr`; `parse_program(source: str) -> Program`.
- Produces: `normalize_expr(expr: Expr) -> Expr`; `normalize_program(program: Program) -> Program`; `desugar_let(bindings: tuple[Binding, ...], body: Expr) -> App`.

**Parallelization rationale:** Normalization lets primitive, fixture, and RED2-definition tasks use Appendix A-like source independently against one stable preprocessing contract.

- [ ] **Step 1: Add failing normalization tests**

Create `tests/test_source_normalization.py`:

```python
from thor_spec.ast import App, Binding, Integer, Lambda, Symbol
from thor_spec.normalization import normalize_expr
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source


def test_lowercase_special_forms_normalize_to_core_names() -> None:
    expr = normalize_expr(parse_expr("(lambda (x) (if (null? x) nil (car x)))"))
    assert to_source(expr) == "(LAMBDA (x) (IF (NULL? x) NIL (CAR x)))"


def test_let_desugars_to_lambda_application() -> None:
    expr = normalize_expr(parse_expr("(let ((x 2) (y 3)) (+ x y))"))
    assert expr == App((Lambda(("x", "y"), App((Symbol("+"), Symbol("x"), Symbol("y")))), Integer(2), Integer(3)))


def test_nested_letrec_is_preserved_but_normalized() -> None:
    expr = normalize_expr(parse_expr("(letrec ((f (lambda (n) n))) (f 1))"))
    assert to_source(expr) == "(LETREC ((f (LAMBDA (n) n))) (f 1))"
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_source_normalization.py -v`

Expected: FAIL because `thor_spec.normalization` does not exist or `let` does not parse.

- [ ] **Step 3: Implement parser support and normalization**

Implement a parsed `LET` as an ordinary `App` or temporary AST form only if necessary, then normalize it to `((LAMBDA (names...) body) values...)`. Normalize special form/operator aliases case-insensitively:

- `lambda -> LAMBDA`, `if -> IF`, `letrec -> LETREC`, `nil -> NIL`
- `car -> CAR`, `cdr -> CDR`, `cons -> CONS`, `null? -> NULL?`, `equal? -> EQUAL?`
- `true -> TRUE`, `false -> FALSE`

Call `normalize_program()` inside `golden.run_source()` before model execution so CLI and tests share behavior.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_source_normalization.py -v`

Expected: PASS.

- [ ] **Step 5: Focused static checks**

Run: `uv run ruff check src/thor_spec/normalization.py src/thor_spec/parser.py src/thor_spec/golden.py tests/test_source_normalization.py && uv run mypy src/thor_spec/normalization.py src/thor_spec/parser.py src/thor_spec/golden.py tests/test_source_normalization.py`

Expected: PASS.

---

### Task 2: Appendix A Scalar Primitives

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Create: `tests/test_appendix_a_scalar_primitives.py`

**Interfaces:**
- Consumes: normalized primitive names from Task 1; `run_source(source, model, quantum)`.
- Produces: THOR and RED2 support for `1+`, `MINUS`, `ABS`, `FLOOR`, `CEILING`, `EXPT`, `MAX`, `MIN`, `EVEN?`, and lowercase aliases through normalization.

- [ ] **Step 1: Add failing scalar primitive parity tests**

Create `tests/test_appendix_a_scalar_primitives.py`:

```python
from thor_spec.golden import run_source


def both(source: str, quantum: int = 50) -> tuple[str, str]:
    return (
        run_source(source, model="thor", quantum=quantum),
        run_source(source, model="red2", quantum=quantum),
    )


def test_appendix_a_numeric_primitives_match() -> None:
    cases = {
        "(1+ 4)": "5",
        "(minus 5)": "-5",
        "(abs (minus 7))": "7",
        "(floor (/ 7 2))": "3",
        "(ceiling (/ 7 2))": "4",
        "(expt 2 5)": "32",
        "(max 3 9)": "9",
        "(min 3 9)": "3",
        "(even? 8)": "TRUE",
    }
    for source, expected in cases.items():
        assert both(source) == (expected, expected)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_scalar_primitives.py -v`

Expected: FAIL on missing primitive behavior.

- [ ] **Step 3: Implement scalar primitives in both models**

Add the primitives to THOR and RED2 primitive modules. Requirements:

- `1+` increments integer/float by one.
- `MINUS` unary negates; binary `-` remains subtraction.
- `ABS`, `FLOOR`, `CEILING`, `EXPT`, `MAX`, `MIN`, `EVEN?` contract only when quantum is available and argument types are sufficient.
- Results are `Integer` when mathematically integral and `Float` otherwise.
- RED2 `fire_primitive()` mirrors THOR behavior for instruction arguments.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_scalar_primitives.py -v`

Expected: PASS.

- [ ] **Step 5: Regression checks**

Run: `uv run pytest tests/test_semantics_primitives.py tests/test_red2_machine_extended.py tests/test_appendix_a_scalar_primitives.py -v`

Expected: PASS.

---

### Task 3: List Primitives and NIL Semantics

**Type:** implementation
**Depends-on:** 1, 2
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Create: `tests/test_appendix_a_list_primitives.py`

**Interfaces:**
- Consumes: scalar primitives from Task 2; normalized names from Task 1.
- Produces: THOR and RED2 support for `CONS`, `CAR`, `CDR`, `NULL?`, `NIL`, and `++` as Appendix A list operations.

- [ ] **Step 1: Add failing list primitive parity tests**

Create `tests/test_appendix_a_list_primitives.py`:

```python
from thor_spec.golden import run_source


def assert_parity(source: str, expected: str, quantum: int = 80) -> None:
    assert run_source(source, model="thor", quantum=quantum) == expected
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_cons_car_cdr_null_match_on_pair_lists() -> None:
    assert_parity("(cons 1 [2 3])", "[1 2 3]")
    assert_parity("(car (cons 1 [2 3]))", "1")
    assert_parity("(cdr (cons 1 [2 3]))", "[2 3]")
    assert_parity("(null? [])", "TRUE")
    assert_parity("(null? [1])", "FALSE")


def test_append_operator_can_be_defined_from_reduce_and_cons() -> None:
    source = """
    reduce == (lambda (f id list)
      (if (null? list) id (f (car list) (reduce f id (cdr list)))))
    ++ == (lambda (a b) (reduce cons b a))
    (++ [1 2] [3 4])
    """
    assert_parity(source, "[1 2 3 4]", quantum=200)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_list_primitives.py -v`

Expected: FAIL because list primitives are missing or incomplete.

- [ ] **Step 3: Implement list primitives**

Implement `CONS` as construction of `StructLit("PAIR", (head, tail))` without reducing tail beyond required primitive argument reduction. Implement `CAR`/`CDR` for PAIR structures natively in both THOR and RED2 while preserving existing generated accessor behavior. Implement `NULL?` as `TRUE` only for `Symbol("NIL")`, `FALSE` for PAIR and other known constants, and no contraction for irreducible applications.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_list_primitives.py -v`

Expected: PASS.

- [ ] **Step 5: Regression checks**

Run: `uv run pytest tests/test_semantics_primitives.py tests/test_red2_machine_extended.py tests/test_appendix_a_list_primitives.py -v`

Expected: PASS.

---

### Task 4: Structure Definitions Generate Constructors and Accessors

**Type:** implementation
**Depends-on:** 1, 3
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/golden.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Create: `tests/test_appendix_a_struct_defs.py`

**Interfaces:**
- Consumes: `StructDef(tag, accessors)` from parser; list primitives from Task 3.
- Produces: `install_struct_definition(tag: str, accessors: tuple[str, ...], definitions: MutableMapping[str, Expr]) -> None` installing constructor `MAKE-<tag>` and accessor names `<tag>-<accessor>` in addition to existing direct accessors.

- [ ] **Step 1: Add failing structure definition tests**

Create `tests/test_appendix_a_struct_defs.py`:

```python
from thor_spec.golden import run_source


def test_tree_struct_definition_installs_appendix_a_helpers() -> None:
    source = """
    tree |= label subtrees
    tree-label == tree-label
    (tree-label (make-tree 7 []))
    """
    assert run_source(source, model="thor", quantum=80) == "7"
    assert run_source(source, model="red2", quantum=80) == "7"


def test_tree_subtrees_accessor_returns_lazy_list() -> None:
    source = """
    tree |= label subtrees
    (tree-subtrees (make-tree 1 [2 3]))
    """
    assert run_source(source, model="thor", quantum=80) == "[2 3]"
    assert run_source(source, model="red2", quantum=80) == "[2 3]"
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_struct_defs.py -v`

Expected: FAIL because `make-tree`, `tree-label`, and `tree-subtrees` are not installed.

- [ ] **Step 3: Implement struct definition helper generation**

When `tree |= label subtrees` is processed, install:

- `make-tree == (LAMBDA (label subtrees) {tree label subtrees})`
- `tree-label == (LAMBDA (value) (CAR-LIKE selector for field 0))` or equivalent native helper.
- `tree-subtrees == ... field 1`.

Use a generic implementation for any tag/accessor list. Normalize helper names case-insensitively but print using Appendix A spelling where practical.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_struct_defs.py -v`

Expected: PASS.

- [ ] **Step 5: Regression checks**

Run: `uv run pytest tests/test_appendix_a_struct_defs.py tests/test_appendix_a_list_primitives.py -v`

Expected: PASS.

---

### Task 5: RED2 Native Recursive Top-Level Definitions

**Type:** implementation
**Depends-on:** 1, 2, 3, 4
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/red2/instructions.py`
- Modify: `src/thor_spec/red2/compiler.py`
- Modify: `src/thor_spec/red2/machine.py`
- Modify: `src/thor_spec/golden.py`
- Create: `tests/test_red2_recursive_definitions.py`

**Interfaces:**
- Consumes: normalized programs from Task 1; primitives/list/struct helpers from Tasks 2-4.
- Produces: `compile_definitions(definitions: Mapping[str, Expr]) -> DefinitionImage`; `Red2Machine(image: ProgramImage, quantum: int, definitions: Mapping[str, Expr] | None = None)` or equivalent definition-loading API; RED2 `SYM` evaluates definitions recursively with Rule 9 contraction cost.

- [ ] **Step 1: Add failing recursive-definition parity tests**

Create `tests/test_red2_recursive_definitions.py`:

```python
from thor_spec.golden import run_source


def test_recursive_top_level_factorial_definition_matches_thor() -> None:
    source = """
    fact == (lambda (n) (if (= n 0) 1 (* n (fact (1- n)))))
    (fact 5)
    """
    assert run_source(source, model="thor", quantum=500) == "120"
    assert run_source(source, model="red2", quantum=500) == "120"


def test_recursive_top_level_fibonacci_definition_matches_thor() -> None:
    source = """
    fib == (lambda (n)
      (if (< n 2)
          n
          (+ (fib (1- n)) (fib (1- (1- n))))))
    (fib 7)
    """
    assert run_source(source, model="thor", quantum=2000) == "13"
    assert run_source(source, model="red2", quantum=2000) == "13"


def test_y_combinator_fibonacci_still_matches() -> None:
    source = """
    ((Y (lambda (fib n)
       (if (< n 2)
           n
           (+ (fib (1- n)) (fib (1- (1- n))))))) 6)
    """
    assert run_source(source, model="thor", quantum=2000) == "8"
    assert run_source(source, model="red2", quantum=2000) == "8"
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_red2_recursive_definitions.py -v`

Expected: FAIL on RED2 recursive definitions while THOR either passes or exposes missing earlier dependencies.

- [ ] **Step 3: Implement RED2 definition store**

Remove recursive source inlining from RED2 execution. Pass definitions into `Red2Machine`. In RED2 `_reduce()` for symbolic instruction terms, if a definition exists and quantum is available, decrement quantum once and reduce the definition in the current environment; if no definition or quantum is exhausted, keep the symbol passive. Ensure recursive definitions do not expand during preprocessing and can refer to themselves through the definition map.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_red2_recursive_definitions.py -v`

Expected: PASS.

- [ ] **Step 5: Full definition regression**

Run: `uv run pytest tests/test_golden_parity.py tests/test_red2_machine_extended.py tests/test_red2_recursive_definitions.py -v`

Expected: PASS.

---

### Task 6: Appendix A Fixture Transcription and Parity Smoke Tests

**Type:** implementation
**Depends-on:** 1, 2, 3, 4, 5
**Review:** adversarial

**Files:**
- Create: `tests/fixtures/appendix_a/sine_core.thor`
- Create: `tests/fixtures/appendix_a/game_core.thor`
- Create: `tests/test_appendix_a_fixtures.py`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: all new Appendix A syntax/runtime support from Tasks 1-5.
- Produces: fixture-level parity tests for executable SINE and GAME subsets and documentation of any intentionally omitted full-benchmark pieces.

- [ ] **Step 1: Add failing Appendix A fixture tests**

Create `tests/test_appendix_a_fixtures.py`:

```python
from pathlib import Path

from thor_spec.golden import run_source


def assert_fixture_parity(path: str, expected: str, quantum: int) -> None:
    source = Path(path).read_text()
    thor = run_source(source, model="thor", quantum=quantum)
    red2 = run_source(source, model="red2", quantum=quantum)
    assert thor == expected
    assert red2 == expected


def test_sine_core_fixture_parity() -> None:
    assert_fixture_parity("tests/fixtures/appendix_a/sine_core.thor", "0", quantum=5000)


def test_game_core_fixture_parity() -> None:
    assert_fixture_parity("tests/fixtures/appendix_a/game_core.thor", "1", quantum=5000)
```

Create initial fixture files directly from Appendix A-inspired source. `sine_core.thor` should include the SINE definitions needed to evaluate a simple exact case such as `sine 0` or a reduced Taylor subset that returns `0`. `game_core.thor` should include `tree |= label subtrees`, `make-tree`/accessor use, `maximum`/`minimum`/`static`-style list recursion, and a small expression returning `1`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_fixtures.py -v`

Expected: FAIL until fixtures and remaining behavior are implemented.

- [ ] **Step 3: Finalize fixtures and docs**

Ensure fixtures are ASCII, deterministic, and close enough to Appendix A to exercise:

- nested `let` and `letrec`
- recursive top-level definitions
- list operations (`cons`, `car`, `cdr`, `null?`, `++`)
- structure constructors/accessors from `|=`
- higher-order source functions (`map`, `reduce`, or `redtree`) where feasible

Update `docs/thor-red2-prototype.md` to state Appendix A coverage now includes executable core SINE/GAME fixture subsets, while full numeric SINE precision and full alpha-beta GAME search remain beyond the faithful prototype unless separately requested.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_fixtures.py -v`

Expected: PASS.

- [ ] **Step 5: Fixture CLI smoke**

Run:

```bash
uv run thor-spec --model thor --quantum 5000 --file tests/fixtures/appendix_a/sine_core.thor
uv run thor-spec --model red2 --quantum 5000 --file tests/fixtures/appendix_a/sine_core.thor
uv run thor-spec --model thor --quantum 5000 --file tests/fixtures/appendix_a/game_core.thor
uv run thor-spec --model red2 --quantum 5000 --file tests/fixtures/appendix_a/game_core.thor
```

Expected: SINE commands print `0`; GAME commands print `1`.

---

### Task 7: Final Verification Gate

**Type:** gate
**Depends-on:** 1, 2, 3, 4, 5, 6

**Files:**
- Test: `tests/`
- Test: `src/`

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: green Appendix A parity verification.

- [ ] **Step 1: Run pytest**

Run: `uv run pytest`

Expected: PASS.

- [ ] **Step 2: Run ruff**

Run: `uv run ruff check .`

Expected: PASS.

- [ ] **Step 3: Run mypy**

Run: `uv run mypy src tests`

Expected: PASS.

- [ ] **Step 4: Run Fibonacci CLI parity smoke**

Run:

```bash
uv run thor-spec --model thor --quantum 2000 --expr "fib == (lambda (n) (if (< n 2) n (+ (fib (1- n)) (fib (1- (1- n))))))
(fib 7)"
uv run thor-spec --model red2 --quantum 2000 --expr "fib == (lambda (n) (if (< n 2) n (+ (fib (1- n)) (fib (1- (1- n))))))
(fib 7)"
```

Expected: both commands print `13`.

- [ ] **Step 5: Run Appendix A fixture CLI parity smoke**

Run the four fixture commands from Task 6 Step 5.

Expected: SINE commands print `0`; GAME commands print `1`.

---

## Operator smoke

- do: `uv run thor-spec --model thor --quantum 2000 --expr 'fib == (lambda (n) (if (< n 2) n (+ (fib (1- n)) (fib (1- (1- n))))))
(fib 7)'`
- see: stdout is exactly `13`.

- do: `uv run thor-spec --model red2 --quantum 2000 --expr 'fib == (lambda (n) (if (< n 2) n (+ (fib (1- n)) (fib (1- (1- n))))))
(fib 7)'`
- see: stdout is exactly `13`.

- do: `uv run thor-spec --model thor --quantum 5000 --file tests/fixtures/appendix_a/sine_core.thor` and repeat with `--model red2`.
- see: both commands print `0`.

- do: `uv run thor-spec --model thor --quantum 5000 --file tests/fixtures/appendix_a/game_core.thor` and repeat with `--model red2`.
- see: both commands print `1`.
