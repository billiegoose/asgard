"""Synthesizable RED2 Machine package.

The PipelineC/Pypeline implementation is loaded lazily so ordinary Python
development does not require the external hardware frontend.
"""

from typing import Any

__all__ = ["SynthesizableRED2Machine"]


def __getattr__(name: str) -> Any:
    if name == "SynthesizableRED2Machine":
        from synthesizable_red2_machine.machine import SynthesizableRED2Machine

        return SynthesizableRED2Machine
    raise AttributeError(name)
