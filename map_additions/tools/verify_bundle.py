#!/usr/bin/env python3
"""Independent-directory integrity and real Godot replay; Python standard library only."""
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path

def normalized(r):
    v=dict(r);v.pop('metrics',None);return v

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--godot',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parent;manifest=json.loads((root/'manifest.json').read_text());checks={}
    checks['files_exact']=set(manifest['files'])=={str(f.relative_to(root)) for f in root.rglob('*') if f.is_file() and '.godot' not in f.parts and str(f.relative_to(root)) not in ['manifest.json']}
    for name,digest in manifest['files'].items():
        path=root/name;checks['sha:'+name]=path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest
    checks['runtime_count']=len(manifest['runtime_files'])==9 and all(manifest['files'].get('addons/mapgen_additions/'+n)==digest for n,digest in manifest['runtime_files'].items())
    # Source copy outside repository; Godot generated caches never mutate delivered tree.
    import shutil
    with tempfile.TemporaryDirectory(prefix='map-additions-verify-') as tmp:
        project=Path(tmp)/'project';shutil.copytree(root,project)
        for case in ['real-930001','real-930007','synthetic-shop']:
            output=Path(tmp)/(case+'.json');cmd=[str(a.godot.resolve()),'--headless','--path',str(project),'--script','res://tests/run.gd','--',str(project/'examples'/(case+'.json')),str(project/'profiles/default.json'),str(output),'1']
            if case=='synthetic-shop':cmd.append(str(project/'examples/shops.json'))
            run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60);print(case,run.stdout.strip());checks[case+':process']=run.returncode==0 and 'SCRIPT ERROR' not in run.stdout and output.exists()
            if output.exists():
                record=json.loads(output.read_text());expected=json.loads((project/'examples'/(case+'.expected.json')).read_text());checks[case+':unchanged']=record['source_unchanged'];checks[case+':replay']=normalized(record['result'])==normalized(expected)
        cmd=[str(a.godot.resolve()),'--headless','--path',str(project),'--script','res://tests/contracts.gd','--',str(project/'examples/synthetic-shop.json'),str(project/'profiles/default.json'),str(project/'examples/shops.json'),str(project/'examples/real-930001.json'),str(Path(tmp)/'contracts.json')]
        run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60);checks['contracts']=run.returncode==0 and 'SCRIPT ERROR' not in run.stdout and json.loads((Path(tmp)/'contracts.json').read_text())['status']=='PASS';print(run.stdout.strip())
    report=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,actual_engine_sha256=hashlib.sha256(a.godot.read_bytes()).hexdigest(),scope='pure-data sidecar replay and static contract checks, no main-game physics');print(json.dumps(report,indent=2));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
