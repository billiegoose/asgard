# SNARL/OPT

An **optimized-build sibling** of the January-1990 Version 1.0 C Head Order Reduction System.

Its `MAKEFILE` switches the Microsoft C flags from debug/no-optimization (`/Zi /Od`) to `/Ox`, and compiles `PRINTER.C` specially. Most major sources are identical or nearly identical to `SNARL/SNARL/`, but `PRIMS.C`, `DEBUG.C`, and some example material differ.

## Notable examples

- `PAP.LAM` — very small recursive factorial/fixed-point examples, potentially useful as a smoke test.
- `HUGHES.LAM`, `SINE.LAM` — larger functional examples.
- `LISTS.LAM` — prelude/list definitions.

This is useful for comparing release-era optimization experiments, but `THOR/` is a better first target for a modern C revival.
