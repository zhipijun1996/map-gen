#!/usr/bin/env python3
"""Build a deterministic portable reference bundle from committed, explicit inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mapgen import ModuleLibrary
from mapgen.package_info import PACKAGE_VERSION, ALGORITHM_ID, IMPLEMENTATION_ID, RUNTIME_TARGET, READINESS, SCHEMAS

NAME = 'mapgen-python-reference-' + PACKAGE_VERSION


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(out, archive, lock_path, source_commit):
    if out.exists():
        raise ValueError('refusing to overwrite a reference release')
    source_commit = subprocess.check_output(['git', 'rev-parse', source_commit], cwd=ROOT, text=True).strip()
    builder_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    builder_bytes = Path(__file__).read_bytes()
    if subprocess.check_output(['git', 'show', source_commit + ':' + builder_rel], cwd=ROOT) != builder_bytes:
        raise ValueError('build tool differs from the specified source commit')
    lock = json.loads(lock_path.read_text()); module_bytes = archive.read_bytes()
    library = ModuleLibrary.from_bytes(module_bytes, expected_sha256=lock['sha256'])
    native_manifest = library.read('manifest.json')
    if library.version != lock['version'] or sha(library._files['catalog.json']) != lock['catalog_sha256']:
        raise ValueError('module version/catalog differs from explicit lock')
    files = {}; sources = {}
    def add(target, source):
        source = source.resolve(); rel = source.relative_to(ROOT).as_posix(); data = source.read_bytes()
        committed = subprocess.check_output(['git', 'show', source_commit + ':' + rel], cwd=ROOT)
        if data != committed:
            raise ValueError('package input not equal to committed source:' + rel)
        files[target] = data; sources[target] = dict(repository_path=rel, sha256=sha(data))
    for p in sorted((ROOT / 'mapgen').glob('*.py')):
        add('mapgen/' + p.name, p)
    for p in sorted((ROOT / 'schemas').glob('*.json')):
        add('schemas/' + p.name, p)
    add('profiles/stable-v2.json', ROOT / 'profiles/stable-v2.json')
    add('pyproject.toml', ROOT / 'pyproject.toml')
    add('reference.py', ROOT / 'reference_package/entry.py')
    add('README.md', ROOT / 'reference_package/docs/README.md')
    for p in sorted((ROOT / 'reference_package/docs').glob('*.md')):
        if p.name != 'README.md':
            add('docs/' + p.name, p)
    add('docs/host-review.json', ROOT / 'reference_package/host-review.json')
    add('call_example.py', ROOT / 'reference_package/call_example.py')
    fixtures = ROOT / 'reference_package/fixtures'
    for case in ('success', 'failure'):
        for p in sorted((fixtures / case).rglob('*')):
            if p.is_file():
                add('samples/' + case + '/' + p.relative_to(fixtures / case).as_posix(), p)
    add('determinism/vectors.json', fixtures / 'vectors.json')
    add('dependencies/python-lock.json', fixtures / 'python-lock.json')
    add('dependencies/module-lock.json', lock_path)
    module_ref = 'dependencies/map-edit-modules-' + lock['version'] + '.zip'
    files[module_ref] = module_bytes
    index_path = fixtures / 'samples.json'; index_rel = index_path.relative_to(ROOT).as_posix(); index_bytes = index_path.read_bytes()
    if subprocess.check_output(['git', 'show', source_commit + ':' + index_rel], cwd=ROOT) != index_bytes:
        raise ValueError('sample index differs from the specified source commit')
    samples = json.loads(index_bytes)
    manifest = dict(schema='mapgen/reference-package/v1', package=dict(name=NAME, version=PACKAGE_VERSION, algorithm=ALGORITHM_ID, implementation=IMPLEMENTATION_ID),
                    runtime_target=RUNTIME_TARGET, readiness=READINESS,
                    source=dict(repository='https://github.com/zhipijun1996/map-gen', commit=source_commit, base_commit='178c40164c2f7371ce1c8a56cde658e84a4f42c2',
                                builder=dict(repository_path=builder_rel, sha256=sha(builder_bytes)),
                                sample_index=dict(repository_path=index_rel, sha256=sha(index_bytes)), files=sources),
                    protocol=dict(request=dict(schema=SCHEMAS['request'], file='schemas/request.schema.json'),
                                  config=dict(schema=SCHEMAS['config'], file='schemas/config.schema.json'),
                                  result=dict(schema=SCHEMAS['result'], file='schemas/result.schema.json'),
                                  map=dict(schema=SCHEMAS['map'], file='schemas/runtime-map.schema.json'), content_schema=SCHEMAS['content']),
                    module_lock_ref='dependencies/module-lock.json', module_zip_ref=module_ref,
                    module_compatibility=dict(version=lock['version'], sha256=lock['sha256'], catalog_sha256=lock['catalog_sha256'],
                                              package_schema=native_manifest['schema'], catalog_schema=library.read('catalog.json')['schema'],
                                              foundation=native_manifest['foundation'], native_source=native_manifest['source'],
                                              qualification='Original module evidence remains scoped; no arbitrary seam/mirror/seal or current-host certification.'),
                    determinism=dict(rules='docs/PROTOCOL.md', migration='docs/GODOT_RUNTIME.md', vectors='determinism/vectors.json',
                                     result_projection='mapgen.artifacts.deterministic_result removes only metrics.generation_seconds'),
                    samples=samples, files={name: sha(data) for name, data in sorted(files.items())})
    files['manifest.json'] = encoded(manifest)
    with tempfile.TemporaryDirectory(prefix='mapgen-reference-build-') as temp:
        root = Path(temp) / NAME
        for name, data in files.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        command = [sys.executable, '-I', '-S', str(root / 'reference.py'), 'verify', '--module-zip', str(root / module_ref)]
        checked = subprocess.run(command, cwd=temp, capture_output=True, text=True)
        if checked.returncode:
            raise RuntimeError(checked.stdout + checked.stderr)
        validation = json.loads(checked.stdout)
        zipped = Path(temp) / (NAME + '.zip')
        with zipfile.ZipFile(zipped, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
                z.writestr(info, data, compresslevel=9)
        out.mkdir(parents=True)
        dest = out / zipped.name; shutil.copyfile(zipped, dest)
        (out / (zipped.name + '.sha256')).write_text(sha(dest.read_bytes()) + '  ' + zipped.name + '\n')
        receipt = dict(status='PASS', archive=zipped.name, archive_sha256=sha(dest.read_bytes()), bytes=dest.stat().st_size,
                       source_commit=source_commit, runtime_target=RUNTIME_TARGET, readiness=READINESS, verification=validation)
        (out / 'receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module-zip', type=Path, required=True); p.add_argument('--module-lock', type=Path, required=True)
    p.add_argument('--source-commit', default='HEAD'); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.out, args.module_zip, args.module_lock, args.source_commit), ensure_ascii=False, indent=2))
