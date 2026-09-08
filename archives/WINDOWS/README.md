# WINDOWS

Graphical user-interface code for the **PC-Scheme lambda-processor/RED2 simulator**.

Despite the directory name, this is not Microsoft Windows application code. It is a set of PC-Scheme/SCOOPS window classes used to visualize the simulated processor.

## Files

- `INTERFAC.S` — main graphical simulator interface. Displays registers, graph memory, environment, stack, etc., and supports stepping through LAC execution.
- `TEXTWIN.S` — text-window utilities.
- `SCROLLWI.S` — scrollable item display class.
- `VALUEWIN.S` — variable/register value display class.
- matching `.FSL` and `.SO` files — historical PC-Scheme compiled forms.
- `EDWIN.TMP` — editor/development artifact.

The source comments explicitly say the interface is built on **SCOOPS**, the Scheme object-oriented programming system.

This directory is not needed to understand the core reducer semantics, and a modern RED2 port can initially ignore the GUI calls (`show`, `send simulator ...`) or replace them with no-ops/tracing.
