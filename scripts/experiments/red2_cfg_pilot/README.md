# RED2 control-flow/storage experiment

This is an experimental hardware implementation; the maintained production top
remains a separate reference. It mechanically lowers the original typed RED2 handlers
before SSA into an immutable synchronous control ROM, synchronous BRAM scratch,
one 64-bit add/sub lane, Boolean/bit operations, and registered graph/control
ports. There is no CPU core, loadable firmware, or writable control-store port.

The first configuration covers all 16 LAMBDA and four APP handlers, their RAM
requests, and APP/LAMBDA entry paths in EXECUTE. Enabling lookup adds its four
handlers, requests, and VAR/APP_VAR entry paths on the same datapath. Full-width
graph/control payloads, typed truncation, malformed addresses, sentinels, ordered
scalar updates, faults, and handoffs come from the original source. Unsupported
AST operations fail generation. A static all-path check rejects uninitialized
operands. `control.json` records source identity, types, state ownership and
handoffs; state addresses are generated, not a stable external ABI.

One start admits one logical transition; physical latency varies with the active
branch. Start state is sampled once. Setup writes and new starts are ignored
while busy. Graph/control requests remain stable until `response_valid`, which
accepts the pair exactly once and latches both read responses. The external RAM
adapter must return read-first data for simultaneous reads/writes. A completion
is not itself a committed RED2 reduction. The addressed setup/debug port reads
and writes typed state words; valid state locations and widths are in the
manifest. It cannot modify constants or controller rows. Unused setup locations
and unsupported start states are outside this pilot's interface contract.

The original family baseline uses the same state locations, request/response
interface and admission domain, with the source handlers and named FF state.
Both models leave outer command arbitration, initial fault checks and the
original synchronous-read admission bubble to the caller. Controller reset
cancels internal activity and suppresses new requests/writes; it does not
implement architectural RESET/LOAD_STATE or undo an already accepted RAM write.

Generate and validate, with Python 3.14 and the native PipelineC dependencies
used by `scripts/check_syn_sim.py`:

The compiler Python environment must provide `setuptools` on Python 3.12 and
later. The native and frontend launchers load its maintained `distutils`
compatibility package when the standard-library package is absent. Temporary
`/tmp` import shims are no longer required; the pinned compiler stays unchanged.

```sh
export RED2_CFG_PILOT_OUT="$PWD/build/red2-cfg-pilot"
python3 scripts/experiments/red2_cfg_pilot/oracle.py
python3 scripts/experiments/red2_cfg_pilot/emit.py
python3 scripts/experiments/red2_cfg_pilot/baseline.py
python3 scripts/experiments/red2_cfg_pilot/check.py
python3 scripts/experiments/red2_cfg_pilot/check_hardware.py
python3 scripts/experiments/red2_cfg_pilot/check_hardware.py --baseline
python3 scripts/experiments/red2_cfg_pilot/frontend.py
python3 scripts/experiments/red2_cfg_pilot/frontend.py --baseline
```

Use a separate output directory and `RED2_CFG_PILOT_LOOKUP=1` for the second
configuration. Generation uses a 256-word graph. The typed oracle is extracted
directly from the original AST and runs through PipelineC's native simulator;
it is not synthesized into the candidate. Deterministic boundary/random cases
compare every family state field and every request bit. A greedy path selection
chooses physical-controller cases, including successful/failing paths. Physical
tests also delay RAM responses, vary inputs after acceptance, attempt busy
starts/setup writes, retain scratch between transitions, cancel with reset, and
check constant protection. Finite iteration budgets require actual completion.

For the recorded Nix/Podman backend, `prepare_map.py` (and `--baseline`) verifies
the enhanced compiler, emits GHDL/Yosys scripts and fingerprints every HDL input.
Run each generated `run.sh` inside the pinned Nix container with `fpgatool-nix`
mounted at `/nix` and that configuration directory at `/experiment`. Count the
result with `scripts/yosys_resources.py <directory>/baseline-area.json --top top`.
The mapper recipe matches the maintained core's flattened classic LUT6 area
flow. This helper assumes the exact Nix store paths recorded in the area report;
it does not install or change tools. Netlists and generated sources stay outside
Git, while the generator and measurement record are committed.

APP/LAMBDA alone maps from 3,977 to 1,481 LUTs; including lookup maps from 6,254
to 1,377 LUTs, with 12 BRAM36 equivalents in the latter candidate. These are
standalone comparisons. Integration must remove legacy handlers/requests and
account for all bridges to the remaining machine. In particular, several state
fields are shared with RBLOCK, definition cleanup, selector and reconstruction
paths. Publication remains a later test and must preserve preparation, external
JOIN/scalar preflight, and explicit commit authorization. Neither isolated result
establishes whole-core fit, routing, timing, or complete-program parity.

`RED2_CFG_PILOT_COMPACT=1` enables CFG-liveness allocation of temporary words
and opcode-specific control packing. Architectural cells and immutable constants
never alias. For lookup this reduces 1,438 scratch words to 146 (256-word RAM)
and the control word to 33 bits: measured storage falls from 12 to five BRAM36
at 1,459 LUT. The interference proof checks every complete live set, including
branch successors; destination reuse is safe because both operands are latched.

`RED2_CFG_PILOT_GRAPH=1` adds EP, CLOSURE, RUP and RECP entry/handler paths on
the same datapath. EP_REVERSE_CONTROL_READ stays in legacy logic because its
shared-initialization launch event is consumed outside the extracted handlers.
This scope has 56 entries, 6,229 rows, 218 allocated words and a packed 34-bit,
8,192-row control ROM. A shared 65-bit add/sub carry implements unsigned GE.
The source-derived oracle passed 6,720 cases and the physical controller passed
159 path witnesses plus reset and constant protection.

