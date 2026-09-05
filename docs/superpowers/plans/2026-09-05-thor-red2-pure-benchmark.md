# Pure Python THOR vs RED2 Benchmark Battery Implementation Plan

**Grammar:** claims-v1

**Claim:** do: Run a small battery of pure THOR workloads through the Python THOR and faithful Python RED2 engines; see: recursion, list construction/traversal, user-defined STRUCT construction/traversal, and a mixed Appendix-A game workload all agree on deterministic results before the runner reports repeatable in-process timing comparisons, with any discovered RED2 correctness defect fixed rather than hidden from the benchmark set. (elicited)

**Goal:** Replace the single-workload benchmark idea with a conformance-first microbenchmark battery. Fix the faithful RED2 recursive user-STRUCT defect uncovered during planning, add orthogonal pure workloads, and benchmark both Python engines at the same fair boundary: shared parsing/normalization outside timing; backend-specific preparation, execution/reduction, and result materialization inside timing.

**Tech Stack:** Python 3.14, THOR parser/normalizer/Chapter-3 reducer, faithful Python `MuredMachine`, pytest, Ruff, mypy, `time.perf_counter`, `statistics.median`, mise.

**Spec:** user request in chat on 2026-09-05 to extend the pure benchmark into a series of little benchmarks including data structures so the suite also exposes obvious implementation brokenness; planning probes on 2026-09-05 showed dynamic PAIR/list construction works in both engines, static user-STRUCT traversal works in both, but recursive dynamic user-STRUCT construction fails faithful RED2 at depth 4 with `GraphEnvironmentCollision` while THOR returns the correct checksum.

## Global Constraints

- All benchmark workloads are pure THOR: no IO monad forms, UART, CLOCK, LEDS, TICKS, host callbacks, filesystem access, subprocesses, or wall-clock reads in benchmark source.
- The default battery contains four deliberately different workloads: `tak` for recursive application/branching/arithmetic; `list` for dynamic PAIR/CONS construction plus CAR/CDR traversal; `struct` for dynamic user-defined STRUCT construction plus generated selector traversal; and `game` for the existing Appendix-A depth-1 mixed list/STRUCT/LETREC/minimax path.
- Correctness is a prerequisite to timing. Every selected workload must first compute its deterministic expected result in both engines; a mismatch or engine failure makes the command fail rather than omitting that workload or printing a misleading partial comparison.
- The RED2 `GraphEnvironmentCollision` found by the dynamic STRUCT probe is a correctness bug to repair, not an expected-failure benchmark result. The repair must work with the existing faithful loader default `memory_words=65_536`; do not solve it by increasing benchmark memory, disabling graph/environment collision checks, or special-casing the benchmark program.
- Planning evidence for the STRUCT bug: `sum-node(build-node 2)` and depth 3 pass in both engines; depth 4 returns `10` in THOR but faithful RED2 reaches `fsp=65334`, `env_frontier=65335` after 66,149 cycles and raises from `_app -> _push_graph`, showing runaway graph/environment growth consumes the working region below live environment frames.
- Shared parsing and normalization happen exactly once per selected benchmark before preflight, warmup, or measured samples. They are excluded from backend timing.
- Every timed sample starts from the same normalized expression and visible definitions, then includes that backend's ordinary backend-specific preparation plus execution/reduction and final `to_source` result materialization. THOR includes definition translation inside `reduce_expr`; RED2 includes compilation/loading inside `load_faithful_machine`.
- RED2 measured runs call `MuredMachine.run(cycle_limit=...)` with an explicit configurable cycle limit rather than inheriting `run_source`'s current 100,000-cycle default. Do not change `MuredMachine.run()`'s default as part of this slice.
- Warmup samples are excluded from statistics. Measured samples use `time.perf_counter`; median is the primary timing and best sample is a secondary diagnostic.
- Every warmup and measured execution must still match the benchmark's expected deterministic result. Buffer successful CSV rows until the complete selected run passes so a late failure cannot leave apparently valid partial benchmark output.
- Report THOR `ReductionResult.steps` as `thor_contractions` and RED2 `MuredMachineState.cycles` as `mured_cycles`. These are backend-native work counters, not equivalent instruction units; do not divide or compare them as an instruction ratio.
- The timed path is in-process and must not invoke `mise`, `uv`, a backend CLI, or `subprocess`. Investigation probes may have used subprocess timeouts, but the benchmark implementation may not.
- `tools/videos/benchmark_breakout.py` and `benchmark-breakout` remain behaviorally unchanged. Documentation must distinguish its command-level/IO-heavy measurement from the new pure in-process backend battery.
- `archives/` and the unrelated untracked Python RED2 IO plan artifacts remain untouched.

