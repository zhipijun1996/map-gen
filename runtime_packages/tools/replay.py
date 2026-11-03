"""Development driver: actual Godot, immutable 0.3.0 oracle, distinct stage evidence."""
import argparse,copy,gzip,hashlib,json,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'validation/godot-candidate-0.3.0/replay-precision'
def normalized(r):
 r=copy.deepcopy(r);r.pop('request_fingerprint');r['metrics'].pop('generation_seconds',None);r['diagnostics'].pop('implementation',None)
 if r['map']:
  r['map'].pop('map_id');r['map']['generator'].pop('request_fingerprint');r['map']['generator'].pop('implementation')
 return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['A','B'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--module-zip',type=Path,required=True);p.add_argument('--quick',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 cfg=ROOT/'profiles'/('stable-v2.json' if a.stage=='A' else 'stable-v3-reward-space.json')
 names=['success','failure'] if a.quick else [x.name for x in sorted(OLD.iterdir()) if x.is_dir()]
 cases=[dict(id=n,request=str(OLD/n/'request.json'),config=str(cfg),batch=1) for n in names]
 cases += [dict(id='success-batch17',request=str(OLD/'success/request.json'),config=str(cfg),batch=17),dict(id='success-batch128',request=str(OLD/'success/request.json'),config=str(cfg),batch=128)]
 cases += [dict(id='cancel-'+phase,request=str(OLD/'success/request.json'),config=str(cfg),batch=1,cancel_phase=phase) for phase in ['growth','final_audit','export']]
 for row in cases:
  folder=a.out/'inputs'/row['id'];folder.mkdir(parents=True)
  for key in ['request','config']:
   src=Path(row[key]);dst=folder/(key+'.json');shutil.copyfile(src,dst);row[key]=str(dst.resolve())
 (a.out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
 source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'godot_runtime/addons/mapgen').glob('*.gd')}
 with (a.out/'godot.log').open('w') as log:
  r=subprocess.run(['godot','--headless','--path',str(ROOT/'godot_runtime'),'--script','res://tests/suite.gd','--',str(a.module_zip.resolve()),str(a.out.resolve()),str((a.out/'cases.json').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 assert r.returncode==0,(a.out/'godot.log').read_text()[-2000:]
 assert 'SCRIPT ERROR' not in (a.out/'godot.log').read_text()
 records=[];outputs={}
 for row in cases:
  f=a.out/(row['id']+'.json');out=json.loads(f.read_text());result=out['result'];outputs[row['id']]=result
  if row['id'].startswith('cancel-'):
   checks={'cancelled':result['status']=='CANCELLED','no_map':result['map'] is None and result['content_store']=={},'input_latency_measured':out['cancel']['latency_usec'] is not None and out['cancel']['latency_usec']>=0}
  else:
   name='success' if row['id'].startswith('success-batch') else row['id'];old=json.loads(gzip.decompress((OLD/name/'actual.json.gz').read_bytes()))['result']
   checks={'identity_separate':result['request_fingerprint']!=old['request_fingerprint']}
   if a.stage=='A':checks['entire_result_except_identity_and_time']=normalized(result)==normalized(old)
   else:checks['protocol_failure_has_no_map']=result['status']=='PASS' or result['map'] is None and result['content_store']=={}
  record=dict(case=row['id'],status=result['status'],checks=checks,metrics=result['metrics'],profile=out['profile'],result_snapshot_usec=out['result_snapshot_usec'],cancel=out['cancel']);records.append(record)
  (a.out/(row['id']+'.json.gz')).write_bytes(gzip.compress(f.read_bytes(),mtime=0));f.unlink()
 baseline=outputs['success'];batch_checks={n:normalized(outputs[n])==normalized(baseline) for n in ['success-batch17','success-batch128']}
 assert source=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'godot_runtime/addons/mapgen').glob('*.gd')},'core changed during replay'
 report=dict(stage=a.stage,status='PASS' if all(all(r['checks'].values()) for r in records) and all(batch_checks.values()) else 'FAIL',cases=len(records),original_seed_and_frozen_cases=len(names),records=records,batch_checks=batch_checks,source_sha256=source,target='advance(1) p99 <= 4000us and max <= 8000us on test machine; observed limits, not time guarantee')
 (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(records))
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
