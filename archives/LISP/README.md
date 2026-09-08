# LISP

An earlier **Common Lisp lambda-processor simulator**, mostly dated August–October 1988.

This looks like a predecessor to the 1989 PC-Scheme implementation in `COMMON/` + `PURE`/`FP`/`RED`.

## Files

- `CPU.LIS` — micro-simulator for the lambda processor. Comments say it was intended for development of microcode on the **AMD29300 evaluation board system**.
- `MEMORY.LIS` — simulated memory, registers, and stack objects.
- `TRANSLAT.LIS` — compiler/translator from lambda expressions to lambda-machine instruction code.
- `INTERFAC.LIS` — reducer setup, load/reduce/decompile operations, trace and statistics.
- `MONITOR.LIS` — elaborate graphical monitor for memory, graph, environment, registers, and stack.
- `TESTS.LIS` — reducer tests and performance statistics.
- `EXAMPLES.LIS` — example lambda programs including factorial, lists, reverse, numerical integration, and Picard iteration.

## Portability

This is historical Common Lisp using **Flavors/Lisp-Machine-style** facilities such as `defflavor`, `defmethod`, and `tv:` window classes. It is valuable documentation of the architecture but probably harder to execute unchanged on a modern Lisp than the plain algorithmic portions suggest.

For Asgard, use it as an independent earlier implementation against which to cross-check the later Scheme machine.