**Acceptance:** suite — focused recursive-STRUCT regression tests, pure benchmark fixture parity tests, runner tests, mise/docs integration tests, full Python pytest/Ruff/mypy gates, and one `benchmark-python --benchmark all` smoke prove the battery is correct and runnable without asserting a performance winner.

**Parallelization rationale:** four implementation tasks form one runtime-dependent chain of width 1. The benchmark fixtures intentionally include the recursive user-STRUCT behavior fixed by Task 1; the runner executes Task 2's real fixtures; mise/docs execute Task 3's real CLI. Task 5 is verification-only. Runtime memory-lifetime, performance, and termination behavior make this a high-risk execution despite the linear shape, so the Ultrapowers risk override applies.

### Task 1: Repair recursive user-STRUCT execution in faithful RED2

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Test: `tests/test_red2_recursive_structs.py`

**Claim:** Faithful Python RED2 can recursively construct and traverse user-defined STRUCT values of practical benchmark depth without exhausting its normal graph/environment working region, while genuine graph/environment collision protection remains intact. (derived)
Machine: M1. A direct faithful-RED2 program defining `node |= value next`, recursively building chains at depths `4`, `8`, and `16`, and recursively summing their fields completes with exact results `10`, `36`, and `136` using `load_faithful_machine(..., memory_words=65_536)` and an explicit sufficient cycle limit. M2. The same depth-4 source still returns `10` under THOR, establishing parity rather than a RED2-only altered semantics. M3. The fix does not raise `load_faithful_machine`'s 65,536-word default, disable `_validate_state`/`_push_graph` collision checks, or convert a genuinely colliding synthetic machine state into success. M4. Existing recursive-definition, STRUCT helper, and PAIR/list RED2 regression suites remain green.

**Authorized-by:** plan-level user request to include STRUCT-heavy benchmarks and use them to expose brokenness; planning probe and depth-4 trace on 2026-09-05; existing faithful memory-safety invariant in `MuredMachine._validate_state` and `_push_graph`.

**Interfaces:**
- Consumes: none
- Produces: `red2-recursive-user-struct`

**Context:** The reproduced failure is not a 65,536-word capacity requirement: a four-node chain should be tiny, yet after 66,149 cycles the graph grows upward to `fsp=65334` while the environment frontier has fallen to `65335`, and the next reverse APP join allocation raises from `_app -> _push_graph`. Existing tests cover basic STRUCT contraction, selectors, lazy zero-quantum reconstruction, and environment non-reuse after path restore, but there is no end-to-end regression for a recursively produced multiword user STRUCT that is then selected/traversed. Repair the general graph/environment lifetime or unwind semantics responsible for the growth; do not special-case tag `node`, depth 4, this source text, or benchmark names. Preserve deliberate collision detection. A correct repair should make deeper chains complete in the ordinary loader memory rather than merely moving the failure outward.

**Proof:**
- Test: `tests/test_red2_recursive_structs.py`
- Legs: (a) parametrized direct-machine tests run dynamic user-STRUCT chains at depths `4`, `8`, and `16` with `memory_words=65_536`, assert exact results `10`, `36`, and `136`, and fail on `GraphEnvironmentCollision` or cycle exhaustion [M1]; (b) the depth-4 source is also executed through THOR and the test fails if its result is anything other than exact `10` [M2]; (c) the test fails if `load_faithful_machine`'s `memory_words` default differs from `65_536`, fails if `_validate_state`/`_push_graph` collision checks are absent or bypassed, and fails unless a deliberately colliding small `MuredMachineState` still raises `GraphEnvironmentCollision` [M3]; (d) `uv run pytest -q tests/test_red2_recursive_definitions.py tests/test_appendix_a_struct_defs.py tests/test_appendix_a_list_primitives.py tests/test_red2_recursive_structs.py` exits 0 [M4].

**Stale-if:**
- sha-matches: `models/python/red2_engine/mured.py`@677f6921fd686c6f5a226701563d491fd74d3b046d979e0de5e5a74aa41a67c8
- sha-matches: `models/python/thor_compile/red2.py`@2b8364ab2f2457776725214ec5b74a2e15b4ec539bba56119db9ef383f5cf6d7
- path-exists: `tests/test_red2_recursive_structs.py`

