"""Drive a generated RTL model through its packed public ports."""

import hashlib
import json
import subprocess
from pathlib import Path

from rtl_trace import PortLayout


class RTLServer:
    def __init__(self, top):
        self.layout = PortLayout(top)
        self.root = self.layout.top / "rtl-netlist/interactive-driver"
        manifest = json.loads((self.root / "provenance.json").read_text())
        self.trace_provenance = {
            "candidate_source_sha256": manifest["candidate_source_sha256"],
            "binary_sha256": manifest["binary_sha256"],
            "manifest_sha256": hashlib.sha256(
                (self.root / "provenance.json").read_bytes()
            ).hexdigest(),
        }
        self.binary = self.root / "server"
        inputs = {
            **manifest["inputs_sha256"],
            str(self.binary): manifest["binary_sha256"],
        }
        for name, digest in inputs.items():
            assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
        self.input_width = manifest["input_width"]
        self.output_width = manifest["output_width"]
        assert self.layout.schema(self.layout.input_type)[0] == self.input_width
        assert self.layout.schema(self.layout.output_type)[0] == self.output_width
        self.process = None

    def close(self):
        if self.process is None:
            return
        process, self.process = self.process, None
        process.stdin.close()
        try:
            code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            process.stdout.close()
        assert code == 0, ("RTL server failed", code)

    def reset(self):
        # Match native sim_reset(): a fresh simulation instance, including RAM
        # initialization. Architectural CMD_RESET remains a separate command.
        self.close()
        self.process = subprocess.Popen(
            [str(self.binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def exchange(self, bits):
        assert 0 <= bits < (1 << self.input_width)
        if self.process is None:
            self.reset()
        self.process.stdin.write(format(bits, "X") + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline().strip()
        assert len(line) == ((self.output_width + 31) // 32) * 8, (
            "RTL server ended or returned a malformed packet",
            line,
        )
        result = int(line, 16)
        assert result < (1 << self.output_width)
        return result

    def call(self, fn, command):
        assert fn.__name__ == "SynthesizableRED2Machine", fn
        bits, width = self.layout.pack(self.layout.input_type, command)
        assert width == self.input_width
        return self.layout.unpack(self.layout.output_type, self.exchange(bits))