The experimental complete top is generated by `integrate.py`, then elaborated
or mapped with `frontend.py --integrated` / `prepare_map.py --integrated`.
`RED2_CFG_PILOT_INTEGRATED_NAME` selects a separate variant directory (default
`integrated`). It currently mirrors the family FF fields through serial BRAM
transfers. Its extra status bit `busy` is part of the experimental contract:
CMD_CLOCK advances a transition; CMD_NOP pauses/observes; RESET, LOAD_STATE and
START cancel; other commands are admitted when idle. Scalar observations during
busy are not a completed architectural snapshot. Accepted RAM writes cannot be
rolled back. The graph must remain 256 words. No production caller is switched.

`check_boundary.py --entries` seeds original internal states only through the
pinned simulator fixture, then drives the complete hardware top through normal
commands. It checks all selected entry states, every family leaf, RAM write
payloads and one paired request, pauses, and cancellation at different phases.
The corrected `integrated-v2` passed all 25 lookup and all 56 graph entries.
A pause in operand-consume phases originally let RAM read addresses drift;
address hold in phases four/five fixes the state-22 counterexample. The first
lookup integration's 40,826-LUT map is **rejected diagnostic evidence**, because
it predates this fix. The corrected graph full-core map is recorded separately.
`check_integrated.py` adapts the existing complete-program native suite by
waiting for actual `busy` completion, with finite failure bounds. A suite that
is still running or was interrupted is not a pass.

The standalone original family includes addressed debug/setup multiplexers that
the production core does not have. Its isolated saving is not an additive
whole-core estimate. The integrated bridge also adds selection and FF state.
Next, freeze the graph scope and make lifecycle-only private state authoritative
in BRAM, use per-entry shared transfers, and publish coherent architectural
outputs. Lifecycle initialization must preserve the difference between RESET,
LOAD_STATE, valid START and invalid START; do not clear all private cells alike.
Measure that complete top before extending connected JOIN/publication families.

`RED2_CFG_PILOT_OWNED=1` selects the next integration experiment. Generation
proves private ownership against the remaining legacy AST after extraction;
it removes 26 Reg roots (29 leaves, 923 typed bits), including their lifecycle
FF assignments. No runtime legacy reference may survive. Private scratch is
retained across owned transitions. A synchronous per-entry mask ROM enables
imports of shared read-before-write or potentially written fields, and exports
only potentially written fields. Potential conditional writes import their old
values too, so an untaken write cannot export stale scratch. The first version
still scans shared indices; masks suppress transfers, not every scan cycle.

The owned variant snapshots only observable architectural/status scalar fields,
then exposes the completed scalar result together when busy drops. This avoids
partial serial-export observations without duplicating private storage. One
lifecycle command received while busy is latched and applied after the current
logical transition completes, including already accepted RAM writes. Callers
must wait for busy to clear before sending another command. RESET/LOAD_STATE
initialize all proven private fields; valid START initializes its exact subset;
invalid START changes the original fault state without initializing private
cells. These masks are extracted from exact original lifecycle predicates and
zero initializers; new/unsupported patterns remain shared or fail generation.

The boundary checker supports `--lifecycle` to test nonzero private sentinels
against all four lifecycle cases, and queued invalid START after an accepted
RAM write and during scalar export. `--entries` also checks coherent scalar
observations on every busy cycle. `check_integrated.py --application` runs
application/lookup and list construction/access in lockstep with the concrete
RED2 reference. All integration variants remain experiments until full parity,
complete mapped resources, and board implementation satisfy acceptance.

The corrected graph mirror maps to 38,908 total LUTs; persistent ownership maps
to 38,417, including its mask ROM, scalar observation bank and queued lifecycle
logic. The latter uses 9,959 FF and 26 BRAM36 equivalents. Both maps account for
all primitives and report zero structural problems. All 159 owned integration
path witnesses, nonzero lifecycle masks, queued invalid START, application/list
lockstep and RECP parity checks pass. This is still above the 20,800-LUT board
capacity; production remains at 41,170 LUT. The event audit regenerates identical
hardware and rejects extraction of non-Reg events still consumed by legacy code.
See `docs/handoffs/synth-red2-cfg-integration-results.json` for exact provenance.

The next configuration uses `RED2_CFG_PILOT_EXTRA_STATES` (comma-separated
original MICRO names) to add specific selector/JOIN handlers while leaving
EXECUTE's other opcode entry paths in legacy hardware. `catalogue.py` reports
conservative candidates and reasons for exclusions. It follows alias
prerequisites and checks RAM writes formed outside the handler bodies. The
current 52-state extension has 108 total entries, 11,709 rows, a 37-bit
16,384-row ROM, and 389 allocated scratch words in a 512-word RAM. It passes
12,960 typed cases and 339 physical witnesses with reset and constant protection.
Its integration owns 60 private words and bridges 144 genuinely shared words.
All 339 integrated path witnesses, pause/coherent observation checks, private
lifecycle masks, queued invalid START and application/list lockstep pass for
the fixed-mask variant. Full-core mapping and further parity are recorded
separately, not inferred from the isolated checks.

Expanded testing exposed a narrow intermediate subtraction before a comparison.
`expression_types.py` uses the enhanced PipelineC runtime's public
`arith_result_type` rules, preserving intermediate unsigned wrap widths rather
than doing every expression at 64 bits. Assignment truncation is propagated
only through operations that preserve the required low bits. Needed wider-than-
64 intermediates fail generation. Shifts of 64 or more produce zero rather than
wrapping the count. `check_expression_types.py` pins intermediate underflow,
widened addition, reflected bitwise operands, slices and shift boundaries.

A state that forms another RAM write after consuming its read response needs an
extended transaction phase. The current adapter rejects it. It also rejects
unadapted metadata-bank writes, including those formed outside ordinary request
arms. The event guard accepts independently reused local names only when each
remaining read has a fresh dominating definition; global zero defaults cannot
hide a removed same-cycle launch assertion. `check_events.py` pins both cases.
`native_runtime.py` caches scalar integer descriptors for long native runs,
leaving mutable array factory descriptors uncached; it changes no HDL/compiler.