### Task 2: Add the pure benchmark battery

**Type:** implementation
**Review:** peer

**Files:**
- Create: `benchmarks/tak.thor`
- Create: `benchmarks/list-build-sum.thor`
- Create: `benchmarks/struct-build-sum.thor`
- Test: `tests/test_pure_benchmarks.py`

**Claim:** The benchmark battery contains orthogonal pure workloads for recursion, dynamic lists, dynamic user-defined STRUCTs, and the existing mixed Appendix-A game path, and both Python engines compute the same deterministic checksum for every workload. (derived)
Machine: M1. `benchmarks/tak.thor` runs `(tak 8 5 3)` three times inside THOR and yields `15`; it uses recursive application, `IF`, `<=`, `1-`, and `+` but no list or user-STRUCT operations. M2. `benchmarks/list-build-sum.thor` recursively constructs the list `24..1` with `CONS`, then traverses it with `NULL?`, `CAR`, and `CDR`, yielding `300`. M3. `benchmarks/struct-build-sum.thor` declares `node |= value next`, recursively constructs a 24-node user-STRUCT chain, traverses it through generated selectors, and yields `300` without list primitives. M4. `tests/fixtures/appendix_a/game_full.thor` remains the fourth benchmark, yielding `8` and exercising a mixed list/STRUCT/LETREC/minimax workload. M5. All four benchmark sources are pure with respect to the forbidden IO/runtime facilities in the Global Constraints, and neither engine is required to be faster.

**Authorized-by:** plan-level user request; Task 1 runtime contract; planning calibration showing Tak repeat-3 parity, dynamic list size 24 parity (`300`), current Appendix-A GAME parity (`8`), and the desire to turn user STRUCT construction into a first-class benchmark after its RED2 defect is repaired.

**Interfaces:**
- Consumes: `red2-recursive-user-struct`
- Produces: `pure-benchmark-battery`

**Context:** Keep each new benchmark as one deterministic, self-contained THOR program with exactly one final benchmark expression so the runner can parse it once and split definitions from the expression. The workloads should be small enough for repeated local runs but substantial enough to exercise different reducer paths. Planning direct-seam calibration measured dynamic list size 24 at roughly 0.47 seconds THOR / 0.54 seconds RED2 and Tak repeat-3 in the few-tenths-of-a-second range. The STRUCT benchmark uses the same size-24 checksum shape as the list benchmark so its semantics are obvious; the `red2-recursive-user-struct` consumed contract permits verifying that size 24 is practical under the explicit benchmark limits, but do not reduce it merely to dodge a correctness failure. The existing depth-1 GAME fixture is intentionally reused rather than duplicated. SINE is not included in the default battery because the current fixture completes in only a few milliseconds and adds little timing signal.

**Proof:**
- Test: `tests/test_pure_benchmarks.py`
- Legs: (a) a parity helper prepares each source once and executes each backend three independent times, using THOR `reduce_expr` and faithful RED2 `load_faithful_machine(...).run(cycle_limit=2_000_000)`, and fails unless all three results within each backend and across both backends equal the workload's exact checksum; this avoids `run_source()`'s 100,000-cycle RED2 default, and source-shape checks additionally require `tak.thor` to yield `15` while containing no list or user-STRUCT constructs [M1]; (b) the same repeated direct parity helper requires all six list executions to equal exact `300`, while source inspection requires dynamic `CONS` construction plus `NULL?`/`CAR`/`CDR` traversal and fails if the source declares or uses any user-defined STRUCT constructor/accessor [M2]; (c) the repeated helper requires all six STRUCT executions to equal exact `300`, while source inspection requires `node |= value next`, recursive `make-node`, `node-value`, and `node-next` and rejects `CONS`, `CAR`, and `CDR` [M3]; (d) the GAME fixture is executed three independent times in each backend and all six results must equal exact `8`, while source inspection confirms both list and `tree |=` STRUCT operations plus `letrec` [M4]; (e) all four sources are scanned for forbidden IO/runtime tokens and the tests contain no speed-order assertion [M5].

**Stale-if:**
- path-exists: `benchmarks/tak.thor`
- path-exists: `benchmarks/list-build-sum.thor`
- path-exists: `benchmarks/struct-build-sum.thor`
- sha-matches: `tests/fixtures/appendix_a/game_full.thor`@2cfdef288cec7a20cd2a9d408ceec05e39b0b7ab433375334805728536ba53cf
- sha-matches: `models/python/thor_engine/golden.py`@59ba407f870b114b77dcd6ff8094e6a4d94c0d5e9e39f8f1962af857a0dbde71

