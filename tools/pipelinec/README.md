# Enhanced RED2 compiler

Run `git submodule update --init tools/fpgatool`, then
`python scripts/setup_pipelinec.py` from the Asgard root. The script reads
the sibling `../PipelineC` Git object database, exports the pinned revision into
`build/pipelinec-enhanced-<manifest-hash>`, and applies the hash-verified patches listed in
`manifest.json` from `tools/fpgatool/toolchain/patches/`. It does not change the
sibling checkout. Use `--checkout /path/to/PipelineC` when needed.

`scripts/run_syn.py`, `scripts/check_syn_sim.py`, and `scripts/check_syn.py` use
this compiler by default. `PIPELINEC_ROOT` overrides the location; its lowering,
runtime, scheduling, VHDL and backend files must match `manifest.json`. The
older `PipelineC-pypeline-red2-pinned` checkout is rejected. The explicit hardware
gate also requires this verified compiler rather than an arbitrary executable
on PATH.

The base is upstream `2fe880d19852b8df0df1aae00f469c8be6fe8ce1`. The patch pair retains
the RED2 enhancements used by the LUT experiments, including priority-preserving elif
branch merging, generated-instance disambiguation, and software comparison
operator lowering. Fingerprints identify the actual files, including patches,
rather than relying on the base revision alone. The shared BoolOp patch is
applied first, followed by `pypeline-red2-enhancements.patch`. The port drops old
name-resolution compatibility hunks whose resulting lookup order is already in
upstream, preserving upstream's injected design parameter support.

Each manifest has its own installation directory, so updating a pin preserves
the previous compiler. Explicit `PIPELINEC_ROOT` overrides still require the
current fingerprints. The old `build/pipelinec-enhanced` tree remains available
for reproducing the original measurements, with patches at fpgatool `fa94add`
and base `d991e1f931a2303e3daa4f6256755f3ab47dd9c3`. Remeasurement with the new
compiler and the repaired full-arithmetic source uses **50,353 total LUTs** (50,035 logic
plus 318 RAM), versus the historical 50,287. Both use the same Yosys/GHDL backend
and flattened area recipe. The source repair and compiler upgrade both changed
between measurements, so the 66-LUT increase is not a compiler-only comparison.
See [the measurement record](../../docs/handoffs/synth-red2-upstream-lut-results.json)
for resources, provenance and scripts. This exceeds Basys 3's 20,800 LUTs;
placement, routing and timing have not been verified.

The hardware top now defaults to `RED2_SYN_FLOAT=0`. Omitting floating arithmetic
maps to **41,705 total LUTs** (41,387 logic plus 318 RAM), saving 8,648 LUTs (17.2%)
under the same recipe. Set `RED2_SYN_FLOAT=1` before elaboration to include the
module. The native `syn` CLI and direct full parity suite default to including
it; an explicit environment override still wins. `check_syn.py` selects
`check_syn_integer_profile.py` for the hardware default and `check_syn_sim.py`
when floating arithmetic is enabled.

The smaller profile preserves integer arithmetic, FLOAT transport through graph
operations, type predicates, structural equality and scalar FLOAT `=`. Requests
that need the omitted module fault explicitly with `FAULT_UNSUPPORTED_VALUE`.
This includes inexact integer division and the negative-exponent path that
requires a floating reciprocal. Integer division with an exact quotient remains
supported. Omitting the module does not round or approximate results. The profile
gate checks supported contractions against Concrete RED2 and verifies that
unsupported requests preserve architectural state and graph/control RAM.

A shared serial integer multiplier was also validated, but maps to 50,709 LUTs
with floating arithmetic enabled, 356 more than the baseline. It is rejected for
this LUT-fitting task despite saving 20 DSPs. See the new
[area experiment record](../../docs/handoffs/synth-red2-area-next-results.json)
for both candidates and their validation.

The fpgatool submodule pins the shared patch sources. Its board build has a
separate compiler pin and does not automatically apply the RED2 patch. Updating
the PipelineC fork's default branch does not advance either compiler pin.

The shared `toolchain/tests/check_red2_compiler.py` regression compares native
execution with emitted VHDL using NVC. See the shared patch README for its command
and coverage. Validation on this pin passed the monolithic native RED2 parity
suite, focused RECP/Fibonacci/selector-promotion checks, and 1,213 ordinary tests
(three existing environment-dependent exclusions). NVC analyzed all 320 emitted
VHDL files for the production top. The BoolOp regression also reproduces a
duplicate-instance elaboration error when generated-instance tagging is removed.

Setup requires Git and Python's standard library. The existing `mise syn-check`
task supplies the Python frontend dependencies; FPGA mapping still needs the
external synthesis tools. Setup and `--frontend-only` do not establish FPGA fit
or timing.

A subsequent graph/control RAM write-data rewrite maps to **41,170 total LUTs**
(40,852 logic plus 318 RAM), saving another 535 LUTs from the hardware profile.
Addresses, write enables, all data bits and RED2 behavior are preserved. See
[the bus measurement record](../../docs/handoffs/synth-red2-bus-area-results.json).
The design still exceeds Basys 3 capacity; no routing/timing result is claimed.