`RED2_CFG_PILOT_STREAM_BRIDGE=1` selects a separately measured ownership
variant. An immutable narrow ROM lists only the import/export scratch addresses
needed by each entry; a dispatch ROM supplies the two list starts. The 108-entry
configuration has 1,558 nine-bit list words in 2,048 locations, compared with a
256x288-bit mask ROM and fixed 144-word scans. Each transfer remains serialized,
and exports finish before busy drops. Private initialization, queued lifecycle
commands and scalar snapshots use the same contract. The default fixed-mask
source was regenerated byte-identically after the emitter refactor. Compare
complete tops at identical entry scope; list size alone does not establish a LUT
saving. `integration.json` records the bridge kind and pause/export phases for
the common boundary checker.

The expanded fixed-mask complete top maps to **34,183 total LUTs** (33,865 logic,
318 LUT memory), 9,272 FF, 20 DSP, 1,766 CARRY4 and 37 BRAM36 equivalents.
This is 4,234 LUTs below the measured 56-entry owned top and 6,987 below
production. All primitives are accounted for and structural checks report zero
problems. Existing RECP parity passes with 112,644 physical clocks. The short-
list complete top also passes application/list parity with 61,168 physical
clocks, versus 83,490 for fixed scans; compare mapped area when both finish.
These measurements still do not establish board fit or complete-program parity.

`RED2_CFG_PILOT_DICTIONARY=1` optionally deduplicates packed immutable control
words behind an index ROM, adding one synchronous fetch cycle. At 108 entries,
11,709 rows reference 2,945 distinct words through a 12-bit index. The encoder
checks exact reconstruction, and typed/physical checks compare the emitted
controller rather than assuming that storage encoding preserves execution.
Use a separate output directory for this experiment. The default encoding was
regenerated byte-identically after adding the option. Any BRAM/LUT saving needs
a completed full-top map; bit-count calculations are not a resource result.

At the same 108-entry scope, the short-list full core maps to **33,449 total
LUTs** (33,131 logic and 318 LUT memory), 9,062 FF, 20 DSP, 1,753 CARRY4 and
33.5 BRAM36 equivalents. That saves 734 LUTs and 3.5 BRAM36 equivalents versus
fixed scans. All 339 integrated witnesses and lifecycle checks pass; all HDL
input hashes match the provenance record, all primitives are accounted for,
and structural checks report zero problems. The remaining gap to the 20,800-
LUT board capacity is 12,649 LUTs. This is an experimental complete-top resource
measurement, not production adoption, RTL parity or a routed board result.

The indexed complete top maps to **33,601 LUTs and 27 BRAM36 equivalents**:
152 extra LUTs buy 6.5 BRAM36 equivalents against the direct short-list control
ROM. It uses 9,064 FF, 20 DSP and 1,769 CARRY4. All 339 integrated witnesses,
lifecycle checks and application/list parity pass; all primitives and HDL hashes
are accounted for and structural checks report zero problems. The direct-ROM
short-list variant remains the lowest measured LUT count. The indexed variant
is the storage baseline for further core extraction. Its exact results are in
`docs/handoffs/synth-red2-cfg-dictionary-results.json`.

`RED2_CFG_PILOT_PUBLICATION_READS=1` enables a read-sidecar experiment. It adds only
MICRO_PUB_EXEC and explicit synchronous read sidecars for `pub_root_ram` and
`pub_patch_ram`; the original publication stack retains metadata and graph write
authorization. Factory types, depth and latency are pinned to the original AST,
and the extracted request arm must contain only the two address assignments.
The single accepted packet reads graph, control and both metadata banks together.
The candidate has 109 entries, 14,634 rows, 3,901 unique control words and 482
allocated scratch words. It passes 13,080 typed comparisons and 370 standalone
hardware witnesses. All 370 complete-top witnesses and publication program
parity pass; the full top maps to 33,299 LUTs. Use a separate output
directory with persistent ownership and short-list bridging enabled.

The native fixture helpers construct nested task/root structs by their declared
types. Unused leaves outside the extracted interface are zero in the source
fixture; extraction retains their legacy hardware. Publication witness selection
covers every observed source-CFG row and includes every sampled task kind, beyond
the six-witness cap used by the original simpler handlers. `native-coverage.json`
records observed/selected rows; this is not exhaustive coverage of all possible
inputs. Existing standalone baselines do not implement metadata sidecars.

Indexed-store RECP parity also passes (79,540 physical clocks). The publication
read experiment passes quick full-top pause/lifecycle checks. Its stronger 370-
witness set includes 31 publication cases covering all 1,048 source-CFG rows
observed in the typed publication trials and every sampled task kind. The
complete-top mapping source and stronger validation source are byte-identical;
records are in `docs/handoffs/synth-red2-cfg-publication-read-results.json`.

The read-sidecar complete top measures **33,299 LUTs and 27.5 BRAM36
equivalents**, saving only 302 LUTs against the indexed-store baseline. All 370
boundary witnesses and publication program parity pass (1,076,556 physical clocks).
Its 60 private words and 205 shared words identify state ownership as the next
boundary, rather than isolated computation.

`RED2_CFG_PILOT_PUBLICATION_TRANSACTIONS=1` replaces the read-only option and
adds MICRO_PUB_STACK. Five source-typed metadata RAM packets join graph/control
in one accepted synchronous transaction. Factory types, depths and latency are
checked against the original source; compound graph-write request arms retain
their incoming phase guards. The original publication completion bank is
appended to its unique triggering handler, while its lifecycle predicates stay
in legacy arbitration. External JOIN preflight still authorizes commit phases.
The request sentinel is 63, distinct from every payload field. Instruction
semantics and publication RAM banks come from the existing RED2 top.

Use persistent ownership, short-list bridging and
`RED2_CFG_PILOT_PRUNE_ALIASES=1` for this variant. Typed struct-zero initializers
are accepted only with the exact field set and proven zero constants; duplicate
zero initializers combine their START masks. No surviving legacy use is allowed
for private state. This configuration has 110 entries, 84 private words (2,696
bits), 191 shared words and 493 allocated scratch words. It passes 13,200 typed
comparisons and 391 standalone physical witnesses. Full-top area and program
validation are still pending.

