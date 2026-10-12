"""Prepare GHDL replay of a successful public-port native program trace."""

import hashlib
import json
import os
import shlex
from pathlib import Path

from paths import INTEGRATED

trace = Path(os.environ["RED2_CFG_PILOT_TRACE"]).resolve()
data = json.loads(trace.with_suffix(".json").read_text())
assert trace.is_relative_to(INTEGRATED.parent)
assert hashlib.sha256(trace.read_bytes()).hexdigest() == data["vectors_sha256"]
assert (
    hashlib.sha256((INTEGRATED / "machine.py").read_bytes()).hexdigest()
    == data["candidate_sha256"]
)
root = trace.parent
container_root = "/experiment/" + str(root.relative_to(INTEGRATED.parent))
hdl = INTEGRATED / "hdl"
files = [Path(p).resolve() for p in (hdl / "vhdl_files.txt").read_text().split()]
provenance = json.loads((INTEGRATED / "provenance.json").read_text())
for p in files:
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == provenance["hdl_files_sha256"][str(p.relative_to(hdl))]
    )
incoming, outgoing = data["input_type"], data["output_type"]
bench = f"""library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;
use std.env.all;
use work.c_structs_pkg.all;
entity red2_replay is end;
architecture test of red2_replay is
  signal clk : std_logic := '0';
  signal command : {incoming} := {incoming}_NULL;
  signal result : {outgoing};
begin
  dut : entity work.top port map(clk, command, result);
  process
    file vectors : text open read_mode is "{container_root}/{trace.name}";
    variable row : line;
    variable input_bits : std_logic_vector({data["input_width"] - 1} downto 0);
    variable expected : std_logic_vector({data["output_width"] - 1} downto 0);
    variable actual : std_logic_vector({data["output_width"] - 1} downto 0);
    variable cycle : integer := 0;
  begin
    while not endfile(vectors) loop
      readline(vectors, row);
      hread(row, input_bits);
      hread(row, expected);
      command <= slv_to_{incoming}(input_bits);
      wait for 5 ns;
      actual := {outgoing}_to_slv(result);
      assert actual = expected
        report "RTL mismatch cycle " & integer'image(cycle) &
          " actual " & to_hstring(actual) & " expected " & to_hstring(expected)
        severity failure;
      clk <= '1';
      wait for 5 ns;
      clk <= '0';
      cycle := cycle + 1;
    end loop;
    assert cycle = {data["cycles"]} severity failure;
    report "INTEGRATED_RTL_REPLAY_PASS " & integer'image(cycle);
    finish;
  end process;
end;
"""
(root / "replay.vhd").write_text(bench)
ghdl = "/nix/store/4gcl6ba0jcmvq2py06cz57fimap9xjvm-ghdl-mcode-6.0.0/bin/ghdl"
args = " ".join(
    shlex.quote("/experiment/" + str(p.relative_to(INTEGRATED.parent))) for p in files
)
work = shlex.quote(container_root + "/work")
(root / "run.sh").write_text(
    "#!/usr/bin/env bash\nset -euo pipefail\n"
    f"mkdir -p {work}\n"
    f"{ghdl} -a --std=08 --workdir={work} {args} {container_root}/replay.vhd\n"
    f"{ghdl} -e --std=08 --workdir={work} red2_replay\n"
    f"{ghdl} -r --std=08 --workdir={work} red2_replay "
    "--assert-level=error --ieee-asserts=disable-at-0\n"
)
print("PREPARED_INTEGRATED_RTL_REPLAY", root, data["cycles"], flush=True)