### Task 3: Build the conformance-first in-process benchmark runner

**Type:** implementation
**Review:** peer

**Files:**
- Create: `tools/benchmark_python_engines.py`
- Test: `tests/test_benchmark_python_engines.py`

**Claim:** Running the Python benchmark tool first proves THOR/RED2 parity for every selected workload and only then reports repeatable per-workload timing and native work counters at the same prepared-source boundary, with no partial successful CSV when a workload is broken. (derived)
Machine: M1. The runner exposes benchmark choices `all`, `tak`, `list`, `struct`, and `game`; `all` is the default and maps to the four Task-2 sources with fixed expected results `15`, `300`, `300`, and `8`. M2. Each selected source is read, parsed, normalized, and split into definitions plus one expression exactly once before untimed preflight, warmups, and measured samples; the timed backend sample function performs no parse/normalize, subprocess, CLI, mise, uv, or IO-runtime call. M3. Before timing, one untimed execution in each backend must equal the registry's expected result; any mismatch, `GraphEnvironmentCollision`, `CycleLimitExceeded`, quantum/resource failure, or backend exception exits nonzero and prints no successful CSV comparison. M4. A THOR timed sample covers `reduce_expr(..., definitions=...)` through `to_source(...)` and records `ReductionResult.steps` as `thor_contractions`; a RED2 timed sample covers `load_faithful_machine(...)`, `run(cycle_limit=...)`, `result_expr()`, and `to_source(...)`, recording `state.cycles` as `mured_cycles`. M5. Successful CSV has stable columns `benchmark`, `backend`, `result`, `iterations`, `median_seconds`, `best_seconds`, `speedup_vs_thor`, `work_units`, and `work_unit_name`; `--benchmark all` emits exactly eight rows, two adjacent backend rows per benchmark, and computes `speedup_vs_thor` independently within each benchmark. M6. Defaults are `benchmark=all`, `warmups=1`, `iterations=5`, `quantum=5_000_000`, and `cycle-limit=2_000_000`; validation rejects `iterations < 1`, `warmups < 0`, `quantum < 1`, or `cycle-limit < 1`. M7. Successful exit depends only on correctness/completion/schema, never on which backend is faster; work counters must be stable across measured samples for the same backend/workload but are never compared across backends as equivalent units.

**Authorized-by:** plan-level claim and Task 2 battery contract; current THOR/RED2 direct execution seams in `thor_engine.semantics.reduce_expr` and `thor_compile.red2.load_faithful_machine`; planning direct-seam calibration demonstrating why the RED2 cycle limit must be explicit.

**Interfaces:**
- Consumes: `pure-benchmark-battery`
- Produces: `benchmark_python_engines.main(argv: Sequence[str] | None = None) -> int`

**Context:** The runner is both a benchmark and a lightweight conformance harness. Registry metadata should identify source path, display name, and expected result; do not duplicate benchmark semantics in Python beyond those facts. Preparation happens once per selected workload. Preflight is deliberately untimed and must run both engines before any CSV is committed. For each measured sample, do not cache a translated THOR definition environment and do not deepcopy/reuse a pristine RED2 machine: those would move backend-specific setup outside timing asymmetrically. Buffer result rows in memory until every selected workload/backend has completed successfully so a late STRUCT or GAME failure cannot leave a plausible partial report. `speedup_vs_thor` is `thor_median / backend_median` for the same workload, making the THOR row `1.0`; it is descriptive only. `work_units` may be an integer because deterministic samples must produce a stable count. The standard loader memory size is not a benchmark knob in this slice; the STRUCT repair must stand on the ordinary faithful machine configuration.

**Proof:**
- Test: `tests/test_benchmark_python_engines.py`
- Legs: (a) registry tests assert exact `all/tak/list/struct/game` selection, source paths, and expected results, with default selection `all` [M1]; (b) parser/normalizer spies plus timed-path guards prove each selected source is prepared exactly once and fail if timed backend execution reaches parse/normalize, subprocess, CLI, mise/uv, or IO-runtime seams [M2]; (c) real one-shot preflight tests cover all four workloads, while injected wrong-result, `GraphEnvironmentCollision`, cycle-limit, and generic backend-exception cases exit nonzero with no CSV header or successful rows [M3]; (d) backend seam spies assert the exact THOR and RED2 timed call chains and the correct native work-unit labels/counters [M4]; (e) deterministic fake timings assert exact CSV header/order, eight rows for `all`, per-benchmark THOR row `1.0`, per-benchmark speedup arithmetic, warmup exclusion, median/best aggregation, and the `result` column [M5]; (f) parametrized CLI tests reject zero/negative invalid bounds and assert all five defaults exactly [M6]; (g) fake cases where THOR wins some workloads and RED2 wins others still exit 0 when parity/counters are valid, while counter instability within one backend/workload fails the run [M7].