`RED2_CFG_PILOT_SPARSE_PUBLICATION=1` retains the full packet interface and
original zero defaults. It clears metadata packet fields on accepted start and
serializes only banks referenced by that entry, reducing 22,416 rows to 14,048.
The typed oracle still constructs every original packet field. Separately,
`RED2_CFG_PILOT_DEAD_TEMPS=1` removes dead temporary writes before scratch
allocation, preserving all state writes, branches, requests and halts. At this
scope it removes another 1,542 rows. Both options default off; use separate
artifact directories and validate the final emitted controller. The prior
read-sidecar source regenerates byte-identically with these options disabled.

`check_boundary.py --metadata-writes` selects a write to each metadata RAM and
checks captured read-first data as well as final contents. Boundary checks also
queue invalid START after each bank's accepted write, finish that transition,
and verify preserved RAM and state before the lifecycle fault. These are native
physical-clock checks, not RTL simulation or board implementation results.

The dense publication transaction top maps to **32,705 LUTs and 38.5 BRAM36
equivalents**. Sparse packets plus dead temporary removal map to **33,276 LUTs
and 32.5 BRAM36 equivalents**: this trades 571 LUTs for six BRAMs, rather than
improving the LUT minimum. The compact top passes all 391 boundary witnesses,
five-bank read-first/lifecycle checks and application/list parity. Its focused
publication program run remains pending. See the transaction results file.

`RED2_CFG_PILOT_PUBLICATION_LAUNCHES=1` adds JOIN_TAIL_READ, JOIN_EP_CHASE,
JOIN_APP_SCAN, JOIN_APP_TARGET_READ and JOIN_MULTI_TARGET_READ. Both uniquely
triggered JOIN-tail selector/promotion banks are copied in source order. Source
guards require one zero default, one selected assertion and one bank reader;
legacy event terms are removed only after matching the bank-body hash. At this
scope, 115 entries own 134 private words (3,992 bits) and share 162 words. The
control table has 13,861 rows, 4,686 unique 40-bit words, and 524 scratch words in
1,024 locations. All 13,800 typed comparisons and 414 initial physical witnesses
pass. Six mandatory STRUCT/APP/LAMBDA selector-continuation fixtures start with
nonzero bank state and exercise promotion-generation wrap. They pass on the
physical controller and complete top, including lifecycle checks. Selector
program parity passes at 7,531 physical clocks. All 418 boundary witnesses and
lifecycle checks pass; focused publication program checks continue. The
stronger fixtures use byte-identical hardware.
The complete top maps to **29,224 LUTs and 34 BRAM36 equivalents**, saving
4,052 LUTs against the matching compact stack top. This remains 8,424 LUTs
over the Basys 3 limit. Production stays unchanged.

`RED2_CFG_PILOT_ONEHOT_IMPORT=1` changes only the short-list bridge's import
mux to independently gated typed fields and a balanced OR tree. Selector codes
must be unique. Exhaustive selector tests cover 5,120 codes across varied field
counts and widths; the prior source regenerates byte-identically with the option
off. The opt-in complete top passes the six mandatory launch/lifecycle fixtures;
its complete top maps to **28,785 LUTs**, saving 439 LUTs. The selector program
also passes at 7,531 physical clocks. This is an implementation choice with the
same latency and state-transfer contract.

`diagnose_scalar.py` creates a separately labelled attribution top that faults
at the legacy scalar entry. It deliberately changes semantics and cannot be a
fit candidate. Its whole-top delta includes scalar control and preflight as well
as arithmetic, and is not an additive standalone arithmetic-unit estimate.

`RED2_CFG_PILOT_SCALAR_CORE=1` splits the four priority branches at the shared
scalar entry: equality continuation, equality child, equality launch and Y
continuation. The active flags come from incoming state; clearing one cannot
activate a later arm in the same transition. Their original request and response
packets move together. The arithmetic fallback retains its original hardware,
request and synchronous read gate. Generation with the option disabled is byte
identical to the mapped one-hot launch top. All 13,920 typed comparisons and 61
standalone and complete-top continuation witnesses pass. Stronger fixtures on
byte-identical hardware retain positive write enables for all five metadata
banks and pass accepted-write lifecycle checks. The complete top maps to
**24,005 LUTs**, saving 4,780 against the one-hot launch top.

`RED2_CFG_PILOT_LITERAL_METADATA=1` additionally connects the three literal
metadata scan handlers and selector value read. It adds only a read address and
the source-typed synchronous response fields; host metadata loading keeps its
original enable and payload. Unique continuation launch writers carry all their
source reset-bank effects, including both consumers of the equality event, in
source order. This is an independent opt-in experiment with its own validation
and mapping. The complete top maps to **21,057 LUTs**, saving another 2,948 and
leaving 257 LUTs above the Basys 3 limit. All 14,400 typed comparisons, 507
standalone and complete-top physical witnesses, and five-bank lifecycle checks
pass.
Results are recorded in the scalar-core results file.

`RED2_CFG_PILOT_CONTROL_COMPACT=1` fuses a single-use temporary calculation with
its adjacent same-width copy, when the copy has only that predecessor, and
removes jumps to the following row. It runs before scratch allocation, preserves
packet/state effects and remaps every entry and branch target. Fourteen focused
checks pass. The metadata candidate shrinks from 17,565 to 13,898 rows, halving
the index-ROM depth, and passes 14,400 typed comparisons plus all 508 standalone
physical witnesses. The complete top maps to **20,885 LUTs**, saving 172 and
leaving 85 LUTs above the board limit. All 508 complete-top boundary witnesses
and five-bank lifecycle checks also pass.

