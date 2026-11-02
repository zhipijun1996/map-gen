#!/usr/bin/env python3
"""Compare every accepted stable-v2 reference with the explicit-input core."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys

# Harness path setup only. The distributable core never changes sys.path.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary
from mapgen.contracts import canonical


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def initialize(archive, digest, request, config):
    global LIBRARY, REQUEST, CONFIG
    LIBRARY = ModuleLibrary.from_zip(archive, expected_sha256=digest)
    REQUEST = request; CONFIG = GeneratorConfig.from_dict(config)


def run_case(row, out):
    request = copy.deepcopy(REQUEST); request['seed'] = row['seed']
    actual = generate(GenerationRequest.from_dict(request), LIBRARY, CONFIG)
    folder = ROOT / 'experiments/optimization-v2/output' / row['cohort'] / 'stable' / f'seed-{row["seed"]}'
    raw = json.loads(gzip.decompress((folder / 'solver-state.json.gz').read_bytes()))
    original = json.loads(gzip.decompress((folder / 'map.json.gz').read_bytes()))
    got_raw = actual.diagnostics.get('solver_state', {}).get('instances')
    nodes = sorted({n for e in original['independent_audit']['edges'] for n in e})
    ids = {n: f'n{k:04}' for k, n in enumerate(nodes)}
    checks = dict(status=actual.status == row['status'], instances=got_raw == raw['instances'],
                  audit=actual.diagnostics.get('independent_audit') == original['independent_audit'],
                  metrics=all(actual.metrics.get(k) == v for k, v in row.items() if k in actual.metrics and k != 'generation_seconds'),
                  main_paths=actual.map is not None and actual.map['graph']['main_paths'] == [[ids[n] for n in p] for p in original['main_paths']],
                  full_content=actual.map is not None and all(actual.content_store['content/' + i['id'] + '.json'] == i['content'] for i in original['instances']))
    record = dict(cohort=row['cohort'], seed=row['seed'], status='PASS' if all(checks.values()) else 'MISMATCH', checks=checks,
                  request_fingerprint=actual.fingerprint,
                  expected_state_sha256=sha(canonical(raw['instances']).encode()), actual_state_sha256=sha(canonical(got_raw).encode()),
                  metrics=actual.metrics, error=actual.diagnostics.get('error'))
    if record['status'] != 'PASS' or row['seed'] in (271028, 930001):
        target = out / f'{row["cohort"]}-{row["seed"]}-result.json.gz'
        target.write_bytes(gzip.compress(json_bytes(actual.to_dict()), mtime=0))
    (out / f'{row["cohort"]}-{row["seed"]}.json').write_bytes(json_bytes(record))
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--library-sha256', required=True)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite a replay batch')
    args.out.mkdir(parents=True); frozen = {}
    paths = list((ROOT / 'mapgen').glob('*.py')) + list((ROOT / 'schemas').glob('*.json')) + [args.request, args.config, ROOT / 'pyproject.toml']
    for path in paths:
        rel = path.resolve().relative_to(ROOT).as_posix(); frozen[rel] = sha(path.read_bytes())
        dest = args.out / 'source' / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    original = json.loads((ROOT / 'experiments/optimization-v2/output/results.json').read_text())
    rows = [r for r in original['results'] if r['variant'] == 'stable']
    records = []; output = args.out.resolve()
    with ProcessPoolExecutor(max_workers=4, initializer=initialize,
                             initargs=(args.library.resolve(), args.library_sha256, json.loads(args.request.read_text()), json.loads(args.config.read_text()))) as pool:
        jobs = [pool.submit(run_case, r, output) for r in rows]
        for future in as_completed(jobs):
            record = future.result(); records.append(record)
            print(record['cohort'], record['seed'], record['status'], flush=True)
            for rel, expected in frozen.items():
                if sha((ROOT / rel).read_bytes()) != expected:
                    raise RuntimeError('core/input changed during replay: ' + rel)
    records.sort(key=lambda r: (r['cohort'], r['seed']))
    summary = dict(status='PASS' if all(r['status'] == 'PASS' for r in records) else 'FAIL', cases=len(records),
                   matching=sum(r['status'] == 'PASS' for r in records), source_sha256=frozen, library_sha256=args.library_sha256,
                   compared=['raw_instance_state', 'independent_audit', 'operation_and_search_counts', 'actual_main_paths', 'full_content'],
                   cases_by_cohort={c: dict(cases=sum(r['cohort'] == c for r in records), matching=sum(r['cohort'] == c and r['status'] == 'PASS' for r in records)) for c in ('calibration', 'validation')})
    (args.out / 'summary.json').write_bytes(json_bytes(summary))
    print(json.dumps(summary, indent=2))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
