"""Pack public-port native traces using the generated VHDL record layouts."""

import hashlib
import json
import re
from collections import namedtuple
from functools import cache
from pathlib import Path


class PortLayout:
    """Use the emitted VHDL record ordering for both trace and live RTL I/O."""

    def __init__(self, top):
        self.top = Path(top)
        source = (self.top / "hdl/c_structs_pkg.pkg.vhd").read_text()
        self.records = {}
        for name, body in re.findall(
            r"type (\w+) is record\s+(.*?)end record;", source, re.S
        ):
            self.records[name] = re.findall(
                r"(\w+)\s*:\s*(unsigned\(\d+ downto 0\)|\w+)\s*;", body
            )
        ports = (self.top / "hdl/top/top.vhd").read_text()
        self.input_type = re.search(r"incoming_command\s*:\s*in (\w+)", ports)[1]
        self.output_type = re.search(r"return_output\s*:\s*out (\w+)", ports)[1]
        self.schema = cache(self._schema)

    def pack(self, typ, value):
        scalar = re.fullmatch(r"unsigned\((\d+) downto 0\)", typ)
        if scalar:
            width = int(scalar[1]) + 1
            return int(value) & ((1 << width) - 1), width
        fields = self.records[typ]
        assert {name for name, _ in fields} == set(value._fields)
        result = width = 0
        for name, subtype in fields:
            bits, size = self.pack(subtype, getattr(value, name))
            result |= bits << width
            width += size
        return result, width

    def _schema(self, typ):
        scalar = re.fullmatch(r"unsigned\((\d+) downto 0\)", typ)
        if scalar:
            return int(scalar[1]) + 1, None, ()
        fields = self.records[typ]
        offset = 0
        parts = []
        for _, subtype in fields:
            width, _, _ = self.schema(subtype)
            parts.append((subtype, offset, (1 << width) - 1))
            offset += width
        return offset, namedtuple(typ, [name for name, _ in fields]), parts

    def unpack(self, typ, bits):
        width, cls, parts = self.schema(typ)
        if cls is None:
            return bits & ((1 << width) - 1)
        return cls(
            *(
                self.unpack(subtype, (bits >> offset) & mask)
                for subtype, offset, mask in parts
            )
        )


class Trace(PortLayout):
    def __init__(self, top, destination):
        super().__init__(top)
        self.destination = Path(destination)
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.destination.open("x")
        self.count = 0

    def append(self, command, output):
        incoming, self.input_width = self.pack(self.input_type, command)
        expected, self.output_width = self.pack(self.output_type, output)
        self.file.write(
            f"{incoming:0{(self.input_width + 3) // 4}X} "
            f"{expected:0{(self.output_width + 3) // 4}X}\n"
        )
        self.count += 1

    def close(self):
        self.file.close()
        metadata = {
            "cycles": self.count,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "input_width": self.input_width,
            "output_width": self.output_width,
            "candidate_sha256": hashlib.sha256(
                (self.top / "machine.py").read_bytes()
            ).hexdigest(),
            "vectors_sha256": hashlib.sha256(self.destination.read_bytes()).hexdigest(),
        }
        self.destination.with_suffix(".json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
