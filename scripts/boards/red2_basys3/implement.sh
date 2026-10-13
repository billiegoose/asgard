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
    --xdc board.xdc --freq 10 --json board.json --seed 1 \
    --parallel-refine --threads 4 --no-route --write board-placed.json \
    > board-place.log 2>&1
placement=board-placed.json
if python3 -c 'import json; raise SystemExit(not json.load(open("board-placement-options.json"))["relocate_response_byte"])'; then
    python3 relocate_monitor.py board-placed.json \
        --output board-placed-serializer.json --report board-serializer-moves.json \
        --first-bit 0 --count 8
    placement=board-placed-serializer.json
fi
python3 - "$placement" <<'PY'
import hashlib, json, sys
from pathlib import Path
path = Path(sys.argv[1])
Path('board-selected-placement.json').write_text(json.dumps({
    'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()
}, indent=2) + '\n')
PY
python3 clocks.py "$placement" --sdc board-route.sdc --report board-clock-names.json
nextpnr-xilinx \
    --chipdb "$FPGA_TOOL_CHIPDB_DIR/xc7a35tcpg236.bin" \
    --sdc board-route.sdc --freq 10 --json "$placement" --no-pack --no-place --seed 1 \
    --router2-bb-expand-max 12 --router2-cong-mult 1.2 -o hold-fix=8 \
    --fasm board.fasm --report board-route-report.json --write board-routed.json \
    > board-route.log 2>&1
python3 audit.py "$placement" board-routed.json \
    "$PRJXRAY_DB_DIR/artix7/xc7a50t/tilegrid.json" > board-physical-lut-sites.json
python3 - <<'PY'
import json, re
from pathlib import Path
log = Path('board-route.log').read_text()
assert 'Program finished normally.' in log
assert re.search(r'overused=0 overuse=0 (?:resources=.*? )?archfail=0', log)
audit = json.loads(Path('board-physical-lut-sites.json').read_text())
print('BOARD_PHYSICAL_LUT_FIT_PASS', audit['unique_physical_lut_sites'], flush=True)
clocks = {}
for name, achieved, status, required in re.findall(
    r"Max frequency for clock\s+'([^']+)': ([0-9.]+) MHz \((PASS|FAIL) at ([0-9.]+) MHz\)", log
):
    clocks[name] = {'achieved_mhz': float(achieved), 'status': status, 'required_mhz': float(required)}
assert clocks, 'no clock timing result; do not load this design'
assert all(c['status'] == 'PASS' for c in clocks.values()), clocks
required = json.loads(Path('board-clock-names.json').read_text())
for wanted in required.values():
    assert wanted in clocks, f'no routed timing result for {wanted}'
    assert abs(clocks[wanted]['required_mhz'] - 10) < 0.01, clocks[wanted]
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
for name in ['red2_basys3.bit', 'board.json', 'board.xdc', 'board.sdc',
    'board-route.sdc', 'board-clock-names.json', 'clocks.py',
    'board-map.log', 'board-place.log', 'board-placed.json', 'board-route.log',
    'board-routed.json', 'board-route-report.json', 'board-physical-lut-sites.json',
    'board-resources.json', 'board-timing.json', 'backend-versions.txt', 'provenance.json',
    'audit.py', 'relocate_monitor.py', 'board-placement-options.json',
    'board-selected-placement.json']:
    record['files_sha256'][name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
if json.loads(Path('board-placement-options.json').read_text())['relocate_response_byte']:
    for name in ['board-placed-serializer.json', 'board-serializer-moves.json']:
        record['files_sha256'][name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
Path('build-result.json').write_text(json.dumps(record, indent=2) + '\n')
PY
printf 'BOARD_BITSTREAM_BUILD_PASS\n'
