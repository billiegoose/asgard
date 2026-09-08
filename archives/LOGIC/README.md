# LOGIC

A collection of **Scheme logic-programming and automated-theorem-proving experiments** by Mike Hilton, mostly March–April 1989.

These files are not the THOR interpreter itself. They appear to be exploratory work feeding into or motivating later attempts to add logic programming/unification to the reducer.

## Files

- `BASICS.S` — clause/literal/logic-variable representation, unification and common resolution utilities.
- `FULL.S` — full first-order predicate-logic interpreter based on van Emden's Prolog interpreting algorithm.
- `PROLOG.S` — compact Prolog interpreter adapted from M. Nilsson.
- `HYPER.S` — hyper-resolution theorem prover.
- `LOCK.S`, `LOCK2.S` — two versions of a lock-resolution theorem prover.
- `FORMAT.S` — formatted-output and structure-printing utilities.
- `TEST.S`, `TEST2.S`, `TEST3.S` — logic test problems.

These are historically interesting for understanding why unification and trail/reset machinery later appear in `RED/`, `DEC6/`, and `WORK/`, but they are not primary references for core THOR/RED2 reduction semantics.
