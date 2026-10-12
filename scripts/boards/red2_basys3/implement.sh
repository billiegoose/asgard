#!/usr/bin/env bash
set -euo pipefail

# Run only inside the pinned fpgatool Nix development shell.
: "${FPGA_TOOL_CHIPDB_DIR:?missing fpgatool chip database}"
: "${PRJXRAY_DB_DIR:?missing Project X-Ray database}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
record = json.loads(Path('provenance.json').read_text())
for name, expected in record['files_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
assert not Path('red2_basys3.bit').exists(), 'use a new output directory for a new build'
PY
yosys -V > backend-versions.txt
nextpnr-xilinx --chipdb "$FPGA_TOOL_CHIPDB_DIR/xc7a35tcpg236.bin" --version \
    >> backend-versions.txt 2>&1
yosys -Q -T -s board.ys > board-map.log 2>&1
python3 yosys_resources.py board.json --top red2_basys3 > board-resources.json
python3 - <<'PY'
import json
from pathlib import Path
resources = json.loads(Path('board-resources.json').read_text())
assert resources['within_basys3_resource_limits'], resources
assert resources['primitives'].get('MMCME2_ADV') == 1, 'expected one board clock generator'
assert resources['primitives'].get('BUFGCE') == 1, 'expected one core clock gate'
assert 'Found and reported 0 problems' in Path('board-map.log').read_text()
print('BOARD_MAPPING_PASS', resources['lut_total'], flush=True)
PY
nextpnr-xilinx \
    --chipdb "$FPGA_TOOL_CHIPDB_DIR/xc7a35tcpg236.bin" \
    --xdc board.xdc --json board.json --fasm board.fasm --seed 1 \
    > board-route.log 2>&1
python3 - <<'PY'
import json, re
from pathlib import Path
log = Path('board-route.log').read_text()
clocks = {}
for name, achieved, status, required in re.findall(
    r"Max frequency for clock '([^']+)': ([0-9.]+) MHz \((PASS|FAIL) at ([0-9.]+) MHz\)", log
):
    clocks[name] = {'achieved_mhz': float(achieved), 'status': status, 'required_mhz': float(required)}
assert clocks, 'no clock timing result; do not load this design'
assert all(c['status'] == 'PASS' for c in clocks.values()), clocks
netnames = json.loads(Path('board.json').read_text())['modules']['red2_basys3']['netnames']
for wanted in ['clock', 'core_clock']:
    bits = netnames[wanted]['bits']
    aliases = {name for name, net in netnames.items() if net['bits'] == bits}
    matches = [value for name, value in clocks.items() if name in aliases]
    assert matches, f'no routed timing result for {wanted}; aliases={aliases}'
    assert all(abs(value['required_mhz'] - 10) < 0.01 for value in matches), matches
Path('board-timing.json').write_text(json.dumps(clocks, indent=2) + '\n')
print('BOARD_ROUTED_TIMING_PASS', clocks, flush=True)
PY
part=xc7a35tcpg236-1
fasm2frames --part "$part" --db-root "$PRJXRAY_DB_DIR/artix7" board.fasm > board.frames
xc7frames2bit --part_file "$PRJXRAY_DB_DIR/artix7/$part/part.yaml" \
    --part_name "$part" --frm_file board.frames --output_file red2_basys3.bit
python3 - <<'PY'
import hashlib, json
from pathlib import Path
record = {'built': True, 'loaded_on_board': False, 'files_sha256': {}}
for name in ['red2_basys3.bit', 'board.json', 'board.xdc', 'board-map.log', 'board-route.log', 'board-resources.json', 'board-timing.json', 'backend-versions.txt', 'provenance.json']:
    record['files_sha256'][name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
Path('build-result.json').write_text(json.dumps(record, indent=2) + '\n')
PY
printf 'BOARD_BITSTREAM_BUILD_PASS\n'
