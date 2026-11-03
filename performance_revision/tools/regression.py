import argparse,copy,gzip,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'validation/runtime-reward-B/replay'
def norm(v):
 v=copy.deepcopy(v);v.pop('request_fingerprint');v['metrics'].pop('generation_seconds',None);v['diagnostics'].pop('implementation',None)
 if v['map']:
  v['map'].pop('map_id');v['map']['generator'].pop('implementation');v['map']['generator'].pop('request_fingerprint')
 return v
p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
cases=json.loads((OLD/'cases.json').read_text());cases=[dict(row,request=str((OLD/'inputs'/row['id']/'request.json').resolve()),config=str((OLD/'inputs'/row['id']/'config.json').resolve()),cancel_delay_usec=1) for row in cases]
(a.out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');shutil.copyfile(ROOT/'performance_revision/tests/regression.gd',a.project/'regression.gd')
source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.project/'addons/mapgen').glob('*.gd')}
with (a.out/'godot.log').open('w') as out:
 r=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(a.project),'--script','res://regression.gd','--',str((ROOT/'.cache/legacy-real-v2/modules.zip').resolve()),str(a.out.resolve()),str((a.out/'cases.json').resolve())],stdout=out,stderr=subprocess.STDOUT,timeout=1200)
assert r.returncode==0 and 'SCRIPT ERROR' not in (a.out/'godot.log').read_text(),(a.out/'godot.log').read_text()[-2000:]
records=[]
for row in cases:
 name=row['id'];f=a.out/(name+'.json');v=json.loads(f.read_text());actual=v['result'];old=json.loads(gzip.decompress((OLD/(name+'.json.gz')).read_bytes()))['result']
 checks={'empty_failure':actual['status']=='PASS' or actual['map'] is None and actual['content_store']=={}}
 if name.startswith('cancel-'):checks['cancelled']=actual['status']=='CANCELLED'
 else:checks.update(entire_result_except_declared_identity_time=norm(actual)==norm(old),identity_separate=actual['request_fingerprint']!=old['request_fingerprint'])
 records.append(dict(case=name,status=actual['status'],checks=checks,metrics=actual['metrics'],profile=v['profile'],result_snapshot_usec=v['result_snapshot_usec'],cancel=v['cancel']))
 (a.out/(name+'.json.gz')).write_bytes(gzip.compress(f.read_bytes(),mtime=0));f.unlink()
report=dict(status='PASS' if all(all(x['checks'].values()) for x in records) else 'FAIL',cases=len(records),source_sha256=source,records=records,expected='unchanged original 0.4.0 complete results',projection='only root fingerprint, generator implementation/fingerprint, map_id, diagnostics implementation, generation_seconds')
(a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(records));raise SystemExit(0 if report['status']=='PASS' else 1)
