# RED2 APP-VAR Slice Design

## Goal

Extend `models/python/red2_engine/mured.py` in place with Chapter 4's single-variable argument optimization, represented as `MuredOpcode.APP_VAR`.

## Scope

This slice adds only APP-VAR behavior:

- compile single variable arguments as inline `APP_VAR` spine words instead of `APP` pointing to a one-word `VAR` graph;
- execute forward/reverse APP-VAR transitions directly;
- make LAMBDA contract an APP-VAR argument by installing an unbound variable in the environment;
- make JOIN convert a reduced one-word VAR argument into APP-VAR and reclaim the VAR/JOIN tail words;
- decompile APP-VAR spine entries back to source applications;
- document that this is still not full RED2.

Out of scope: primitive firing, symbols/definition lookup, floats/chars, structures, recursion, CLI integration, Rust, or evaluator-backed execution.

## Transition Semantics

`APP_VAR` stores a corrected De Bruijn variable index in its data field. It is a spine argument word; source compilation emits it with `head=False`.

Forward APP-VAR:

1. Validate `word.data` is a non-negative integer and call `LOOKUP(word.data)`.
2. Increment `pc` to continue past the inline argument word.
3. If `s_a` addresses a `UBV`, push `Word(APP_VAR, phi - ubv.data, False)` to the result graph.
4. If `s_a` addresses a `CLOSURE`, push the closure path pointer on the control stack and push `Word(APP, closure_code, False)` to the result graph.
5. Other values are malformed redex-store values.

Reverse APP-VAR decrements `pc` only.

Forward LAMBDA contraction treats a result-head `APP_VAR` as a beta argument by allocating `Word(UBV, phi - app_var.data, False)` in the environment, decrementing `q`, reclaiming the APP-VAR result word, and advancing into the lambda body. It does not pop the control stack.

JOIN in reverse computes `s_a = pc + 1`. If that word is `VAR`, the parent APP word becomes `Word(APP_VAR, var.data, False)` and the two-word `VAR; JOIN` tail is reclaimed from `fsp`. Otherwise JOIN preserves the existing APP-pointer insertion behavior.

## Compiler/Decompiler

The compiler may optimize only arguments that are syntactically a single variable node (`Var` or an in-scope `Symbol`). Operators and non-variable arguments continue to use the existing APP-pointer graph layout. APP-VAR is not valid as a standalone source graph root.

Decompiler support is limited to APP-VAR entries inside an application spine. It reconstructs the inline variable argument while preserving source argument order.

## Validation

Tests must prove:

- compiler layout for `((LAMBDA (x) x) x)`-style bound variable arguments inside a lambda body;
- forward APP-VAR on UBV and CLOSURE environment values;
- reverse APP-VAR;
- LAMBDA contraction with APP-VAR installs the correct shifted UBV;
- JOIN converts reduced VAR arguments into APP-VAR and reclaims two words;
- semantic parity for small closed programs still holds;
- anti-shortcut checks remain green.