`RED2_CFG_PILOT_INTEGER_JOINS=1` additionally connects JOIN_PUBLISH and
JOIN_EP_RESULT_WRITE under the existing `RED2_SYN_FLOAT=0` profile. Binary64
unpack/domain helpers inline from the original AST with a checked compiler type
factory. Raw FLOAT transport, predicates and EVEN? applicability remain intact.
The typed oracle retains the original helper calls and unspecialized bodies.
All 14,640 typed comparisons and 30 helper edge cases pass.
`check.py --integer-corners` adds mandatory signed
boundary, overflow, predicate and FLOAT domain witnesses on a separate fixture
copy of the identical hardware.

The integer JOIN top maps to **19,151 LUTs**, but is **not a usable fit
candidate**: RTL replay diverges during addition at physical clock 9,817 and
structure creation/access at 14,210. Verilator and Icarus independently reproduce
the addition mismatch; function application passes all 10,703 clocks. All 527
standalone and complete-top witnesses plus five-bank lifecycle checks pass.
The separate mandatory corner suite passes all 152 standalone and complete-top
witnesses plus accepted-write lifecycle checks, and 14,792 typed comparisons.
This demonstrates why native comparisons alone are insufficient.

The mismatch identifies a compiler register re-annotation bug: the surviving
EXECUTE JOIN decoder assigns `join_saved_primitive: uint1_t = ...` after its
`Reg[uint1_t]` declaration. The compiler redeclared a zero-driven local instead
of updating the register. The fix lives in fpgatool's
`pypeline-register-reannotations.patch`, with scalar/struct native/VHDL regression
coverage. A separate root recompiles byte-identical controller, complete top and
oracle sources with the corrected compiler and reuses the concrete-checked
public-port traces. The corrected top maps to **19,172 LUTs** (18,846 logic and
326 LUTRAM), **8,095 FF**, **20 DSP48E1** and **34.5 BRAM36 equivalents**.
That leaves **1,628 LUTs** below the Basys 3 limit. All 219 generated HDL files
and mapping scripts match their recorded hashes; structural checks report zero
problems and every mapped primitive is accounted for.

The corrected RTL passes every public-port clock for addition (26,391), function
application (10,703), structure creation/access (123,863), signed-boundary
addition (26,391) and `(EVEN? -2)` (44,742): **232,090 clocks** in total.
Independent Icarus replay also passes all 26,391 addition clocks. The same
source/oracle/control and unchanged native runtime retain the 527 boundary and
152 mandatory corner results above. This establishes a measured resource-fit
candidate for the tested profile; it does not establish exhaustive ISA parity,
board integration or routed timing. Historical pre-fix area results do not
establish RTL correctness for those variants.

`RED2_CFG_PILOT_TRACE=/absolute/new/vectors.txt check_integrated.py --program`
records every public input/output clock for `RED2_CFG_PILOT_PROGRAM`. A complete
native/concrete pass writes the trace metadata and source hash. `prepare_rtl.py`
prepares direct GHDL replay; the large complete top makes that backend slow.
`prepare_verilator.py --conversion-only` prepares conversion of the area map's
`coarse.json`; after running that Yosys script, `prepare_verilator.py` emits a
packed-port wrapper, replay driver and build script. It checks all 626 output
bits on each clock. Register/memory initialization comes from the generated RTL;
the replay driver does not inject internal state.

The end-to-end list-equality probe `(EQUAL? (CONS 7 NIL) (CONS 7 NIL))` faults
at commit 41 (`hw=3`, microstate 3, PC 62) on both the continuation candidate
and unchanged production hardware. This is an existing unsupported execution
path, not a passing parity check. Simple addition and scalar equality complete
before that probe; broad supported-program parity remains outstanding.
The experimental top remains separate from production source. The compiler
correction is pinned project-wide; routed board timing remains unverified.


## Datapath sharing

Four optional flags further reduce the dedicated core; all default off:
`RED2_CFG_PILOT_SHARED_RESPONSE`, `RED2_CFG_PILOT_COMPACT_PENDING`,
`RED2_CFG_PILOT_REVERSE_CONTROL` and `RED2_CFG_PILOT_DIRTY_WRITEBACK`.
Set each to `1` alongside the corrected integer JOIN configuration. Shared
response removes duplicate capture registers; compact pending retains only
queued lifecycle operands. Reverse control executes on the existing shared
engine. Dirty writeback tags actual scratch writes, omits overwritten inputs
from the import data selector and bypasses the export bus for proven constant
writes. No instruction is removed and the enhanced compiler pin is unchanged.

| Cumulative change | LUTs including LUT RAM | Flip-flops |
| --- | ---: | ---: |
| Corrected baseline | 19,172 | 8,095 |
| Shared response | 19,101 | 7,188 |
| Compact pending | 18,985 | 6,901 |
| Shared reverse control | 18,767 | 7,018 |
| Dirty writeback | **17,266** | **6,345** |

All retain 34.5 BRAM36 equivalents and 20 DSPs. The final candidate saves 1,906
LUTs and 1,750 flip-flops. Source guards check the storage/launch assumptions;
constant-write analysis is conservative at control-flow joins and concretely
asserted during typed execution. Imports clear tags before every possible
export, including clear-only imports; only executed writes set tags.

All 701 complete-top boundary cases, 14,912 typed comparisons, queued lifecycle
checks and 69 mutation guards pass. Five native/concrete program traces pass
230,990 RTL clocks, plus 1,018 public lifecycle clocks. Xilinx primitive mapped
simulation passes application and lifecycle. Fresh regeneration reproduces both
the default baseline and candidate exactly. Evidence and artifact hashes are in
[the results record](../../../docs/handoffs/synth-red2-datapath-sharing-results.json).
These are core measurements. The complete board with the shift serializer and
verified eight-bit response placement recipe now routes at 17,997 physical LUT
sites and passes the 10 MHz timing gate. All five programs plus queued lifecycle
pass on the Basys 3: 232,008 clocks, comparing every 626-bit output, with a fresh
SRAM load per case. See
[the complete physical corpus](../../../docs/handoffs/red2-complete-physical-corpus-results.json)
and [the board build instructions](../../boards/red2_basys3/README.md).
The optional burst-clock frontend also passes the complete physical corpus,
comparing all 626 bits at its 6,927 packet endpoints across 232,008 executed
clocks. Its complete image uses 17,932 physical LUT sites and passes routed
10 MHz timing; see [the burst evidence](../../../docs/handoffs/red2-burst-clock-results.json). The experimental top
remains separate from maintained production source; the existing list-equality
execution gap remains outside the passing profile.

