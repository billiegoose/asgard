"""Locations shared by the isolated RED2 control-flow experiment."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(
    os.environ.get("RED2_CFG_PILOT_OUT", ROOT / "build" / "red2-cfg-pilot")
).resolve()
OUT.mkdir(parents=True, exist_ok=True)
INCLUDE_LOOKUP = os.environ.get("RED2_CFG_PILOT_LOOKUP", "0") == "1"
