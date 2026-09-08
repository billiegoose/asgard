# MANUAL

TeX source for **User's Manual and Programming Guide for THOR/HORSE, Version 1.0**, copyright 1990, by Klaus J. Berkling and Michael L. Hilton of Syracuse University.

This is **not the dissertation manuscript**, but it is probably the single best surviving source for the intended user-visible THOR semantics.

## Files

- `MANUAL.TEX` — document root, introduction, bibliography, and front matter.
- `THOR.TEX` — large language-reference chapter: THOR syntax, abstractions, constants, lists, structures, primitives, recursion, and informal semantics.
- `HORSE.TEX` — programming-environment chapter. States that HORSE ran on IBM PCs and Sun workstations and explains invocation, commands, loading files, reduction control, etc.
- `EXAMPLE.TEX` — extended constructive-programming example using sine, adapted from Gerald Roylance.

`MANUAL.TEX` identifies THOR as a lazy, untyped functional language with normal-order semantics and HORSE as its programming environment.

For Asgard, this directory should be used alongside the implementation sources whenever language-level behavior is ambiguous.