## Shared divider iteration

Appending `MICRO_U64_DIV` to `RED2_CFG_PILOT_EXTRA_STATES` moves the integer
long-division loop onto the existing fixed hardware control engine. Division
and modulo remain available; this trades additional clocks for shared logic.
The scalar fallback insertion preserves the original dispatch order even when
the divider handler is extracted. Before the saved-equality revision below, the
normal configuration regenerated the qualified f97 core byte-for-byte.

| Core measurement | Qualified datapath | Shared divider candidate |
| --- | ---: | ---: |
| LUTs including LUT RAM | 17,266 | **16,870** |
| Flip-flops | 6,345 | 6,343 |
| CARRY4 | 736 | 702 |
| BRAM36 equivalents | 34.5 | 34.5 |
| DSP48E1 | 20 | 20 |

The candidate source is
`e6a0dced233b5621f698e291d8662dc9a30912cdfef8a7e289a1c2a928e955ff`.
Both measurements use the same enhanced compiler, Yosys/GHDL versions and area
mapping scripts. Native validation passes 15,032 typed comparisons including
152 mandatory integer corner witnesses, 699 complete-top boundary witnesses
covering all 124 entries, lifecycle checks, and multiply/divide/modulo/exponent
program parity. These are selected witnesses, not exhaustive coverage.

All 11 program traces pass RTL replay: **518,097 simulated clocks**, plus
**1,018 public lifecycle clocks**, comparing all 626 output bits per clock.
Mapped-primitive application, lifecycle, division, modulo and large-magnitude
division also pass. The complete burst board maps to **17,819 LUTs**, 8,543 FF,
34.5 BRAM36 equivalents and 20 DSPs, saving the same 396 LUTs versus the qualified
burst image. It routed at **17,826 physical LUT sites**, with 11.29/11.32 MHz
core/monitor timing estimates against a 10 MHz target. Actual board application
replay failed, including a fresh single-clock diagnostic. The complete flattened
mapped board passes application simulation, its core has identical primitive
parameters and wiring to the core map, and its LUT truth tables match the FASM.
The physical failure remains unresolved; the previously qualified burst image
was restored. This is not the default board candidate. See
[the failed physical qualification](../../../docs/handoffs/red2-shared-divider-physical-results.json),
[the integration evidence](../../../docs/handoffs/red2-arithmetic-sharing-integration-results.json),
[the frozen simulation/fit gate](../../../docs/handoffs/synth-red2-shared-divider-results.json)
and [resource attribution](../../../docs/handoffs/red2-shared-divider-resource-attribution.json).
This frozen candidate still retains the earlier list-equality gap.


## Saved equality IF semantics

The maintained hardware source now recognizes private `__EQUAL_IF__` at saved
JOIN boundaries and shares ordinary IF branch/path handling. Private IF keeps
quantum unchanged, accepts TRUE/FALSE/EQUAL_STUCK conditions, and handles inline,
APP and EP branches. A separate clock stages inline and terminal EP writes before
the RAM request. Equality completion preserves the live argument count instead
of forcing it to two.

The native regression gate is `scripts/check_syn_equality_if.py`, using the same
pinned enhanced runtime as `check_syn_sim.py`. It passes 26 saved-IF fixtures
(18 private and eight ordinary), comparing architectural fields and every graph
and control RAM word. Four full list-equality programs also pass at every
architectural commit, including equal and unequal nested lists. Fourteen focused
static/fallback checks pass. See [the semantic evidence](../../../docs/handoffs/red2-equality-if-results.json).

This is native evidence for the maintained source, not an RTL, area or board
result. Direct/EP private primitive firing remains separate from saved JOIN.
The qualified FPGA image and frozen shared-divider candidate still use their
older sources. A combined candidate in `build/red2-equality-integrated/shared-divider`
extracts the new write stage onto the existing dedicated control engine. It
generates 125 entries and 14,982 compact rows and passes 15,152 typed comparisons
with mandatory integer corners. Exact enhanced RTL elaboration and core mapping
complete at **17,003 LUTs**, 6,346 FFs, 34.5 BRAM36 equivalents and 20 DSPs.
All 704 selected native boundaries and lifecycle checks pass, but full list
equality fails before commit 41. The shared request extraction bug below is
responsible; this candidate is not qualified. See
[the combined candidate record](../../../docs/handoffs/red2-equality-shared-divider-integration-results.json).

## Shared multiplier and shared request guards

`RED2_CFG_PILOT_SHARED_MULTIPLY=1` appends a low-64-bit product instruction to
the dedicated control engine. It requires integer JOIN lowering and extraction
of `MICRO_U64_DIV_FINISH` and `MICRO_JOIN_SCALAR_INT_POW`. Source sign, overflow
and truncation behavior is preserved. No arithmetic instruction is removed.
Liveness, ownership, compaction, writeback and native models all recognize the
new instruction; it has explicit scratch-write enable because its opcode is
appended after HALT.

The frozen pre-request-fix candidate `e718bd5a...` maps at **15,830 LUTs**,
6,314 FFs, 34.5 BRAM36 equivalents and 10 DSPs. Compared with the 17,003-LUT
combined core above, that saves 1,173 LUTs and ten DSPs. It passes 15,504 typed
comparisons including 112 explicit product witnesses, 123 selected native
controller witnesses, and 820 complete-top native boundaries plus lifecycle.
Eleven programs pass native/concrete comparison and RTL replay: **523,584
simulated cycles**, comparing all 626 exposed output bits each cycle. This
corpus excludes list equality. See
[the multiplier evidence](../../../docs/handoffs/red2-shared-multiplier-results.json).

