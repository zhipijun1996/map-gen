"""Actual Godot process vs unchanged Python reference; no engine substitution."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary
from mapgen.artifacts import validate_result
from mapgen.contracts import canonical


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def semantic_map(value):
    result = copy.deepcopy(value)
    if result is not None:
        del result['map_id']
        del result['generator']['implementation']
        del result['generator']['request_fingerprint']
    return result


def compare(actual, expected, request, config, library):
    # Identity checked separately, never used to hide topology/content/count drift.
    identity = actual['request_fingerprint'] != expected['request_fingerprint']
    if actual['map'] is not None:
        m = actual['map']
        identity &= (m['generator']['implementation'] == 'mapgen/gdscript-candidate-0.3.0'
                     and m['generator']['request_fingerprint'] == actual['request_fingerprint']
                     and m['map_id'] == 'map-'+actual['request_fingerprint'][:24])
    a_metrics = {k:v for k,v in actual['metrics'].items() if k != 'generation_seconds'}
    b_metrics = {k:v for k,v in expected['metrics'].items() if k != 'generation_seconds'}
    checks = dict(identity_separately_declared=bool(identity), status=actual['status']==expected['status'],
                  layout_graph_routes_seals_anchors_inputs=semantic_map(actual['map'])==semantic_map(expected['map']),
                  complete_content_store=actual['content_store']==expected['content_store'], search_counts=a_metrics==b_metrics,
                  decisions=actual['diagnostics'].get('details',{}).get('decisions')==expected['diagnostics'].get('decisions'))
    # Reuse the independent reference semantic validator on an EXPLICIT copy
    # with only declared identity remapped. Original actual is always retained.
    projected = copy.deepcopy(actual)
    projected['request_fingerprint'] = expected['request_fingerprint']
    if projected['map'] is not None:
        projected['map']['map_id'] = expected['map']['map_id']
        projected['map']['generator'] = expected['map']['generator'].copy()
    validate_result(projected, request, config, library)
    checks['independent_semantic_validation'] = True
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module-zip', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--godot', default='godot')
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--all-40', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    cfg_dict = json.loads((ROOT/'profiles/stable-v2.json').read_text())
    cfg = GeneratorConfig.from_dict(cfg_dict)
    library = ModuleLibrary.from_zip(args.module_zip, expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
    base = json.loads((ROOT/'examples/request-930001.json').read_text())
    cases = [('success',base), ('failure',json.loads((ROOT/'reference_package/fixtures/failure/request.json').read_text()))]
    if args.all_40:
        rows = json.loads((ROOT/'experiments/optimization-v2/output/results.json').read_text())['results']
        cases = [(f'{r["cohort"]}-{r["seed"]}',dict(base,seed=r['seed'])) for r in rows if r['variant']=='stable'] + cases
    source_sha = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'godot_candidate/addons/mapgen').glob('*.gd'))}
    def run(case):
        name, req_dict = case
        folder = args.out/name
        folder.mkdir()
        (folder/'request.json').write_text(json.dumps(req_dict,ensure_ascii=False,indent=2)+'\n')
        request = GenerationRequest.from_dict(req_dict)
        # Freeze cases are read, not rewritten; 40 cases use unchanged Python API.
        expected = (json.loads((ROOT/f'reference_package/fixtures/{name}/result.json').read_text()) if name in ('success','failure')
                    else generate(request,library,cfg).to_dict())
        command = [args.godot,'--headless','--path',str(ROOT/'godot_candidate'),'--script','res://tests/generate.gd','--',str(args.module_zip.resolve()),str((folder/'request.json').resolve()),str((ROOT/'profiles/stable-v2.json').resolve()),str((folder/'actual.json').resolve()),'128']
        process = subprocess.run(command,text=True,capture_output=True,timeout=240)
        (folder/'godot.log').write_text(process.stdout+process.stderr)
        assert process.returncode==0 and 'SCRIPT ERROR' not in process.stderr, process.stdout+process.stderr
        output = json.loads((folder/'actual.json').read_text())
        checks = compare(output['result'],expected,request,cfg,library)
        checks['operation_bound'] = output['scheduling']['operation_bound_pass']
        actual = output['result']
        record = dict(case=name,seed=req_dict['seed'],status='PASS' if all(checks.values()) else 'MISMATCH',generation_status=actual['status'],checks=checks,
                      actual_identity=actual['request_fingerprint'],reference_identity=expected['request_fingerprint'],
                      semantic_map_sha256=digest(semantic_map(actual['map'])),content_store_sha256=digest(actual['content_store']),
                      scheduling=output['scheduling'],metrics=actual['metrics'])
        for filename,value in [('reference.json',expected),('actual.json',output)]:
            raw=(canonical(value)+'\n').encode()
            (folder/(filename+'.gz')).write_bytes(gzip.compress(raw,mtime=0))
        (folder/'actual.json').unlink()
        (folder/'comparison.json').write_text(json.dumps(record,indent=2)+'\n')
        print(name,record['status'],actual['status'],flush=True)
        return record
    results=[]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed([pool.submit(run,c) for c in cases]):
            results.append(future.result())
    assert source_sha == {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'godot_candidate/addons/mapgen').glob('*.gd'))}, 'component changed during replay'
    report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',cases=len(results),matching=sum(r['status']=='PASS' for r in results),source_sha256=source_sha,module_sha256=library.sha256,
                identity_encoding='GDScript full-precision typed JSON; different from Python canonical',
                results=sorted(results,key=lambda r:r['case']),whole_map_playable='NOT_RUN')
    (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
