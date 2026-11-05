"""Source-pinned standalone GDScript architecture experiment, never production."""
import argparse,gzip,json,subprocess,tempfile,zipfile
from pathlib import Path
from branch_routes.tools.setup import ROOT
from joint_routes.tools.build import enc,sha
from structure_routes.tools.setup import assemble,ALGORITHM

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source-commit',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip();checked={}
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'--','structure_routes','joint_routes','branch_routes','godot_runtime/addons/mapgen','godot_runtime/tests','schemas','performance_revision/upstream'],cwd=ROOT,text=True).splitlines()
    for rel in paths:
        raw=(ROOT/rel).read_bytes();assert subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)==raw,rel;checked[rel]=sha(raw)
    a.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='mapgen-structure-bundle-') as temp:
        project=Path(temp)/'assembled';assemble(project,ROOT/'structure_routes/profiles/returns.json');files={}
        for folder in ['addons','schemas','tests']:
            for path in (project/folder).rglob('*'):
                if path.is_file():files[path.relative_to(project).as_posix()]=path.read_bytes()
        for n in ['project.godot','source-lock.json']:files[n]=(project/n).read_bytes()
        for n in ['README.md','REPORT.md','HANDOFF.md','VERSIONS.md','versions.json','plan.json','selection.json']:files[n]=(ROOT/'structure_routes'/n).read_bytes()
        for n in ['returns','merge']:files['profiles/'+n+'.json']=(ROOT/'structure_routes/profiles'/(n+'.json')).read_bytes()
        files['tests/verify_bundle.gd']=(ROOT/'godot_runtime/tests/verify_bundle.gd').read_bytes();files['tests/dependencies/modules.zip']=(ROOT/'.cache/legacy-real-v2/modules.zip').read_bytes()
        for n in ['toolchain.json','godot_build.json']:files['dependencies/'+n]=(ROOT/'performance_revision/upstream'/n).read_bytes()
        lock=json.loads((project/'source-lock.json').read_text());samples=[]
        for folder,case,label in [('primary-returns','seed-930001','returns-success'),('primary-returns','seed-930006','returns-search-failure'),('primary-returns','seed-930036','returns-budget-failure'),('primary-merge','seed-930001','merge-success'),('contracts','failure','jump-only-failure')]:
            src=ROOT/'validation/structure-first-20261105'/folder;assert json.loads((src/'source-lock.json').read_text())==lock,folder
            result=json.loads(gzip.decompress((src/(case+'.json.gz')).read_bytes()))['result'];prefix='samples/'+label
            for n in ['request.json','config.json']:files[prefix+'/'+n]=(src/'inputs'/case/n).read_bytes()
            files[prefix+'/result.json']=enc(result)
            if result['map'] is not None:
                files[prefix+'/map.json']=enc(result['map']);files[prefix+'/content_store.json']=enc(result['content_store'])
                for ref,body in result['content_store'].items():
                    assert not Path(ref).is_absolute() and '..' not in Path(ref).parts
                    files[prefix+'/'+ref]=enc(body)
            samples.append(dict(id=label,request=prefix+'/request.json',config=prefix+'/config.json',result=prefix+'/result.json'))
        for path in (ROOT/'structure_routes/comparison').iterdir():
            if path.is_file():files['comparison/'+path.name]=path.read_bytes()
        for n in ['native-bench/summary.json','web-audit.json','reward-route-inventory.json','failure-analysis.json','contracts-api/jobs.json','contracts-api/isolation.json','contracts/summary.json','protected-packages.json']:files['evidence/'+n]=(ROOT/'validation/structure-first-20261105'/n).read_bytes()
        protocol=(project/'addons/mapgen/protocol.gd').read_text();impl=next(line.split('"')[1] for line in protocol.splitlines() if line.startswith('const IMPLEMENTATION'))
        manifest=dict(schema='mapgen/reference-package/v1',package=dict(version='0.7.0-experiment',algorithm=ALGORITHM,implementation=impl),runtime_target='godot-standard-gdscript',readiness=dict(status='research-prototype',production_ready=False,default_replacement=False,host_integration='NOT_RUN',whole_map_physics='NOT_RUN',hard_frame_budget='NOT_GUARANTEED'),source=dict(commit=commit,baseline='941c7205bcdef017ef443a7edb438c019ff7ca87',files=checked,assembly='structure_routes/tools/setup.py'),protocol=dict(request='mapgen/generation-request/v1',config='mapgen/generator-config/v1',result='mapgen/generation-result/v1',map='mapgen/runtime-map/v2'),module_package=dict(version='1.1.0',sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723',compatibility='exact SHA'),addon_files={n:sha(b) for n,b in files.items() if n.startswith('addons/')},samples=samples,files={n:sha(b) for n,b in sorted(files.items())})
        assert len(manifest['addon_files'])==25 and sha(files['tests/dependencies/modules.zip'])==manifest['module_package']['sha256']
        files['manifest.json']=enc(manifest);name='mapgen-godot-experiment-0.7.0';dest=a.out/(name+'.zip')
        with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for rel,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name+'/'+rel,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,raw,compresslevel=9)
        with zipfile.ZipFile(dest) as z:z.extractall(Path(temp)/'independent')
        package=Path(temp)/'independent'/name
        run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(package),'--script','res://tests/verify_bundle.gd','--',str(package/'tests/dependencies/modules.zip')],cwd=temp,capture_output=True,text=True,timeout=300)
        raw=run.stdout+run.stderr;(a.out/'standalone.log').write_text(raw);assert run.returncode==0 and 'SCRIPT ERROR' not in raw,raw[-2500:]
        verified=json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith('{')));assert verified['status']=='PASS'
        sample=samples[0];output=Path(temp)/'cli-result.json'
        run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(package),'--script','res://tests/generate.gd','--',str(package/'tests/dependencies/modules.zip'),str(package/sample['request']),str(package/sample['config']),str(output)],cwd=temp,capture_output=True,text=True,timeout=120)
        (a.out/'standalone-cli.log').write_text(run.stdout+run.stderr);assert run.returncode==0 and 'SCRIPT ERROR' not in run.stdout+run.stderr
        actual=json.loads(output.read_text());expected=json.loads((package/sample['result']).read_text());actual['metrics'].pop('generation_seconds',None);expected['metrics'].pop('generation_seconds',None);assert actual==expected
        receipt=dict(status='PASS',archive=dest.name,sha256=sha(dest.read_bytes()),source_commit=commit,implementation=impl,algorithm=ALGORITHM,addon_files=25,bytes=dest.stat().st_size,independent_extract_verified=True,standalone_cli_replay=True,verify_checks=len(verified['checks']),engine_sha256=sha(a.godot.read_bytes()),readiness=manifest['readiness'])
        (a.out/'receipt.json').write_bytes(enc(receipt));(a.out/(dest.name+'.sha256')).write_text(receipt['sha256']+'  '+dest.name+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
