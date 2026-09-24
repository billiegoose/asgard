# Pypeline/PipelineC RED2 Processor

## Scope

`red2_stepper.py` now defines **RED2_ABI_V1**, the fixed-width hardware contract
used by the stateful processor work. It deliberately does not reuse the older
32-bit compiler-image format as live machine memory: faithful `MuredMachine`
words include additional opcodes, `definition`, `closure_slot`, and populated
workspace cells with no opcode.

The ABI currently freezes:

- 16-bit physical RAM cell addresses plus 17-bit environment/frontier path registers, so path `65536` represents one-past-end in a 65,536-word arena;
- 32-bit quantum/counter and literal-ID registers;
- signed 64-bit integer scalar payloads and IEEE-754 binary64 bit payloads;
- every current `MuredOpcode`, plus a distinct populated `None` opcode tag;
- word `head`, `definition`, and `closure_slot` metadata;
- forward/reverse direction, run status, deterministic fault IDs and host-call IDs;
- typed fixed-width control entries for addresses, saved primitive/fire/quantum,
  saved definition paths, subgraph frames and equality frames.

Empty RAM is encoded separately from `Word(None, ...)`. Source strings and
primitive names are assigned finite literal IDs by the host-side
`RED2ABICodec` in `red2_engine.pipelinec_vectors`; strings and Python objects do
not enter processor memory. Likewise Python diagnostics (`cycles`, memory-event
lists, peak statistics, poisoning configuration) are not architectural state.

`RED2_PRIM_SEQ_V1` keeps primitive sequencing string-free. `PRIM_1` and
`PRIM_2` derive strict collection arity from the opcode. The host loader may
also provide a bounded literal-ID-indexed `PRIM_0` role image for zero-arity
names whose collection behavior is special. Definition targets remain finite
encoded addresses in each `SYM` word; source names are never consulted by the
processor. Task 5 stops at the ready-to-contract boundary: scalar contractions,
lazy IF/Y semantics and host effects are implemented only by later slices.

`RED2_SCALARS_V1` adds a bounded literal-ID-indexed scalar-op image supplied by
the host loader. The core never dispatches on primitive strings. Native scalar
execution is signed 64-bit integer arithmetic/comparison plus boolean and type
predicates. Integer overflow, divide/modulo by zero, integer division requiring
a fractional FLOAT result, negative-exponent `EXPT`, and arithmetic/comparison
that would require floating-point execution fault deterministically with
`FAULT_UNSUPPORTED_VALUE`; they never inherit Python arbitrary precision or
Python float arithmetic. Ordinary strict type mismatch remains an unreduced
(stuck) RED2 spine, matching `MuredMachine`. Each successful scalar contraction
decrements `q` exactly once regardless of processor clock count.

Float values retain their IEEE-754 binary64 ABI representation, and predicates
such as `FLOAT?` may inspect the opcode, but Task 6 intentionally provides no
native floating-point execution unit.

`RED2_LAZY_V1` adds non-strict `IF` and `Y`. Boolean `IF` splices only the
selected branch, including bounded EP-chain chase, without creating a JOIN or
forcing the dead branch. Stuck conditions expose the same encoded
`__IF_RECONSTRUCT__` primitive and saved-quantum control entry as the Python
machine. `Y` points recursive APPs back to the original problem-code argument
and reuses one preflighted scratch word for immediate arguments; capacity
faults occur before architectural graph/control mutation.

The retained `red2_step_word` function is only the original 32-bit word-level
frontend/golden smoke artifact. It is not the processor execution semantics.

## Local Checks

Run the dependency-light ABI/static checks without FPGA vendor tools:

```bash
uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py
```

Run the Task 7 lazy-control parity gate with:

```bash
uv run pytest -q tests/test_pypeline_red2_lazy.py tests/test_pypeline_red2_programs.py
```

## External Validation

The explicit hardware gate is:

```bash
mise run pypeline-red2-check
```

The tested upstream PipelineC/Pypeline revision is
`171c52b3f1411f632a07ccfc3dbfb177efa901cd`. Point `PIPELINEC_ROOT` at a checkout
of that exact revision, or provide an installed `pypelinec`/`pipelinec` launcher
on `PATH`. The mise task provisions only the frontend's Python-side `setuptools`
(distutils compatibility) and `pyrtl==0.11.3` dependencies; generated HDL and
vendor/open-source synthesis artifacts stay in a temporary directory.

Unlike ordinary pytest, this gate is deliberately non-skipping. A missing
frontend is an error, a revision mismatch is an error, and the full gate first
preflights the generic PyRTL backend's real Yosys/GHDL prerequisites. A missing
synthesis backend is therefore an explicit error rather than being hidden behind
PipelineC's later `No synthesis tool install detected ... Skipping synthesis`
path. `--frontend-only` runs the supported
`pypelinec --no_synth` path, including normal trim/collapse and VHDL emission for
`red2_processor_top`, and then runs the native Pypeline RED2 parity checker. The
hardware top is `models/python/pypeline_red2/red2_pypeline.py`; the separate
`Red2Processor` class remains the CPython architectural model/oracle.

The RED2 source deliberately keeps the large request and microstate dispatches
flat rather than expressing them as deep Python `elif` trees. This is a
frontend-shape optimization only: the request predicates are mutually exclusive,
and the state-transition dispatch preserves priority with an entry-state
`clock_dispatch_handled` guard. At the tested PipelineC revision this reduces the
post-trim RED2 graph enough for the stock supported `--no_synth` flow to complete
and emit the full VHDL top.

A successful *full* gate additionally requires a real synthesis exit with
target/resource/timing evidence. `RED2_SYNTH_V1` remains withheld until the
hardware source marks its persistent reducer semantics complete and that
synthesis proof succeeds; frontend acceptance or VHDL emission alone does not
make that claim.
