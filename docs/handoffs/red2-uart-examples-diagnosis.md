# Full UART example failures on standalone RED2

The installed, persistent v6 engine runs `clock-dots`, but this does not qualify
every THOR program. Both full UART examples encounter incomplete publication
paths in the reducer. The physical fault LED, typed hardware-source simulation,
and frontend RTL simulation agree. There is no evidence that changing `tio`
settings would resolve these faults.

Both unchanged programs pass the abstract reference processor with
`--quantum 5 --supervise --memory-words 256 --max-quanta 1000`. Alphanumerics
produces the full 63-byte sequence and halts; Caesar transforms `Az09!` into
`Ed09!` and halts on ESC. This validates their expected behavior, without asserting
that the reference processor uses the FPGA's exact storage layout or publication
implementation. Simple one-byte and two-byte UART receive/echo fixtures also pass
the frontend RTL model, as does CRC rejection.

The hardware and original example sources were unchanged during this diagnosis.
The experimental changes discussed below were confined to ignored build files;
they have not been deployed or promoted into the qualified hardware source.

## Alphanumerics

At quantum 5, `uart-alphanumerics.thor` faults before its first character.
The fault is `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` (3), surfaced by the standalone
controller as `0x88`. Its last active source microstate is
`MICRO_JOIN_TAIL_READ` (36), at exhausted quantum.

The returned graph has multiple words. Its parent is an environment pointer
(EP), while the corresponding JOIN path accepts APP/RECP parents for that
publication shape. The execution stops at PC 51, with FSP 63. This first failure
is an explicit unsupported branch, not graph-memory exhaustion: the program's
working arena contains 225 words.

Frontend RTL trials at other budgets did not yield a working workaround:

| Quantum | UART before failure | Last active microstate |
| --- | --- | --- |
| 1 | empty | JOIN_APP_SCAN (50) |
| 2 | empty | JOIN_APP_SCAN (50) |
| 5 | empty | JOIN_TAIL_READ (36) |
| 10 | `0` | JOIN_TAIL_READ (36) |
| 20 | `01` | JOIN_TAIL_READ (36) |

Every row reaches hardware fault 3. A native-only experiment redirected
multiword EP-parent publication to the existing generic publication walker, and
redirected non-inline flat-scan terms there too. That experiment printed `0` at
quantum 5, then encountered another unsupported case in JOIN_APP_SCAN. It is not
a complete fix and should not be treated as a qualified patch.

## Caesar

Caesar has no startup banner: it first waits for UART input. However, supplying
input does not resolve its current failure. A physical trial sent `Az!` after
startup and received no output; LD6 was lit afterward.

The typed-source model consumes `A` at logical clock 187, completes one quantum
restart, then faults before output. The first failure is
`MICRO_JOIN_FLAT_SCAN` (41) at quantum zero: that scan rejects a non-inline graph
term instead of routing it through complete generic publication. PC is 34 and
FSP is 87. The program has only 120 working-arena words because static definitions
occupy the remainder of the 256-word graph.

The frontend RTL model independently reproduces the same microstate, fault 3,
PC and FSP with real 8N1 input bits for `Z`. It faults at board cycle 9,192,033,
after one restart and before any transmitted byte. Further memory limits may
appear after publication support is extended; these results establish the first
failure, not that fixing it will make the entire program fit.

## Reproduction and next engineering work

The standalone `check.py` now accepts `--case uart-alphanumerics` and
`--case uart-caesar-plus4`, or `--uart-examples` to include both alongside the
qualified smoke cases. Each full-example check demands its real output and halt;
faults and cycle-limit exhaustion are failures. The Caesar fixture sends
`Az09!` plus ESC and expects `Ed09!`. The simulation harness supports multiple
received bytes, while retaining its existing single-byte UART test.

See `scripts/boards/red2_standalone/README.md` for concrete commands. The local
evidence and hashes are recorded in `red2-uart-examples-results.json` alongside
this document; detailed logs are under `build/red2-uart-examples/`.

The next engine change should extend transactional generic publication to the
missing EP-parent, APP-scan and flat-scan cases, with reconstruction compared
against the reference machine. A rebuilt engine then needs area, timing, RTL and
physical qualification. Increasing quantum alone does not supply those semantics.

The deployment receipt's `passed` field means the data flash was programmed and
verified and configuration reset succeeded. It does not assert runtime success;
the command now explicitly prints the running, halted and fault LED meanings.
The diagnostic session restores the already qualified `clock-dots` image afterward.
