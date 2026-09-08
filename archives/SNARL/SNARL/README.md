# SNARL/SNARL

A strong candidate for the **January 11, 1990 Version 1.0 release snapshot** of the C HORSE/SNARL system.

The original `README` explicitly says:

> HORSE now conforms to the user's manual. Releasing Version 1.0!

`MAIN.C` identifies itself as Version 1.0. The source tree contains the complete program: reducer, primitive implementation, arithmetic, compiler/parser, printer, editor/debug support, and header.

## Examples

- `SIEVE.LAM` — lazy prime sieve/infinite lists.
- `SINE.LAM` — constructive sine.
- `HUGHES.LAM` — higher-order/list/tree examples from Hughes.
- `LISTS.LAM` — list and string prelude.

## Relationship to `THOR/`

`THOR/` is a later, extremely close descendant. Core diffs show mostly branding/copyright changes, the explicit rename of `RED.C` comments from “SNARL” to “THOR,” and generalization of the startup list file into `PRELUDE.LAM`. `THOR/` files have May 1990 timestamps versus January here.

Therefore this directory is an excellent historical release reference, while `THOR/` is probably the best later C tree to revive.
