#!/usr/bin/env python3
"""Portable Python-reference package entry. Module ZIP is always an explicit input."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parent


def check(ok, message):
    if not ok:
        raise ValueError(message)


def relative(name):
    check(isinstance(name, str) and name and '\\' not in name and '\x00' not in name, 'invalid file reference')
    p = PurePosixPath(name)
    check(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'unsafe file reference:' + name)
    return name


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def verify_files(root):
    manifest = read(root / 'manifest.json')
    check(manifest['schema'] == 'mapgen/reference-package/v1', 'unsupported artifact manifest')
    check(manifest['runtime_target'] == 'python-reference' and manifest['readiness']['godot_runtime'] == 'NOT_IMPLEMENTED', 'incorrect runtime target/readiness')
    actual = set()
    for path in root.rglob('*'):
        check(not path.is_symlink(), 'symlink in package')
        if path.is_file() and '__pycache__' not in path.parts:
            actual.add(path.relative_to(root).as_posix())
    check(actual == set(manifest['files']) | {'manifest.json'}, 'package file inventory mismatch; keep generated outputs outside the package')
    for name, expected in manifest['files'].items():
        check(hashlib.sha256((root / relative(name)).read_bytes()).hexdigest() == expected, 'file SHA mismatch:' + name)
    return manifest


def context(root, manifest, archive):
    # Bootstrap only this unpacked package, including under python -I -S.
    sys.path.insert(0, str(root))
    from mapgen import ModuleLibrary
    from mapgen.package_info import PACKAGE_VERSION, ALGORITHM_ID, IMPLEMENTATION_ID, READINESS, SCHEMAS
    check(manifest['package']['version'] == PACKAGE_VERSION and manifest['package']['algorithm'] == ALGORITHM_ID and
          manifest['package']['implementation'] == IMPLEMENTATION_ID and manifest['readiness'] == READINESS, 'package identity/readiness mismatch')
    for key in ('request', 'config', 'result', 'map'):
        check(manifest['protocol'][key]['schema'] == SCHEMAS[key], 'protocol version mismatch:' + key)
        check(relative(manifest['protocol'][key]['file']) in manifest['files'], 'missing protocol schema file:' + key)
    check(manifest['protocol']['content_schema'] == SCHEMAS['content'], 'content protocol mismatch')
    for name, info in manifest['source']['files'].items():
        check(manifest['files'][name] == info['sha256'], 'source file identity mismatch:' + name)
    lock = read(root / manifest['module_lock_ref'])
    check(manifest['files'][relative(manifest['module_zip_ref'])] == lock['sha256'], 'bundled module ZIP does not match the explicit lock')
    check(all(manifest['module_compatibility'][k] == lock[k] for k in ('version', 'sha256', 'catalog_sha256')), 'module compatibility/lock mismatch')
    library = ModuleLibrary.from_zip(archive, expected_sha256=lock['sha256'])
    check(library.version == lock['version'], 'module version mismatch')
    check(hashlib.sha256(library._files['catalog.json']).hexdigest() == lock['catalog_sha256'], 'module catalog mismatch')
    check(library.read('manifest.json')['foundation'] == manifest['module_compatibility']['foundation'], 'module Foundation mismatch')
    check(library.read('manifest.json')['schema'] == manifest['module_compatibility']['package_schema'] and
          library.read('catalog.json')['schema'] == manifest['module_compatibility']['catalog_schema'], 'module schema mismatch')
    return library


def case_data(root, item):
    from mapgen import GenerationRequest, GeneratorConfig
    path = root / relative(item['path'])
    req = GenerationRequest.from_dict(read(path / 'request.json'))
    cfg = GeneratorConfig.from_dict(read(path / 'config.json'))
    return path, req, cfg, read(path / 'result.json'), read(path / 'provenance.json')


def verify_case(root, item, library):
    from mapgen.artifacts import validate_result, input_hashes, result_hashes
    path, req, cfg, result, provenance = case_data(root, item)
    check(result['status'] == item['expected_status'], 'sample status mismatch')
    check(provenance['fingerprints'] == input_hashes(req, cfg, library), 'sample input/config fingerprint mismatch')
    check(provenance['result_hashes'] == result_hashes(result), 'sample result hash mismatch')
    check(read(path / 'module-lock.json') == read(root / 'dependencies/module-lock.json'), 'sample module lock mismatch')
    receipt = validate_result(result, req, cfg, library)
    basic = {'request.json', 'config.json', 'module-lock.json', 'result.json', 'provenance.json'}
    actual_files = {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}
    if result['status'] == 'PASS':
        check(read(path / 'map.json') == result['map'], 'map.json differs from complete result')
        check(read(path / 'content_store.json') == result['content_store'], 'content_store.json differs from complete result')
        expected = basic | {'map.json', 'content_store.json'} | set(result['content_store'])
        for name, value in result['content_store'].items():
            check(read(path / relative(name)) == value, 'unresolved or changed content_ref:' + name)
    else:
        expected = basic
    check(actual_files == expected, 'sample contains missing/extra usable output files')
    return dict(case=item['id'], **receipt)


def replay_case(root, item, library):
    from mapgen import generate
    from mapgen.artifacts import deterministic_result, validate_result, result_hashes
    _, req, cfg, expected, _ = case_data(root, item)
    got = generate(req, library, cfg).to_dict()
    validate_result(got, req, cfg, library)
    check(deterministic_result(got) == deterministic_result(expected), 'frozen sample replay differs:' + item['id'])
    check(result_hashes(got) == result_hashes(expected), 'frozen canonical result bytes differ:' + item['id'])
    return dict(case=item['id'], status='PASS', generation_status=got['status'], **result_hashes(got))


def write_generated(out, result):
    check(not out.exists(), 'refusing to overwrite output')
    out.mkdir(parents=True)
    write(out / 'result.json', result)
    if result['status'] == 'PASS':
        write(out / 'map.json', result['map']); write(out / 'content_store.json', result['content_store'])
        for name, value in result['content_store'].items():
            write(out / relative(name), value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['verify', 'replay', 'generate'])
    p.add_argument('--module-zip', type=Path, required=True)
    p.add_argument('--case', choices=['all', 'success', 'failure'], default='all')
    p.add_argument('--request', type=Path); p.add_argument('--config', type=Path); p.add_argument('--out', type=Path)
    args = p.parse_args()
    try:
        manifest = verify_files(ROOT); library = context(ROOT, manifest, args.module_zip)
        if args.command == 'generate':
            check(args.request and args.config and args.out, 'generate requires --request --config --out')
            from mapgen import generate, GenerationRequest, GeneratorConfig
            from mapgen.artifacts import validate_result
            req = GenerationRequest.from_dict(read(args.request)); cfg = GeneratorConfig.from_dict(read(args.config))
            result = generate(req, library, cfg).to_dict(); validate_result(result, req, cfg, library)
            write_generated(args.out, result)
            print(json.dumps(dict(status=result['status'], request_fingerprint=result['request_fingerprint'])))
            return 0 if result['status'] == 'PASS' else 2
        cases = [c for c in manifest['samples'] if args.case == 'all' or c['id'] == args.case]
        receipts = [verify_case(ROOT, c, library) for c in cases]
        from mapgen import GeneratorConfig
        from mapgen.reference_vectors import generate_vectors
        from mapgen.artifacts import canonical_sha256
        cfg = GeneratorConfig.from_dict(read(ROOT / 'profiles/stable-v2.json'))
        # getstate() tuples are encoded as JSON arrays in the frozen vectors.
        actual_vectors = json.loads(json.dumps(generate_vectors(cfg)))
        check(actual_vectors == read(ROOT / 'determinism/vectors.json'), 'RNG/numeric compatibility vectors differ')
        if args.command == 'replay':
            receipts = [replay_case(ROOT, c, library) for c in cases]
        print(json.dumps(dict(status='PASS', runtime_target=manifest['runtime_target'], readiness=manifest['readiness'],
                              command=args.command, samples=receipts, vectors_sha256=canonical_sha256(actual_vectors)), indent=2))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='REJECTED', error=dict(type=type(exc).__name__, message=str(exc)))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
