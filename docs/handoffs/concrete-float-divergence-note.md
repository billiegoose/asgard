# RED2 FLOAT hardware profile decision

## Status

The former Concrete RED2 Chapter-4 FLOAT capability gap is now closed for the project's bounded hardware profile.

`RED2_FLOAT_V1` keeps the existing RED2 ABI binary64 payload and implements ordinary finite floating-point numeric execution plus mixed INT/FLOAT coercion. The reference behavior is deliberately aligned with PipelineC/Pypeline's existing `include/pypeline/floating_point.py` implementation rather than silently inheriting Python's host FPU.

## Supported domain

`RED2_FLOAT_V1` supports:

- binary64 finite normal values;
- signed zero;
- INT -> FLOAT coercion using the Pypeline-style truncating conversion;
- FLOAT -> integer conversion where RED2 primitives require it;
- `+`, `-`, `*`, `/`;
- `<`, `>`, `<=`, `>=`;
- type-sensitive `=`;
- `MAX` and `MIN`;
- `1+`, `MINUS`, `ABS`, `FLOOR`, `CEILING` on FLOAT where Abstract RED2 defines them;
- fractional integer division producing FLOAT;
- `EXPT` when the exponent is an exactly representable integer, including negative integer exponents.

The Chapter-4 cases that originally exposed the gap now execute normally:

```text
(+ 1.5 2.25)  -> 3.75
(+ 2 1.5)     -> 3.5
(/ 7 2)       -> 3.5
(EXPT 2 -1)   -> 0.5
```

Concrete regression tests compare these common cases directly against `AbstractRED2Machine` committed architectural state.

## Deliberately excluded domain

This profile is **not full IEEE-754**. The following are intentionally outside the hardware contract:

- subnormal operands/results;
- infinities;
- NaNs;
- IEEE rounding-mode guarantees or exact IEEE rounding behavior;
- arbitrary fractional-exponent `EXPT` requiring a transcendental power implementation.

Unsupported values/results fault deterministically instead of falling through to Python host floating arithmetic.

This matches the level of rigor in Pypeline's current floating-point library, whose own contract describes common-case IEEE-754-shaped arithmetic while omitting special subnormal/Inf/NaN/rounding handling.

## Architectural rationale

RED2 is the target architecture; designing a novel ALU/FPU is not a project goal. PipelineC/Pypeline already supplies synthesizable float32/float64 arithmetic and conversion operators, including worked synthesis examples. `RED2_FLOAT_V1` therefore defines the RED2-side contract that those existing operators can implement in Synth.

Concrete uses a small bit-oriented compatibility model in `concrete_red2_machine/float_profile.py`. This avoids making Concrete more capable than Synth by accidentally delegating semantics to Python's native floating-point implementation.

## Remaining bounded numeric refinements

The following remain finite-hardware restrictions rather than thesis semantic disagreements:

- signed-64 integer overflow;
- finite graph/control/environment storage;
- bounded addresses/counters/literal IDs;
- graph/environment collision;
- bounded traversal/workspace limits.

Fractional integer division and negative integer exponentiation are no longer classified as bounded-domain failures: they now enter the supported FLOAT result domain.

## Synth target

Synth should implement the same `RED2_FLOAT_V1` contract using Pypeline's existing `float64_t`, registered `+ - * /` operators, comparisons/conversions where available, and bounded multi-cycle/resource-sharing machinery where appropriate. It should not introduce a bespoke RED2 FPU.
