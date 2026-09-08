# RED

The most developed **PC-Scheme RED2/lambda-processor branch** in this archive, with explicit experiments in adding logic programming and unification.

This directory runs on top of the shared simulator infrastructure in `COMMON/` and GUI code in `WINDOWS/`.

## Files

- `INSTRUCT.S` — 622-line instruction implementation, dated 20 June 1989 and labelled “Modifications for logic programming.”
- `PRIMITIV.S` — arithmetic, comparisons, conditionals, recursion, boolean operations, structures, and other primitives.
- `UNIFY.S` — unification primitive and traversal machinery, dated 22 June 1989.
- `LOGIC.S` — begins with the comment **“Attempt at adding logic programming to red2”** and adds the `try` primitive and trail/reset behavior.
- `EQUAL.S` — alpha-equality traversal/predicate experiment.
- `FUNS.S` — small compiled-language examples (`fact`, `yfact`, lists, bottom).
- `TEST.S` — small test material.
- `SCHEME.INI` — PC-Scheme load/compile script.
- `FSL.BAT`, `EDWIN.TMP` — period development/build/editor artifacts.

## Importance for Asgard

This directory is direct historical evidence for RED2 implementation behavior. Read it together with:

- `COMMON/REDUCER.S` for the reducer loop/register model,
- `COMMON/COMPILE.S` for the LAC compiler,
- `FP/` for the cleaner pre-logic functional branch.

Because `RED/` deliberately experiments with logic programming, not every behavior here should automatically be treated as canonical core RED2 semantics. Where it differs from `FP/`, establish whether the change is a core fix or logic-specific before porting it.
