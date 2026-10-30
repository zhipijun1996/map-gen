#!/usr/bin/env python3
"""Development/build only: install immutable inputs, then compile an indexed cache.

The game never invokes this script or downloads resources. No source module changes.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OWN_TESTS = ['data_suite.gd', 'assembly_suite.gd', 'assembly_suite.tscn',
             'physics_suite.gd', 'physics_suite.tscn']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def copy_generator_source(target):
    """Do not copy the host's installed tests along with our own test folder."""
    target = Path(target)
    for folder in ['addons/mapgen', 'configs', 'example']:
        shutil.copytree(ROOT / 'godot' / folder, target / folder, dirs_exist_ok=True)
    (target / 'tests').mkdir(parents=True, exist_ok=True)
    for name in OWN_TESTS:
        shutil.copy2(ROOT / 'godot/tests' / name, target / 'tests' / name)


def install(target, archive=None, host_source=None, host_profile='native'):
    target = Path(target).resolve()
    lock = json.loads((ROOT / 'godot/configs/package-lock.json').read_text())
    archive = Path(archive) if archive else ROOT / '.cache/runtime-v1/map-edit-modules-1.0.0.zip'
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(lock['url'], timeout=90) as response:
            data = response.read()
        if digest(data) != lock['sha256']:
            raise ValueError('package_sha256_mismatch')
        archive.write_bytes(data)
    if digest(archive.read_bytes()) != lock['sha256']:
        raise ValueError('package_sha256_mismatch')
    pack = target / 'module_pack'
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            rel = Path(name)
            if rel.is_absolute() or '..' in rel.parts or '\\' in name:
                raise ValueError('unsafe_zip_path')
            if name.endswith('/'):
                continue
            data = source.read(name)
            dest = pack / rel
            if dest.exists() and dest.read_bytes() != data:
                raise ValueError('conflicting_package_file:' + name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    manifest = json.loads((pack / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if digest((pack / name).read_bytes()) != expected:
            raise ValueError('changed_package_file:' + name)
    spec = importlib.util.spec_from_file_location('locked_installer', pack / 'integration/install_host.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    dependency = manifest['hostDependency'] if host_profile == 'native' else 'runtime/host-lock-current-game.json'
    selected_host = json.loads((pack / dependency).read_text())
    lock.update(host_profile=selected_host['id'], host_commit=selected_host['commit'], host_dependency=dependency)
    host = installer.install(pack / dependency, target, host_source)
    if target != ROOT / 'godot':
        copy_generator_source(target)
        if not (target / 'project.godot').exists():
            shutil.copy2(ROOT / 'godot/project.godot', target / 'project.godot')
    (target / 'configs/package-lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    region_path = target / 'configs/plains.json'
    region = json.loads(region_path.read_text())
    region['runtime_host_profile'] = selected_host['id']
    if host_profile != 'native':
        region['fallback']['enabled'] = False
        region['host_qualification'] = 'API_INTEGRATION_ONLY; continuous route qualification pending on this host'
    region_path.write_text(json.dumps(region, ensure_ascii=False, indent=2) + '\n')
    receipt = {'schema': 'mapgen/install/1', 'lock': lock, 'host': host,
               'manifest_sha256': digest((pack / 'manifest.json').read_bytes()),
               'catalog_sha256': digest((pack / 'catalog.json').read_bytes()),
               'verified_package_files': len(manifest['files'])}
    (target / 'configs/installed.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=ROOT / 'godot')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--host-source', type=Path)
    parser.add_argument('--host-profile', choices=['native', 'current-game'], default='native')
    args = parser.parse_args()
    print(json.dumps(install(args.target, args.archive, args.host_source, args.host_profile), indent=2))
