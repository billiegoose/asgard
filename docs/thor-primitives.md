# THOR Primitive Reference

This file documents the user-visible primitive surface implemented by the
current Python THOR interpreter and RED2 model. It is a reference for deciding
which primitives are present today and where future language work might add
useful coverage.

## Current Primitives

### Language Forms

These are syntax or top-level forms rather than ordinary primitive functions:

- `LAMBDA` — lambda abstraction.
- `LETREC` — local mutually recursive bindings.
- `name == expr` — top-level symbolic definition.
- `tag |= accessor ...` — top-level structure declaration. This installs
  generated constructor/accessor definitions for the declared tag.

The source normalizer accepts lowercase aliases for core forms such as `lambda`
and `letrec`, but user-defined symbols remain case-sensitive.

### Constants

- `TRUE` — boolean true.
- `FALSE` — boolean false.
- `NIL` — empty list value, also parsed from `[]`.

Lowercase aliases `true`, `false`, and `nil` normalize to these constants when
not shadowed by a local binder.

### Control and Recursion

- `IF` — conditional. The condition is reduced first; only the selected branch
  is reduced when the condition becomes `TRUE` or `FALSE`.
- `Y` — fixpoint operator for explicit recursion.

### Logical Operators

- `AND` — non-strict logical conjunction over zero or more arguments.
- `OR` — non-strict logical disjunction over zero or more arguments.
- `NOT` — strict unary negation of `TRUE`/`FALSE`.

### Arithmetic Operators

- `+` — addition.
- `-` — subtraction.
- `*` — multiplication.
- `/` — division.
- `1-` — decrement.
- `1+` — increment.
- `MINUS` — unary numeric negation.
- `ABS` — absolute value.
- `FLOOR` — floor to integer.
- `CEILING` — ceiling to integer.
- `EXPT` — exponentiation.
- `MAX` — numeric maximum.
- `MIN` — numeric minimum.

Integer arithmetic preserves integer results where the implementation can do so;
otherwise numeric operations may produce floating-point values.

### Comparison and Equality

- `<` — numeric less-than.
- `>` — numeric greater-than.
- `=` — equality for constants.
- `EQUAL?` — structural/alpha equality for THOR expressions.

### Type Predicates

- `INTEGER?`
- `FLOAT?`
- `CHAR?`
- `SYMBOL?`
- `STRUCTURE?`

Predicates reduce only when enough information is available. For example, a
predicate applied to an irreducible application may remain partially reduced
rather than forcing a false result.

### Lists and Pairs

- `CONS` — constructs a `PAIR` structure.
- `CAR` — selects the first field of a `PAIR`.
- `CDR` — selects the second field of a `PAIR`.
- `NULL?` — tests whether a value is `NIL`.

Lists are syntax sugar over `PAIR` structures ending in `NIL`.

### Structures

- `TAG` — returns the tag symbol from a structure value.
- `make-<tag>` — generated constructor installed by `tag |= ...`.
- `<tag>-<accessor>` — generated accessor installed by `tag |= accessor ...`.

Generated helper names use the declared case exactly. For example:

```lisp
tree |= label subtrees
TREE |= LABEL
Tree |= Label

(make-tree 1 []) ; {tree 1 NIL}
(make-TREE 2)   ; {TREE 2}
(make-Tree 3)   ; {Tree 3}
```

`MAKE-TREE` is not automatically equivalent to `make-tree` unless the declared
tag spelling makes that the generated helper name.

## Case Policy

THOR symbols are case-sensitive in the current implementation. The normalizer
recognizes lowercase spellings of known built-in forms and primitives because
the dissertation uses uppercase names in the formal grammar and lowercase names
in Appendix A benchmark programs. This compatibility rule does not apply to
arbitrary user definitions or generated structure helpers.

Examples:

- `lambda` normalizes to `LAMBDA`.
- `if` normalizes to `IF`.
- `cons` normalizes to `CONS`.
- `make-tree` and `MAKE-TREE` are distinct symbols.
- `tree-label` and `TREE-LABEL` are distinct symbols.

## RED2 Internals Are Not THOR Primitives

RED2 uses machine instructions and bookkeeping cells such as `APP`, `VAR`,
`PNP`, `CLOSURE`, `UBV`, `RBLOCK`, `RUP`, and `JOIN`. These are implementation
internals. They should not be required in user THOR source, and CLI output should
not expose them as user-level results except when deliberately debugging the RED2
machine itself.

## Future Primitive Candidates

The following candidates would make THOR more useful as a programming language.
They are not all present today.

### Numeric Completeness

- `<=`, `>=`, `/=`, or `NOT=` comparisons.
- `ZERO?`, `POSITIVE?`, `NEGATIVE?`, `ODD?`.
- `MOD`, `QUOTIENT`, `REMAINDER`.
- More explicit integer/float coercions.
- Safer division behavior or documented divide-by-zero semantics.

### Character and String Support

- Character ordering and conversion primitives.
- String literals and string predicates.
- String concatenation, length, indexing, and substring operations.

### Symbol Utilities

- Symbol-to-string and string-to-symbol conversion.
- Symbol ordering or stable hashing if needed for maps/sets.

### List Library

- `LIST`, `APPEND`, `REVERSE`, `MAP`, `FILTER`, `FOLDL`, `FOLDR`, `LENGTH`.
- `MEMBER?`, `ASSOC`, `TAKE`, `DROP`, `NTH`.
- These can often be written in THOR, but built-ins may be useful for benchmarks
  or host-language interop.

### Structure and Record Utilities

- Arity inspection.
- Field access by index.
- Better diagnostics for applying the wrong accessor to a structure.

### Error and Undefined-Value Semantics

- A deliberate `ERROR` or `BOTTOM` value.
- Predicates or control forms for detecting failed primitive applications.
- Clearer behavior for arity mismatch and nonsensical applications.

### I/O and Host Interop

- Printing/tracing primitives for examples and debugging.
- File or environment access if THOR grows beyond pure reduction experiments.
- Foreign-function hooks for embedding THOR in Python tests or tools.

Future additions should be evaluated against both models: implement the THOR
semantics first, add the RED2 primitive behavior, then extend completion parity
and contraction-prefix parity diagnostics.