**Stale-if:**
- path-exists: `tools/benchmark_python_engines.py`
- sha-matches: `models/python/thor_engine/semantics.py`@cf7b5700cd6a4d3ce66b8653427f1ab8a8e7632a71f7fa381b194d1eb8a63a96
- sha-matches: `models/python/thor_compile/red2.py`@2b8364ab2f2457776725214ec5b74a2e15b4ec539bba56119db9ef383f5cf6d7

### Task 4: Expose and document the benchmark battery

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `.mise.toml`
- Create: `docs/python-engine-benchmarks.md`
- Test: `tests/test_mise_tasks.py`
- Test: `tests/test_docs_examples.py`

**Claim:** An operator can run one documented mise command for the whole pure benchmark battery or select one workload, and the documentation makes each workload's coverage, correctness gate, timing boundary, and non-comparable native work units unambiguous. (derived)
Machine: M1. `.mise.toml` exposes `benchmark-python` invoking `tools/benchmark_python_engines.py` and forwards `benchmark`, `warmups`, `iterations`, `quantum`, and `cycle-limit`; defaults run the complete battery. M2. `docs/python-engine-benchmarks.md` contains a benchmark matrix naming `tak`, `list`, `struct`, and `game`, their expected results `15`, `300`, `300`, and `8`, and the distinct reducer/runtime behavior each stresses. M3. Documentation states parity preflight happens before timing; parse/normalize is outside timing; backend preparation/execution/result rendering is inside timing; warmups are excluded; median is primary; best is diagnostic; a failed workload prevents successful comparison output. M4. Documentation states `thor_contractions` and `mured_cycles` are different native units, not directly comparable instruction counts, and no backend is required to win any workload. M5. Documentation explicitly distinguishes the new in-process pure battery from `benchmark-breakout`, and the existing `benchmark-breakout` description, usage, and run command remain unchanged.

**Authorized-by:** plan-level claim; Task 3 runner contract; existing benchmark task in `.mise.toml`; existing Breakout command-level implementation in `tools/videos/benchmark_breakout.py`.

**Interfaces:**
- Consumes: `benchmark_python_engines.main(argv: Sequence[str] | None = None) -> int`
- Produces: `benchmark-python`

**Context:** Add a sibling mise task; do not replace Breakout. The operator surface should support `--benchmark all|tak|list|struct|game`, with `all` as the normal command for conformance plus performance comparison. Documentation should call the timed quantity “backend pipeline time” or similarly precise language: THOR includes definition translation, RED2 includes AST-to-μRED compilation/loading, and both include result rendering. Explain that the suite is intentionally made of small orthogonal workloads rather than one realistic application, because differences and defects are easier to localize: Tak stresses recursion/application, list stresses PAIR allocation/traversal, struct stresses user-STRUCT allocation/selectors, GAME mixes several features. Mention the dynamic STRUCT bug as planning motivation only after it is fixed; do not document it as an expected current failure. Historical calibration numbers may be included as illustrative machine-specific observations, never assertions.

**Proof:**
- Test: `tests/test_mise_tasks.py`
- Test: `tests/test_docs_examples.py`
- Legs: (a) `mise run benchmark-python --benchmark all --warmups 0 --iterations 1 --quantum 5000000 --cycle-limit 2000000` exits 0 with eight data rows, `mise run benchmark-python --benchmark tak --warmups 0 --iterations 1 --quantum 5000000 --cycle-limit 2000000` exits 0 with exactly the two `tak` backend rows and no other workload rows, and task-source assertions prove all five public options are forwarded and `all` is the default [M1]; (b) documentation assertions find the four benchmark names, exact expected results, and a distinct stated purpose for each workload [M2]; (c) docs tests require explicit statements for parity-before-timing, parse exclusion, backend preparation/execution/render inclusion, warmup exclusion, median/best policy, and whole-run failure on workload error [M3]; (d) docs tests find both native labels, their non-comparability warning, and a no-required-winner statement [M4]; (e) `.mise.toml`'s existing `benchmark-breakout` stanza is asserted exactly equal to its pinned pre-plan description, usage, and `uv run python tools/videos/benchmark_breakout.py --iterations ...` command, while docs distinguish it as command-level/subprocess/IO-heavy [M5].

