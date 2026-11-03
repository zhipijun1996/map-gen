#!/usr/bin/env python3
"""Freeze real API samples without altering defaults, module data or old evidence."""
import argparse
import copy
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary
from mapgen.artifacts import validate_result, input_hashes, result_hashes, deterministic_result
from mapgen.reference_vectors import generate_vectors


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module-zip', type=Path, required=True); p.add_argument('--module-lock', type=Path, required=True)
    p.add_argument('--request', type=Path, required=True); p.add_argument('--config', type=Path, required=True)
    p.add_argument('--baseline-result', type=Path, required=True); p.add_argument('--base-commit', required=True)
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite frozen fixtures')
    lock = json.loads(args.module_lock.read_text()); library = ModuleLibrary.from_zip(args.module_zip, expected_sha256=lock['sha256'])
    config_data = json.loads(args.config.read_text()); config = GeneratorConfig.from_dict(config_data)
    request_data = json.loads(args.request.read_text())
    # Verify the source of the actual algorithm separately from newly added tooling.
    original_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', args.base_commit, 'mapgen'], cwd=ROOT, text=True).splitlines()
    algorithm_sources = {}
    for rel in original_paths:
        if rel.endswith('.py'):
            expected = subprocess.check_output(['git', 'show', args.base_commit + ':' + rel], cwd=ROOT)
            if expected != (ROOT / rel).read_bytes():
                raise ValueError('algorithm baseline changed:' + rel)
            algorithm_sources[rel] = hashlib.sha256(expected).hexdigest()
    for rel, supplied in [('examples/request-930001.json', args.request), ('profiles/stable-v2.json', args.config)]:
        if subprocess.check_output(['git', 'show', args.base_commit + ':' + rel], cwd=ROOT) != supplied.read_bytes():
            raise ValueError('default request/config changed:' + rel)
    baseline_bytes = args.baseline_result.read_bytes()
    baseline = json.loads(gzip.decompress(baseline_bytes) if args.baseline_result.suffix == '.gz' else baseline_bytes)
    args.out.mkdir(parents=True)
    observations = []
    for name in ('success', 'failure'):
        req_data = copy.deepcopy(request_data)
        if name == 'failure':
            req_data['player']['abilities'] = ['jump']
        request = GenerationRequest.from_dict(req_data)
        result = generate(request, library, config).to_dict()
        expected_status = 'PASS' if name == 'success' else 'SEARCH_EXHAUSTED'
        if result['status'] != expected_status:
            write(args.out / name / 'unexpected-result.json', result)
            raise ValueError('preserved unexpected sample status:' + name + ':' + result['status'])
        validation = validate_result(result, request, config, library)
        if name == 'success' and (deterministic_result(result) != deterministic_result(baseline) or result_hashes(result) != result_hashes(baseline)):
            write(args.out / name / 'unexpected-result.json', result)
            raise ValueError('success differs from frozen interface baseline')
        folder = args.out / name
        write(folder / 'request.json', req_data); write(folder / 'config.json', config_data)
        write(folder / 'module-lock.json', lock); write(folder / 'result.json', result)
        if result['status'] == 'PASS':
            write(folder / 'map.json', result['map']); write(folder / 'content_store.json', result['content_store'])
            for ref, content in result['content_store'].items():
                write(folder / ref, content)
        provenance = dict(algorithm_source_commit=args.base_commit, algorithm_source_sha256=algorithm_sources,
                          fingerprints=input_hashes(request, config, library), result_hashes=result_hashes(result),
                          source_baseline_result_sha256=hashlib.sha256(baseline_bytes).hexdigest() if name == 'success' else None,
                          request_difference={} if name == 'success' else {'player.abilities': {'default': request_data['player']['abilities'], 'sample': ['jump']}},
                          meaning='Unchanged default success' if name == 'success' else 'Valid jump-only request has no compatible declared growth route in this real package; bounded search failure is not physical impossibility.',
                          validation=validation)
        write(folder / 'provenance.json', provenance)
        observations.append(dict(id=name, expected_status=expected_status, path='samples/' + name))
    write(args.out / 'samples.json', observations)
    write(args.out / 'vectors.json', generate_vectors(config))
    try:
        schema_version = importlib.metadata.version('jsonschema')
    except importlib.metadata.PackageNotFoundError:
        schema_version = None
    write(args.out / 'python-lock.json', dict(runtime_target='python-reference', minimum_python='3.10',
          tested_runtime=dict(implementation=platform.python_implementation(), version=platform.python_version(), platform=sys.platform),
          runtime_dependencies=[], optional_schema_validation=dict(package='jsonschema', tested_version=schema_version),
          engine_dependencies=[], note='No Python interpreter or Godot runtime is bundled. Replays on other runtimes must be checked, not assumed.'))
    print(json.dumps(dict(status='PASS', samples=observations), indent=2))


if __name__ == '__main__':
    main()
