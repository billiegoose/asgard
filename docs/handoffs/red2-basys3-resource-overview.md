# RED2 Basys 3 resource overview

Measured candidate: `cfg-integer-joins-regfix`, generated source SHA256
`f229a2755c11376093f876e46e9b175148c98727e6e638f179f5e5e53258da68`.
These are the dedicated RED2 hardware measurements, with floating-point
arithmetic disabled and integer arithmetic retained.

## Whole design

| Resource | RED2 core | UART/board wrapper delta | Complete board | Basys 3 capacity |
| --- | ---: | ---: | ---: | ---: |
| Mapped LUTs, including LUT RAM | 19,172 | 878 | 20,050 | 20,800 |
| Flip-flops | 8,095 | 2,180 | 10,275 | 41,600 |
| BRAM36 equivalents | 34.5 | 0 | 34.5 | 50 |
| DSP48 | 20 | 0 | 20 | 90 |
| CARRY4 | 774 | 19 | 793 | 5,200 |

LUT utilization is 96.4%; BRAM is 69%, flip-flops 24.7%, and DSPs 22.2%.
The wrapper delta includes the full-width UART command/status monitor, clock
generator, clock gate and LEDs. It is not a UART-only estimate.

The selected saved placement occupies **19,984 unique physical LUT sites**,
leaving 816. Mapping totals and physical sites differ because packing can share
the two outputs of a physical LUT. Counting A5LUT and A6LUT as separate physical
LUTs would overcount. Final routed fit and timing are recorded separately in
`synth-red2-basys3-bringup-results.json` as they become available.

## Exact memory attribution

| Storage | BRAM36 equivalents | Purpose |
| --- | ---: | --- |
| Microcode index ROM | 6 | Maps control row to dictionary word |
| Microcode dictionary ROM | 9 | Shared microinstructions |
| Microengine scratch RAM | 2 | Persistent state, temporaries and constants |
| State-transfer plan ROM | 1.5 | Imports/exports between engine and hardwired state |
| Graph RAM | 2 | RED2 graph words |
| Control RAM | 2 | RED2 control words |
| Promotion materialization RAM | 2 | Materialization bookkeeping |
| Publication root RAM | 1 | Publication roots |
| Publication task RAM | 3.5 | Publication work queue |
| Publication patch RAM | 2.5 | Deferred graph patches |
| Publication patch-address RAM | 0.5 | Patch addresses |
| Publication materialization RAM | 2.5 | Publication materialization bookkeeping |
| **Total** | **34.5** | |

In addition, literal metadata occupies **126 LUT RAM sites**, and promotion
forwarding occupies **200 LUT RAM sites** (50 RAM256X1S instances). These 326
sites are included in the LUT totals above.

Graph storage itself is four BRAMs when graph and control memory are combined.
The large LUT cost is in control and data selection/manipulation surrounding
storage; it is not a graph implemented entirely in flip-flops.

## Exact register ownership

The companion `red2-basys3-resource-attribution.json` matches source `Reg`
declarations to mapped flip-flop Q-bit aliases. This is storage ownership,
not a complete functional cost estimate.

| Named state owner | Flip-flops |
| --- | ---: |
| Remaining root core state | 3,426 |
| State-transfer bridge | 2,010 |
| Shared microengine | 1,960 |
| Integer arithmetic state | 532 |
| Unattributed/compiler or memory pipeline state | 167 |
| **Core total** | **8,095** |

The remaining root state includes RED2 state, remaining hardwired handlers and
interface state. The bridge and remaining state also need muxes, decoders,
write enables and routing, whose LUT costs cannot be inferred by counting bits.
ABC flattened and shared combinational logic: assigning exact per-function LUT
totals from its generated LUT names would be misleading.

Reproduce the storage attribution from the frozen prepared core:

```sh
python3 scripts/experiments/red2_cfg_pilot/attribute_resources.py \
  /tmp/asgard-area-next/cfg-integer-joins-regfix/integrated-stream/machine.py \
  build/red2-basys3/core.json
```

## Arithmetic

There are two distinct 64-bit multipliers, using **10 DSP48s each**. One
finishes ordinary integer multiplication after magnitude/domain preflight;
the other handles integer exponentiation. Division already performs an
iterative shift/subtract step, rather than instantiating a full combinational
divider. Dropping division therefore is not an obvious large LUT win.

An earlier serial-multiply experiment removed DSPs but added 356 LUTs on its
then-current baseline. This is evidence against assuming that slower
arithmetic automatically saves LUTs; it is not a projection for this candidate.
Sharing the current multipliers could save DSPs, but operand selection and
control must be measured against the LUT budget.

## What further microcoding would mean

The current design is already substantially microcoded: 122 logical entry
points, 14,550 control rows, 5,663 unique dictionary words, 594 allocated scratch
words, and 156 shared bridge words. Earlier work moved 5,683 bits of private
state into engine storage. Function application, lookup, structures,
publication and many equality/continuation/integer JOIN paths already use the
shared engine. The immutable ROM sequences drive dedicated RED2 hardware.

Further cycle-for-area tradeoffs are plausible. The strongest next experiment
is a unified graph datapath that keeps RED2 state in BRAM and removes the
hybrid import/export boundary: a few work registers, one address/arithmetic
lane, and serialized graph/control requests and writeback. Remaining handlers
would become ROM sequences over this datapath. Graph-specific microoperations
could also replace verbose source-derived sequences and reduce control-ROM
storage. Arithmetic and hardware drivers can remain separate modules.

This requires actual resource sharing. Extra pipeline registers or idle cycles
alone do not remove LUTs. Narrower or word-serial accesses can reduce wide
selection networks, at the cost of more clocks for each reduction. Ordering,
aliasing, publication preflight/commit, fault and reset behavior must remain
faithful to RED2; intermediate writes cannot expose a partially committed
reduction where the semantics prohibit it.

Earlier isolated APP/LAMBDA experiments fell from 3,977 to 1,481 LUTs when
replaced by shared hardware. Later integrated migrations also produced large
measured reductions. Those measurements establish that the approach can work;
they are different variants and must not be added into a fictional block
budget for today's core. No exact further LUT target is established yet.

The next useful measurement is a prototype that unifies graph address,
request and writeback paths, checked against the existing native/RTL semantic
traces and synthesized with the same enhanced PipelineC toolchain. Compare
LUTs, BRAM, routed timing and clocks per workload before expanding it.

The application replay's 10,703 clocks are a whole command/program trace, not
the cycle count of one RED2 reduction.
