#!/usr/bin/env python3
"""CI gate: Godot exit status AND actual logs, including error-after-PASS cases."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(engine, args, name, limit=180):
    log = ROOT / 'reports/runtime-v1' / (name + '.log')
    completed = subprocess.run([str(engine), '--headless', '--path', str(ROOT / 'godot'), *args],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=limit)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(completed.stdout)
    text = completed.stdout.decode(errors='replace')
    if completed.returncode or 'SCRIPT ERROR:' in text or '\nERROR:' in text:
        raise RuntimeError(f'{name}: Godot failure; see {log}')
    print(name, 'PASS', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--godot', required=True, type=Path)
    p.add_argument('--import-only', action='store_true')
    a = p.parse_args()
    run(a.godot, ['--editor', '--import'], 'ci-import', 300)
    if not a.import_only:
        # These deterministic output directories are suitable for clean CI jobs.
        # Archive previous local reports before intentionally rerunning this gate.
        run(a.godot, ['tests/physics_suite.tscn', '--fixed-fps', '60'], 'ci-physics')
        run(a.godot, ['--script', 'tests/data_suite.gd'], 'ci-data')
        run(a.godot, ['tests/assembly_suite.tscn', '--fixed-fps', '60'], 'ci-assembly')
        for script in ['prototype/verify.py', 'tools/verify_progress.py']:
            subprocess.run(['python3', script], cwd=ROOT, check=True)