**Stale-if:**
- sha-matches: `.mise.toml`@0c5117c19d84aaa0d35774bbce96f8e68a56eb25b89c350ef488eea16fa8f439
- sha-matches: `tools/videos/benchmark_breakout.py`@a86477ecbce96017f8a4987c8c13451ce7fc49718af9cd367f87370ceffce4d4
- sha-matches: `tests/test_mise_tasks.py`@1b420a663f32cec4ba927f98d5f5f2e4bdde981d6dfc1681d8076364ac3962be
- path-exists: `docs/python-engine-benchmarks.md`

### Task 5: Benchmark battery integration gate

**Type:** gate
**Review:** peer

**Files:** none

**Claim:** The completed pure benchmark battery passes the recursive-STRUCT regression, focused workload/runner/docs tests, full Python quality gates, and a whole-battery operator smoke without IO dependencies, partial-success output, or performance-winner assertions. (derived)
Machine: M1. The recursive user-STRUCT regression and all focused benchmark ownership tests pass at the integrated implementation head. M2. Full Python pytest, Ruff, and mypy gates pass. M3. `benchmark-python --benchmark all` completes all four workloads in both backends and emits exactly eight successful rows with expected result metadata and distinct native work-unit labels. M4. Benchmark source and timed runner code remain free of IO-runtime/subprocess dependencies, the standard faithful loader memory default remains 65,536 words, the existing Breakout task is unchanged, and `git diff --check` exits 0.

**Authorized-by:** plan-level acceptance contract and repository Python verification policy.

**Interfaces:**
- Consumes: `benchmark-python`
- Produces: none

**Context:** This gate writes nothing and runs against the integrated implementation head. Focused tests are `tests/test_red2_recursive_structs.py`, `tests/test_pure_benchmarks.py`, `tests/test_benchmark_python_engines.py`, `tests/test_mise_tasks.py`, and `tests/test_docs_examples.py`. Full gates are `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy models/python tests`. The operator smoke should use one warmup-free measured sample to keep it cheap while still exercising every benchmark/backend. Acceptance concerns completion, parity, schema, labeling, and architectural boundaries, not elapsed values or speed ordering. Do not run or modify the unrelated Python RED2 IO plan or `archives/`.

**Proof:**
- Test: `tests/test_red2_recursive_structs.py`
- Test: `tests/test_pure_benchmarks.py`
- Test: `tests/test_benchmark_python_engines.py`
- Test: `tests/test_mise_tasks.py`
- Test: `tests/test_docs_examples.py`
- Legs: (a) `uv run pytest -q tests/test_red2_recursive_structs.py tests/test_pure_benchmarks.py tests/test_benchmark_python_engines.py tests/test_mise_tasks.py tests/test_docs_examples.py` must exit 0, and the gate fails if any focused ownership test fails [M1]; (b) `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy models/python tests` all exit 0 [M2]; (c) `mise run benchmark-python --benchmark all --warmups 0 --iterations 1 --quantum 5000000 --cycle-limit 2000000` exits 0, emits exactly two rows for each of `tak`, `list`, `struct`, and `game`, reports results `15`, `300`, `300`, and `8`, and uses `thor_contractions`/`mured_cycles` without any speed threshold [M3]; (d) source inspection finds forbidden IO tokens absent from the three new benchmark files, no `subprocess`/IO-runtime invocation in the timed runner path, `load_faithful_machine` still defaults to `memory_words=65_536`, the pinned `benchmark-breakout` stanza remains exact, and `git diff --check` exits 0 [M4].

**Stale-if:**
- sha-matches: `pyproject.toml`@a57bf097335563c926fedfd98d3a0b50cd55296c6c0daf1b22a94cd917d6c079
- sha-matches: `models/python/thor_engine/semantics.py`@cf7b5700cd6a4d3ce66b8653427f1ab8a8e7632a71f7fa381b194d1eb8a63a96
- sha-matches: `models/python/thor_compile/red2.py`@2b8364ab2f2457776725214ec5b74a2e15b4ec539bba56119db9ef383f5cf6d7
