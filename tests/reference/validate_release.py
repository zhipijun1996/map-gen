#!/usr/bin/env python3
"""Validate an actual ZIP in isolation, replay real samples, and retain receipts."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mapgen.artifacts import result_hashes, deterministic_result


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def resign(root):
    manifest = read(root / 'manifest.json')
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json' and '__pycache__' not in p.parts}
    manifest['files'] = files
    for name in list(manifest['source']['files']):
        if name not in files:
            del manifest['source']['files'][name]
        else:
            manifest['source']['files'][name]['sha256'] = files[name]
    write(root / 'manifest.json', manifest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True); p.add_argument('--module-zip', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite release validation')
    expected = args.archive.with_name(args.archive.name + '.sha256').read_text().split()[0]
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != expected:
        raise ValueError('outer ZIP hash mismatch')
    receipts = []
    with tempfile.TemporaryDirectory(prefix='mapgen-reference-isolated-') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(args.archive) as z:
            names = z.namelist()
            if len(names) != len(set(names)):
                raise ValueError('duplicate ZIP member')
            for info in z.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError('unsafe ZIP member')
            roots = {n.split('/')[0] for n in names}; assert len(roots) == 1
            z.extractall(temp)
        root = temp / next(iter(roots)); work = temp / 'unrelated-working-directory'; work.mkdir()
        assert not any((root / n).exists() for n in ('experiments', 'prototype', 'delivery', '.cache'))
        manifest = read(root / 'manifest.json'); module = root / manifest['module_zip_ref']
        assert module.read_bytes() == args.module_zip.read_bytes()
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
        def run(command, bundle=root, extra=(), expected_code=0, module_path=None):
            dependency = module_path or bundle / manifest['module_zip_ref']
            cmd = [sys.executable, '-B', '-I', '-S', str(bundle / 'reference.py'), command, '--module-zip', str(dependency), *map(str, extra)]
            result = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=120)
            if result.returncode != expected_code:
                raise RuntimeError(' '.join(cmd) + '\n' + result.stdout + result.stderr)
            text = result.stdout if expected_code == 0 or command == 'generate' else result.stderr
            return json.loads(text)
        receipts.append(dict(check='isolated_file_content_graph_validation', result=run('verify')))
        receipts.append(dict(check='isolated_frozen_success_and_failure_replay', result=run('replay')))
        for case, code in [('success', 0), ('failure', 2)]:
            output = work / ('generated-' + case); path = root / 'samples' / case
            result = run('generate', extra=('--request', path / 'request.json', '--config', path / 'config.json', '--out', output), expected_code=code)
            got = read(output / 'result.json'); frozen = read(path / 'result.json')
            assert deterministic_result(got) == deterministic_result(frozen)
            assert result_hashes(got) == result_hashes(frozen)
            if case == 'failure':
                assert {p.name for p in output.iterdir()} == {'result.json'}
                assert got['map'] is None and got['content_store'] == {}
            receipts.append(dict(check='isolated_generate_' + case, result=result, exit_code=code, hashes=result_hashes(got)))
        # Real API example: no site packages, unrelated cwd, explicit paths.
        cmd = [sys.executable, '-B', '-S', str(root / 'call_example.py'), '--module-zip', str(module),
               '--module-lock', str(root / 'dependencies/module-lock.json'), '--request', str(root / 'samples/success/request.json'),
               '--config', str(root / 'profiles/stable-v2.json')]
        example = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=120, check=True)
        receipts.append(dict(check='real_call_example', result=json.loads(example.stdout)))
        for mutation in ('missing_content', 'false_readiness', 'failed_map', 'rng_vector'):
            damaged = temp / ('damaged-' + mutation); shutil.copytree(root, damaged)
            if mutation == 'missing_content':
                (damaged / 'samples/success/content/M01.json').unlink(); resign(damaged)
            elif mutation == 'false_readiness':
                m = read(damaged / 'manifest.json'); m['readiness']['web_runtime'] = 'IMPLEMENTED'; write(damaged / 'manifest.json', m)
            elif mutation == 'failed_map':
                path = damaged / 'samples/failure'; r = read(path / 'result.json'); r['map'] = read(damaged / 'samples/success/map.json')
                write(path / 'result.json', r); prov = read(path / 'provenance.json'); prov['result_hashes'] = result_hashes(r); write(path / 'provenance.json', prov); resign(damaged)
            else:
                path = damaged / 'determinism/vectors.json'; vectors = read(path); vectors['streams'][0]['shuffle_22'].reverse(); write(path, vectors); resign(damaged)
            observed = run('verify', bundle=damaged, expected_code=2)
            assert observed['status'] == 'REJECTED'
            receipts.append(dict(check='reject_' + mutation, result=observed))
        wrong_module = work / 'wrong-module.zip'; wrong_module.write_bytes(module.read_bytes() + b'changed')
        observed = run('verify', module_path=wrong_module, expected_code=2)
        assert observed['status'] == 'REJECTED'
        receipts.append(dict(check='reject_unlocked_module_zip', result=observed))
        # Rebuild from exactly the source commit recorded in the actual package.
        rebuild = temp / 'rebuilt'
        cmd = [sys.executable, 'reference_package/build.py', '--module-zip', str(args.module_zip.resolve()),
               '--module-lock', 'examples/library-lock.json', '--source-commit', manifest['source']['commit'], '--out', str(rebuild)]
        rebuilt = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120, check=True)
        assert (rebuild / args.archive.name).read_bytes() == args.archive.read_bytes()
        receipts.append(dict(check='deterministic_zip_rebuild', result=json.loads(rebuilt.stdout)))
        report = dict(status='PASS', archive=args.archive.name, archive_sha256=expected, source_commit=manifest['source']['commit'],
                      runtime_target=manifest['runtime_target'], readiness=manifest['readiness'], checks=receipts,
                      isolation=dict(site_packages=False, original_repository_on_child_path=False, unrelated_cwd=True, implicit_experiment_paths=False),
                      godot_execution='NOT_RUN', web_execution='NOT_RUN')
    args.out.mkdir(parents=True); write(args.out / 'report.json', report)
    print(json.dumps(dict(status=report['status'], checks=len(receipts), source_commit=report['source_commit']), indent=2))


if __name__ == '__main__':
    main()
