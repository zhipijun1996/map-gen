"""Build standalone, source-pinned performance candidate or research prototype."""
import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from branch_routes.tools.setup import ROOT

def enc(v): return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def sha(v): return hashlib.sha256(v).hexdigest()

def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--kind',choices=['performance','research'],required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--godot',type=Path,required=True)
    a=p.parse_args();research=a.kind=='research'
    if research:
        from joint_routes.tools.setup import assemble
    else:
        from joint_routes.tools.setup_perf import assemble
    commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip()
    version='0.6.0-experiment' if research else '0.5.1'
    name='mapgen-godot-'+('experiment-' if research else 'candidate-')+version
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'--','joint_routes','branch_routes','godot_runtime/addons/mapgen','godot_runtime/tests','schemas','performance_revision/upstream'],cwd=ROOT,text=True).splitlines()
    checked={}
    for rel in paths:
        raw=(ROOT/rel).read_bytes()
        assert subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)==raw,rel
        checked[rel]=sha(raw)
    a.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='mapgen-joint-package-') as temp:
        project=Path(temp)/'assembled';assemble(project);files={}
        for folder in ['addons','schemas','tests']:
            for path in (project/folder).rglob('*'):
                if path.is_file():files[path.relative_to(project).as_posix()]=path.read_bytes()
        for n in ['project.godot','source-lock.json']:files[n]=(project/n).read_bytes()
        for n in ['README.md','REPORT.md','HANDOFF.md','plan.json','selection.json']:files[n]=(ROOT/'joint_routes'/n).read_bytes()
        profile=ROOT/('joint_routes/profiles/joint-v1.json' if research else 'branch_routes/profiles/stable-v4-reward-branches.json')
        files['profiles/config.json']=profile.read_bytes()
        files['tests/verify_bundle.gd']=(ROOT/'godot_runtime/tests/verify_bundle.gd').read_bytes()
        files['tests/dependencies/modules.zip']=(ROOT/'.cache/legacy-real-v2/modules.zip').read_bytes()
        for n in ['toolchain.json','godot_build.json']:files['dependencies/'+n]=(ROOT/'performance_revision/upstream'/n).read_bytes()
        source_lock=json.loads((project/'source-lock.json').read_text());samples=[]
        cases=[('joint-controller40','seed-930001'),('joint-controller40','seed-930005'),('joint-fresh20','seed-950001'),('joint-contracts','failure')] if research else [('perf501-controller40','seed-930001'),('perf501-controller40','seed-930007'),('perf501-controller40','seed-930005'),('perf501-controller-final','failure')]
        for folder,case in cases:
            src=ROOT/'validation/joint-reward-20261104'/folder
            assert json.loads((src/'source-lock.json').read_text())==source_lock,(folder,'source mismatch')
            prefix='samples/'+case;result=json.loads(gzip.decompress((src/(case+'.json.gz')).read_bytes()))['result']
            for n in ['request.json','config.json']:files[prefix+'/'+n]=(src/'inputs'/case/n).read_bytes()
            files[prefix+'/result.json']=enc(result)
            if result['map'] is not None:
                files[prefix+'/map.json']=enc(result['map']);files[prefix+'/content_store.json']=enc(result['content_store'])
                for ref,body in result['content_store'].items():
                    assert not Path(ref).is_absolute() and '..' not in Path(ref).parts
                    files[prefix+'/'+ref]=enc(body)
            samples.append(dict(id=case,request=prefix+'/request.json',config=prefix+'/config.json',result=prefix+'/result.json'))
        for n in ['metrics.json','all-outcomes.csv','module-usage.csv']:files['comparison/'+n]=(ROOT/'joint_routes/comparison-v7'/n).read_bytes()
        for n in ['web-audit.json','native-paired/summary.json']:files['evidence/'+n]=(ROOT/'validation/joint-reward-20261104'/n).read_bytes()
        protocol=(project/'addons/mapgen/protocol.gd').read_text()
        implementation=next(line.split('"')[1] for line in protocol.splitlines() if line.startswith('const IMPLEMENTATION'))
        algorithm='stable-v5-joint-reward-plans' if research else 'stable-v4-reward-branches'
        manifest=dict(schema='mapgen/reference-package/v1',package=dict(version=version,algorithm=algorithm,implementation=implementation),runtime_target='godot-standard-gdscript',readiness=dict(status='research-prototype' if research else 'candidate',production_ready=False,whole_map_physics='NOT_RUN',host_integration='NOT_RUN',hard_frame_budget='NOT_GUARANTEED',default_replacement=False),source=dict(commit=commit,baseline='47e661f9f6049d8fb701007c6af85efe2ead1e03',files=checked,assembly='joint_routes/tools/setup.py' if research else 'joint_routes/tools/setup_perf.py'),protocol=dict(request='mapgen/generation-request/v1',config='mapgen/generator-config/v1',result='mapgen/generation-result/v1',map='mapgen/runtime-map/v2'),module_package=dict(version='1.1.0',sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723',compatibility='exact SHA'),addon_files={n:sha(b) for n,b in files.items() if n.startswith('addons/')},samples=samples,files={n:sha(b) for n,b in sorted(files.items())})
        assert len(manifest['addon_files'])==(22 if research else 20)
        assert sha(files['tests/dependencies/modules.zip'])==manifest['module_package']['sha256']
        files['manifest.json']=enc(manifest);dest=a.out/(name+'.zip')
        with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for rel,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name+'/'+rel,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,raw,compresslevel=9)
        with zipfile.ZipFile(dest) as archive:archive.extractall(Path(temp)/'independent')
        package=Path(temp)/'independent'/name
        run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(package),'--script','res://tests/verify_bundle.gd','--',str(package/'tests/dependencies/modules.zip')],cwd=temp,capture_output=True,text=True,timeout=300)
        raw=run.stdout+run.stderr;(a.out/'standalone.log').write_text(raw)
        assert run.returncode==0 and 'SCRIPT ERROR' not in raw,raw[-2500:]
        verified=json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith('{')));assert verified['status']=='PASS'
        sample=samples[0];output=Path(temp)/'cli.json'
        run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(package),'--script','res://tests/generate.gd','--',str(package/'tests/dependencies/modules.zip'),str(package/sample['request']),str(package/sample['config']),str(output)],cwd=temp,capture_output=True,text=True,timeout=120)
        (a.out/'standalone-cli.log').write_text(run.stdout+run.stderr);assert run.returncode==0 and 'SCRIPT ERROR' not in run.stdout+run.stderr
        actual=json.loads(output.read_text());expected=json.loads((package/sample['result']).read_text())
        actual['metrics'].pop('generation_seconds',None);expected['metrics'].pop('generation_seconds',None);assert actual==expected
        receipt=dict(status='PASS',archive=dest.name,sha256=sha(dest.read_bytes()),source_commit=commit,implementation=implementation,algorithm=algorithm,addon_files=len(manifest['addon_files']),bytes=dest.stat().st_size,independent_extract_verified=True,standalone_cli_replay=True,verify_checks=len(verified['checks']),engine_sha256=sha(a.godot.read_bytes()),readiness=manifest['readiness'])
        (a.out/'receipt.json').write_bytes(enc(receipt));(a.out/(dest.name+'.sha256')).write_text(receipt['sha256']+'  '+dest.name+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
