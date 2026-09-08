# CRED

A small collection of `.LAM` programs for the C/HORSE-era language.

## Files

- `HUGHES.LAM` — examples adapted from John Hughes' **“Why Functional Programming Matters”**: reductions over lists, mapping, reversing, trees, etc.
- `SINE.LAM` — constructive sine implementation adapted from Gerald Roylance's L&FP '88 work.
- `TEST.LAM` — useful language/reducer tests involving infinite lists, `Y`, `letrec`, structures, list processing, and higher-order functions.
- `KJBTESTS.LAM` — 21 compact lambda terms, apparently a test corpus associated with Klaus J. Berkling.

These are good sources of historical THOR/HORSE examples. `TEST.LAM` and `KJBTESTS.LAM` are especially attractive as Asgard conformance inputs because they exercise reducer fundamentals without depending on the later logic-programming experiments.
