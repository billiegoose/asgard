# Pypeline/PipelineC RED2 Stepper Artifact

## Scope

`red2_stepper.py` is a fixed-width RED2 stepper subset for hardware exploration.
It is not a complete FPGA reducer: it classifies one encoded instruction word at
a time and returns packed status metadata instead of mutating RED2 graph memory.

## Mapping to the Python Model

The instruction word layout matches `red2_engine.instructions`:

- bit 31: head flag
- bits 24..30: opcode number
- bits 0..23: unsigned data field

The opcode numbers and names are the same as the Python RED2 `Opcode` enum. The
initial subset covers `STOP`, passive constants, `APP`, `VAR`, and `LAMBDA`
classification for golden vectors.

## Local Checks

Run the static artifact and golden vectors checks without FPGA vendor tools:

```bash
uv run pytest tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py
```

## Optional External Validation

To experiment with Pypeline/PipelineC locally, clone
<https://github.com/JulianKemmerer/PipelineC>, copy or symlink
`models/python/pypeline_red2/red2_stepper.py` into an examples workspace in that checkout, and
then run the Pypeline/PipelineC commands from the checkout's current docs.
