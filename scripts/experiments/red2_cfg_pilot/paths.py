"""Locations shared by the isolated RED2 control-flow experiment."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(
    os.environ.get("RED2_CFG_PILOT_OUT", ROOT / "build" / "red2-cfg-pilot")
).resolve()
OUT.mkdir(parents=True, exist_ok=True)
INCLUDE_LOOKUP = os.environ.get("RED2_CFG_PILOT_LOOKUP", "0") == "1"
EXTRA_STATES = tuple(
    filter(None, os.environ.get("RED2_CFG_PILOT_EXTRA_STATES", "").split(","))
)
INCLUDE_GRAPH = os.environ.get("RED2_CFG_PILOT_GRAPH", "0") == "1"
PUBLICATION_READS = os.environ.get("RED2_CFG_PILOT_PUBLICATION_READS", "0") == "1"
PUBLICATION_TRANSACTIONS = (
    os.environ.get("RED2_CFG_PILOT_PUBLICATION_TRANSACTIONS", "0") == "1"
)
assert not (PUBLICATION_READS and PUBLICATION_TRANSACTIONS)
SPARSE_PUBLICATION = os.environ.get("RED2_CFG_PILOT_SPARSE_PUBLICATION", "0") == "1"
assert not SPARSE_PUBLICATION or PUBLICATION_TRANSACTIONS
PUBLICATION_LAUNCHES = os.environ.get("RED2_CFG_PILOT_PUBLICATION_LAUNCHES", "0") == "1"
assert not PUBLICATION_LAUNCHES or PUBLICATION_TRANSACTIONS
SCALAR_CORE = os.environ.get("RED2_CFG_PILOT_SCALAR_CORE", "0") == "1"
assert not SCALAR_CORE or INCLUDE_GRAPH
LITERAL_METADATA = os.environ.get("RED2_CFG_PILOT_LITERAL_METADATA", "0") == "1"
assert not LITERAL_METADATA or PUBLICATION_TRANSACTIONS
INTEGER_JOINS = os.environ.get("RED2_CFG_PILOT_INTEGER_JOINS", "0") == "1"
REVERSE_CONTROL = os.environ.get("RED2_CFG_PILOT_REVERSE_CONTROL", "0") == "1"
assert not REVERSE_CONTROL or INCLUDE_GRAPH
assert not INTEGER_JOINS or os.environ.get("RED2_SYN_FLOAT", "0") == "0"
INTEGRATED = OUT / os.environ.get("RED2_CFG_PILOT_INTEGRATED_NAME", "integrated")

assert int(os.environ.get("RED2_SYN_GRAPH_WORDS", "256")) == 256, (
    "RED2 CFG experiments require RED2_SYN_GRAPH_WORDS=256"
)