Both frozen candidates fail an independent reachable equality checkpoint:
an IF path read requests control-stack slot 0 instead of slot 4. The old request
extractor treated an `or` guard as one state name, dropping both alternatives.
This also affects structure preflight/rewrite request guards. The extractor now
expands shared guards and merges request blocks in source order; integration
removes only selected alternatives. Mixed guards require explicit specialized
lowering. Source-based regressions cover both IF paths and all six shared
structure requests. `check_integrated.py --equality-checkpoint` constructs the
reachable state before commit 41 with Concrete RED2, loads it through public
ports, and compares the next commit's architectural fields and every graph and
control word. It can record an RTL replay trace through the usual trace option.

Corrected candidates use a fresh output root. Earlier area and passing test
counts remain evidence only for their frozen sources; the request fix requires
new semantic validation and area measurement before promotion. Simulation
cycles include setup and observation commands and are not reductions or a
performance benchmark. Physical burst replay compares packet endpoints,
whereas the RTL corpus above compares every simulated cycle.

The fresh corrected source `89c7712c...` passes 15,504 typed comparisons
including the product corners. The reachable equality checkpoint now passes
in native hardware-source simulation: 61,871 simulated cycles including public
setup and full memory readback. All architectural fields and all 256 graph and
256 control words match Concrete RED2 at that next commit. Full program and
RTL validation, mapping, routing and physical qualification remain separate.
See [the corrected request evidence](../../../docs/handoffs/red2-shared-request-guards-results.json).

Its completed enhanced core map uses **15,803 LUTs**, 6,170 FFs, 34.5 BRAM36
equivalents, ten DSPs and 534 CARRY4 cells, with zero structural problems and
verified HDL/script provenance. It also passes the 123 selected native product
controller witnesses plus reset cancellation and constant protection. The
request fix saves another 27 LUTs and 144 FFs against the frozen pre-fix product
candidate by removing its retained shared request logic. No routed-board or
physical qualification is implied by this core measurement.

## Interactive RTL semantic checks

`build_interactive_rtl.py` links a small host-side port driver to the already
compiled Verilator model archive. It verifies source, coarse netlist, wrapper
and VHDL layout hashes and records the archive, runtime object, C++ source,
compiler command and resulting binary. It does not rebuild or change the FPGA
design. The shared `PortLayout` retains native trace packing and also decodes
RTL responses; focused tests pin nested field offsets, truncation and trace
format. A fresh server instance implements simulation `sim_reset`; hardware
`CMD_RESET` remains a separate command.

After the normal exact-source RTL replay build, using the same configuration:

```sh
python3 scripts/experiments/red2_cfg_pilot/build_interactive_rtl.py
python3 scripts/experiments/red2_cfg_pilot/check_interactive_vectors.py \
  "$RED2_CFG_PILOT_OUT/equality-checkpoint-rtl/vectors.txt" \
  --out "$RED2_CFG_PILOT_OUT/interactive-vector-check.json"
RED2_CFG_PILOT_RTL_INTERACTIVE=1 \
RED2_CFG_PILOT_PROGRAM='(EQUAL? (CONS 7 NIL) (CONS 7 NIL))' \
  python3 scripts/experiments/red2_cfg_pilot/check_integrated.py --program
```

The vector check compares every exposed output bit on every cycle of a complete
same-source native trace. The program check instead drives the RTL directly,
compares architectural fields and expected graph/control mutations with Concrete
RED2 at every committed reduction, then compares all graph/control words at
termination. It emits `INTEGRATED_RTL_CONCRETE_PARITY_PASS` with an explicit RTL
environment label. Native checks keep their own result marker. Interactive mode
rejects native expected-output trace recording and only admits the public-port
program/checkpoint gates. RTL simulation uses the optimized frontend netlist
before technology mapping; mapped primitives, routing and physical behavior
still need their own checks.

For corrected source `89c7712c...`, the complete equality checkpoint passes both
ordinary RTL replay and the interactive driver against its native trace: 61,871
cycles, all 626 output bits each cycle. Direct RTL prototype application and
equal/unequal one-element list programs also pass through termination, including
final full-RAM equality. Their program results are distinct from the per-cycle
native-output comparison. The durable driver is running the broader corpus and
nested lists; see the separate validation scopes in the request-fix evidence.

The durable interactive driver now passes all 11 original programs on the
corrected core: 523,617 simulated cycles with architecture/mutations checked at
every commit and all RAM at termination. The equal two-element nested list also
passes (1,380,140 cycles). All 26 saved-IF fixtures pass in actual RTL, including
all architectural fields and every graph/control word for each fixture. Native
public lifecycle assertions and ordinary every-bit RTL replay pass a separate
1,043-cycle continuous command trace. Broader native boundary/lifecycle and
remaining direct RTL list cases still have separate completion receipts.

All **15 full programs** have now completed direct RTL/Concrete parity,
including equal and unequal nested lists: 4,568,145 simulated cycles across
the programs. The 26 saved-IF fixtures are a separate passing gate. Native
signed multiply also passes ordinary RTL replay on all 626 output bits for
46,855 cycles. Xilinx mapped-primitive lifecycle replay passes all 626 bits for
1,043 cycles; its longer equality/multiply cases are still running. These
simulation results do not establish routing, timing or physical-board behavior.

The corrected divider-only reference is now measured with the same source
semantics, shared request fix, compiler and byte-identical mapping recipe:

| Corrected core | LUTs including LUT RAM | FFs | BRAM36 equivalents | DSPs | CARRY4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy finish/power arithmetic | 16,809 | 6,200 | 34.5 | 20 | 700 |
| Shared product/finish/power | **15,803** | **6,170** | **34.5** | **10** | **534** |

