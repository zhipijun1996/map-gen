#!/usr/bin/env python3
"""Build an offline Godot project ZIP and a small reusable addon archive."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def build():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    host = ROOT / 'godot'
    lock = json.loads((host / 'module_pack/runtime/host-lock.json').read_text())
    manifest = json.loads((host / 'module_pack/manifest.json').read_text())
    for rel, expected in lock['files'].items():
        if hashlib.sha256((host / rel).read_bytes()).hexdigest() != expected:
            raise ValueError('changed_host:' + rel)
    for rel, expected in manifest['files'].items():
        if hashlib.sha256((host / 'module_pack' / rel).read_bytes()).hexdigest() != expected:
            raise ValueError('changed_package:' + rel)
    source = [host / 'project.godot']
    for folder in ['addons/mapgen', 'example', 'configs', 'tests']:
        source.extend(p for p in (host / folder).rglob('*') if p.is_file() and p.suffix != '.uid')
    archives = {}
    files = source + [host / rel for rel in lock['files']] + [host / 'module_pack' / rel for rel in manifest['files']] + [host / 'module_pack/manifest.json']
    addon = [p for p in source if p.relative_to(host).parts[0] in ['addons', 'configs']]
    for name, members in [('mapgen-godot-0.1.0-offline.zip', files), ('mapgen-addon-0.1.0.zip', addon)]:
        path = output / name
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for member in sorted(set(members)):
                info = zipfile.ZipInfo(str(member.relative_to(host)), date_time=(2026, 10, 30, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, member.read_bytes())
            if 'addon' in name:
                z.writestr('INSTALL.txt', 'Install the locked module_pack and host dependencies using tools/runtime/install.py from zhipijun1996/map-gen. Copy addons/mapgen and the matching configs into your host; keep the host project.godot and existing player/services. See docs/GODOT_RUNTIME.md in the repository.\n')
        archives[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'files': len(set(members))}
    (output / 'SHA256.json').write_text(json.dumps(archives, indent=2) + '\n')
    print(json.dumps(archives, indent=2))


if __name__ == '__main__':
    build()
