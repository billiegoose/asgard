# Synthesizable RED2 FLOAT_V1 handoff

## Status

Bounded FLOAT support is implemented in `src/machines/synthesizable_red2_machine/machine.py` and aligned with the Concrete RED2 `RED2_FLOAT_V1` semantics.

The profile is deliberately not full IEEE-754. It supports finite normal binary64 values plus signed zero, and excludes subnormals, infinities, NaNs, and full IEEE rounding/exception behavior.

## Implemented datapaths

The Synth machine now includes fixed-width PipelineC/Pypeline-compatible helpers for:

- binary64 pack/unpack and domain validation;
- signed-zero-aware comparison;
- signed64-to-binary64 conversion;
- binary64-to-signed64 integral/truncation analysis;
- RED2 `_float_number_result` collapse semantics;
- floor/ceiling conversion;
- add/subtract;
- checked multiply/divide;
- bounded integral power for `|exponent| <= 63`.

These local fixed-width shims mirror the pinned Pypeline float algorithms while avoiding generic factory-local annotation/comparator problems in PipelineC revision `171c52b3f1411f632a07ccfc3dbfb177efa901cd`.

## Unary scalar behavior

Implemented for both direct JOIN and EP-backed reconstruction paths:

- `INC FLOAT`: add 1.0, then collapse exact integral result to INT when representable;
- `NEGATE FLOAT` / `ABS FLOAT`: preserve RED2 number-result collapse behavior;
- `FLOOR FLOAT` / `CEILING FLOAT`: return signed64 INT or typed unsupported-value fault;
- `DEC FLOAT` and `EVEN? FLOAT`: non-applicable/stuck, with no quantum consumption;
- malformed FLOAT opcode with non-`DATA_FLOAT64` kind: stuck;
- proper but excluded FLOAT64 payload: `FAULT_UNSUPPORTED_VALUE`.

## Binary scalar behavior

Implemented:

- ordinary scalar `=` for FLOAT/FLOAT, including `+0 == -0`;
- mixed passive FLOAT/INT scalar `=` remains type-sensitive false;
- `+`, `-`, `*`, `/` with either FLOAT operand produce FLOAT results without integral collapse;
- INT/INT inexact `/` crosses into FLOAT;
- numeric `<`, `>`, `<=`, `>=` across INT/FLOAT;
- `MAX` / `MIN` choose the original operand, with selected FLOAT passed through number-result collapse;
- `EXPT` accepts exact integral numeric exponents and uses bounded FLOAT power;
- negative INT exponents cross into FLOAT;
- `MOD` remains integer-only and is rejected as stuck before FLOAT payload decoding, matching Concrete ordering.

Fault/stuck boundaries intentionally match Concrete:

- malformed FLOAT kind in arithmetic: stuck;
- proper excluded FLOAT64 in arithmetic other than MOD: `FAULT_UNSUPPORTED_VALUE`;
- malformed INT kind when FLOAT conversion is required: `FAULT_ILLEGAL_TRANSITION`;
- FLOAT divide by zero: `FAULT_UNSUPPORTED_VALUE`;
- non-integral FLOAT exponent: `FAULT_UNSUPPORTED_VALUE`;
- bounded hardware FLOAT exponent magnitude above 63: `FAULT_UNSUPPORTED_VALUE`.

## Validation checkpoint

Completed gates during implementation:

- `tests/test_synthesizable_red2_static.py` + Concrete primitive/closure/struct regressions: **145 passed**;
- full native `scripts/check_syn_sim.py` parity, including the final malformed-INT/FLOAT kind regressions: **PASS**;
- `python -m py_compile` for the Synth machine and simulator harness: **PASS**;
- `git diff --check` for the FLOAT implementation, simulator regressions, and this handoff: **PASS**;
- pinned PipelineC frontend-only gate: **PASS**;
- emitted top: `SynthesizableRED2Machine_0CLK_f1a3d12d.vhd`;
- emitted top size: **51,880,461 bytes**;
- authoritative frontend gate elapsed time on this workstation: about **1233.5 s**;
- native parity is rerun by `scripts/check_syn.py --frontend-only` and passed in that gate;
- after that frontend gate, only simulator regression coverage and this handoff changed; the synthesizable machine source itself was not modified.

The very long frontend runtime is not specific evidence of the FLOAT changes: a pre-FLOAT HEAD frontend probe also spent minutes in PipelineC's output-writing phase. The completed FLOAT frontend produced roughly 59 MB across 284 intermediate files, with the top-level VHDL alone about 51.9 MB.

## Scope note

No attempt was made to add subnormal arithmetic, NaN/Inf semantics, or correctly rounded general IEEE-754 behavior. Those remain explicitly outside `RED2_FLOAT_V1`.