The controlled saving is **1,006 LUTs**, 30 FFs and ten DSPs. The baseline maps
two ten-DSP multiplier instances; the candidate maps one. Both pass the reachable
equality checkpoint; baseline multiply, power, divide and signed-boundary
multiply also pass direct RTL/Concrete program parity. The saving includes
moving the complete finish/power handlers, rather than only deleting a
multiplier. See [the controlled comparison](../../../docs/handoffs/red2-corrected-arithmetic-sharing-results.json).

All 820 candidate native boundary witnesses, lifecycle, accepted metadata and
poisoned payload checks now pass. Four native-expected traces pass both frontend
RTL and Xilinx mapped-primitive replay on all 626 bits per cycle: application,
public lifecycle, equality checkpoint and signed multiply. The frozen
[experimental board-fit gate](../../../docs/handoffs/synth-red2-shared-multiplier-results.json)
uses those results plus the 15 independent full-program RTL/Concrete tests and
26 saved-IF fixtures. The slower duplicate native list-program corpus remains
separate corroboration. This gate permits experimental board preparation;
routed timing and physical qualification remain separate.

Interactive RTL can also record a trace for subsequent board comparison:

```sh
RED2_CFG_PILOT_RTL_INTERACTIVE=1 \
RED2_CFG_PILOT_RTL_OBSERVATIONS="$RED2_CFG_PILOT_OUT/rtl-observed-application/vectors.txt" \
RED2_CFG_PILOT_PROGRAM='((LAMBDA (x) x) 7)' \
  python3 scripts/experiments/red2_cfg_pilot/check_integrated.py --program
```

This option requires the complete program gate, HALTED termination and no pending
host operation. Metadata is published only after the architectural/memory checks
and RTL process finish successfully. It labels the expected outputs as
`Verilator RTL simulation`, retains the checked program and semantic scope, and
pins the same-source model binary and manifest hashes. Native trace recording
keeps its separate origin. The board host validates and carries this distinction
into physical results; RTL observations do not constitute a native per-cycle
comparison. The application observation trace matches all 10,688 cycles of the
native trace byte for byte. See
[the trace-origin evidence](../../../docs/handoffs/red2-rtl-observation-trace-results.json).

For further area work, `attribute_resources.py --lut-cones` additionally walks
mapped combinational connectivity to register/memory/DSP inputs and public
outputs. It reports overlapping cones and disjoint sets of endpoint groups.
Registers, RAM and DSPs are traversal boundaries; multi-output combinational
primitives conservatively traverse all input pins. Clock pins are excluded,
while DSP C remains a data input. LUT RAM is reported as memory separately.
These sets are not source-function ownership or estimates of removable area.

```sh
python3 scripts/experiments/red2_cfg_pilot/attribute_resources.py \
  "$RED2_CFG_PILOT_OUT/integrated-stream/machine.py" \
  "$RED2_CFG_PILOT_OUT/integrated-stream/baseline-area.json" \
  --module top --lut-cones
```

The corrected shared-multiplier core partitions all 15,477 combinational LUTs.
The two largest exclusive sets feed remaining core state (3,501) and shared
scratch-memory inputs (2,979). The latter includes ALU, result masking/selection
and write steering; it is not the RAM's own area. Five connectivity regressions
pass and storage/DSP attribution is unchanged. See
[the endpoint attribution](../../../docs/handoffs/red2-lut-endpoint-attribution-results.json).

`RED2_CFG_PILOT_SHARED_SHIFT=1` is an optional area experiment for the scratch
datapath. It implements left and right logical shifts with one right shifter,
fixed bit reversal and direction multiplexers. Counts of 64 or more still yield
zero. It adds no controller states or cycles; result-width masking and memory
request sequencing remain unchanged. The default is off, and the default
emitted source/control tables match the measured shared-multiplier baseline
byte for byte.

The emitted expressions pass 9,694 independent arithmetic comparisons and 3,406
typed native checks. An isolated enhanced PipelineC/GHDL RTL miter passes SAT
equivalence against independent Verilog shifts for all 129 input bits. The full
candidate also passes 15,504 typed handler comparisons and 123 selected emitted
controller native witnesses, reset cancellation and constant protection. Full
core mapping uses **15,515 LUTs**, saving **288** against the same-recipe
15,803-LUT reference. FFs, BRAMs and DSPs are unchanged; CARRY4 increases by 16.
See [the shifter experiment](../../../docs/handoffs/red2-shared-shift-results.json).
The complete candidate frontend RTL now passes all 17 reference traces: all 626
public bits on every one of 4,631,059 simulated cycles. These deliberately use
earlier-source native/validated-RTL expected outputs, retaining both source IDs
and origins. Routing and physical qualification remain separate. The flag stays
off by default; the qualified board still uses the shared-multiplier source.


The next optional graph extraction adds `MICRO_JOIN_IF_EP_CHASE` to
`RED2_CFG_PILOT_EXTRA_STATES` in the shared-shifter configuration. With the same
enhanced compiler and byte-identical mapper scripts/backend, its complete core
maps at 15,181 LUTs and 6,090 FFs (334 LUTs and 80 FFs fewer). It adds 88 control
rows without increasing scratch depth or mapped BRAM/DSP use. The ownership
proof moves the 64-bit EP target and 16-bit hop counter entirely into existing
scratch RAM; mapped remaining-core flip-flops fall by exactly 80. Full native
boundaries and complete-program RTL gates are still required before physical
qualification.

`check.py --integer-corners --shared-multiply-corners` includes 27 explicit IF
EP-chase witnesses when that state is selected. They cover all 88 lowered rows,
including valid/malformed EP hops, the hop limit, atomic words, closure parent
boundaries and unsupported forms. `check_hardware.py --if-ep-chase-only` runs
these witnesses on the actual emitted native controller, with delayed responses,
busy-input interference, reset cancellation and constant protection. These are
native simulation checks; hardware qualification is separate. See
`docs/handoffs/red2-if-ep-sharing-results.json` for measured artifacts and pending
complete-top gates.
