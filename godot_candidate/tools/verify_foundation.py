"""Development oracle, never imported or executed by the GDScript component."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mapgen.contracts import GenerationRequest, GeneratorConfig
from mapgen.library import ModuleLibrary, PreparedLibrary
from mapgen.transform import materialize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module-zip', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--godot', default='godot')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    project = ROOT/'godot_candidate'
    for original, copied in [('reference_package/fixtures/vectors.json', 'tests/reference-vectors.json'),
                             ('examples/request-930001.json', 'tests/request.json'),
                             ('profiles/stable-v2.json', 'tests/config.json')]:
        assert (ROOT/original).read_bytes() == (project/copied).read_bytes(), original
    for suite in ['foundation', 'library', 'numbers', 'integer_hypot_probe']:
        command = [args.godot, '--headless', '--path', str(project), '--script', f'res://tests/{suite}.gd', '--', str(args.module_zip.resolve()), str((args.out/'library.json').resolve())]
        run = subprocess.run(command, text=True, capture_output=True, timeout=120)
        (args.out/f'{suite}.log').write_text(run.stdout+run.stderr)
        assert run.returncode == 0 and 'SCRIPT ERROR' not in run.stderr, run.stdout+run.stderr
    request = GenerationRequest.from_dict(json.loads((ROOT/'examples/request-930001.json').read_text()))
    config = GeneratorConfig.from_dict(json.loads((ROOT/'profiles/stable-v2.json').read_text()))
    source = ModuleLibrary.from_zip(args.module_zip, expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
    prepared = PreparedLibrary(source, request, config)
    actual = json.loads((args.out/'library.json').read_text())
    assert actual['keys'] == list(prepared.templates), 'template enumeration'
    assert actual['templates'] == prepared.templates, 'complete template data'
    for key, template in prepared.templates.items():
        assert actual['materialized'][key] == [materialize(template, mirror, prepared.block_pixels) for mirror in (False, True)], key
    raw = (args.out/'library.json').read_bytes()
    (args.out/'library.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    (args.out/'library.json').unlink()
    report = dict(status='PASS', comparison='all fields; numeric JSON equality (not byte hashes)',
                  source_sha256=source.sha256, modules=len(prepared.entries), templates=len(prepared.templates),
                  materialized_contents=len(prepared.templates)*2,
                  integer_hypot_vectors=1005,
                  gdscript_library_data_sha256=hashlib.sha256(raw).hexdigest(),
                  oracle='Python reference 0.2.0; GDScript runs in actual Godot Standard')
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
