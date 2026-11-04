"""Frozen input replay, complete 0.4.1 comparison and independent source audit."""
import argparse,copy,gzip,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OLD=ROOT/'validation/performance-0.4.1/final/replay';INPUT=ROOT/'validation/runtime-reward-B/replay'
def norm(v,identity=True):
 v=copy.deepcopy(v);v['metrics'].pop('generation_seconds',None)
 if identity:
  v.pop('request_fingerprint');v['diagnostics'].pop('implementation',None)
  if v['map']:
   v['map'].pop('map_id');v['map']['generator'].pop('implementation');v['map']['generator'].pop('request_fingerprint')
 return v
p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);p.add_argument('--mode',choices=['default','varied','baseline'],required=True);p.add_argument('--selection',choices=['regression','calibration','unseen'],default='regression');p.add_argument('--config',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
base=json.loads((INPUT/'cases.json').read_text());cases=[]
config=a.config or ROOT/('profiles/stable-v3-varied-v1.json' if a.mode=='varied' else 'profiles/stable-v3-reward-space.json')
if a.selection=='unseen':
 template=json.loads((INPUT/'inputs/success/request.json').read_text())
 for seed in range(930021,930041):
  req=copy.deepcopy(template);req['seed']=seed;cases.append(dict(id='unseen-'+str(seed),request_data=req,config=str(config),batch=1))
else:
 for row in base:
  name=row['id']
  if a.selection=='calibration' and not name.startswith('calibration-') and name!='failure':continue
  if a.mode=='varied' and not name.startswith(('calibration-','validation-')) and name!='failure':continue
  cases.append(dict(row,request=str((INPUT/'inputs'/name/'request.json').resolve()),config=str(config),cancel_delay_usec=1))
 if a.mode=='varied' and a.selection=='regression':
  primary=next(row for row in cases if row['id']=='validation-930001')
  for batch in [17,128,4096]:cases.append(dict(primary,id='varied-batch'+str(batch),batch=batch))
  for phase in ['growth','final_audit','export']:cases.append(dict(primary,id='cancel-'+phase,cancel_phase=phase,batch=1,cancel_delay_usec=1))
# Snapshot before execution; future profile edits cannot change these runs.
for row in cases:
 folder=a.out/'inputs'/row['id'];folder.mkdir(parents=True)
 request=(json.dumps(row.pop('request_data'),indent=2)+'\n').encode() if 'request_data' in row else Path(row['request']).read_bytes()
 (folder/'request.json').write_bytes(request);(folder/'config.json').write_bytes(Path(row['config']).read_bytes())
 row.update(request=str((folder/'request.json').resolve()),config=str((folder/'config.json').resolve()),request_sha256=hashlib.sha256(request).hexdigest(),config_sha256=hashlib.sha256((folder/'config.json').read_bytes()).hexdigest())
(a.out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');shutil.copyfile(ROOT/'performance_revision/tests/regression.gd',a.project/'iteration_suite.gd')
source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.project/'addons/mapgen').glob('*.gd')}
implementation=re.search(r'const IMPLEMENTATION := "([^"]+)"',(a.project/'addons/mapgen/protocol.gd').read_text()).group(1)
with (a.out/'godot.log').open('w') as log:
 run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(a.project),'--script','res://iteration_suite.gd','--',str((ROOT/'.cache/legacy-real-v2/modules.zip').resolve()),str(a.out.resolve()),str((a.out/'cases.json').resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
assert run.returncode==0 and 'SCRIPT ERROR' not in (a.out/'godot.log').read_text()
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime_packages/tools'))
from validity import inspect_result
from mapgen import ModuleLibrary
library=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
records=[];primary=None
if a.mode=='varied' and a.selection=='regression':primary=json.loads((a.out/'validation-930001.json').read_text())['result']
for row in cases:
 path=a.out/(row['id']+'.json');record=json.loads(path.read_text());actual=record['result'];audit=None;check={'failure_empty':actual['status']=='PASS' or actual['map'] is None and actual['content_store']=={}}
 if row['id'].startswith('cancel-'):check['cancelled']=actual['status']=='CANCELLED'
 else:
  if a.mode=='default' and a.selection=='regression':
   previous=json.loads(gzip.decompress((OLD/(row['id']+'.json.gz')).read_bytes()))['result'];check['full_041_except_identity_time']=norm(actual)==norm(previous)
  if a.mode=='varied':
   check['expected_status']=actual['status']==('SEARCH_EXHAUSTED' if row['id']=='failure' else 'PASS')
   if row['id'].startswith('varied-batch'):check['batch_independent']=norm(actual,False)==norm(primary,False)
  if actual['status']=='PASS':
   assert actual['map']['generator']['implementation']==implementation
   check['real_identity']=actual['map']['generator']['request_fingerprint']==actual['request_fingerprint'] and actual['map']['map_id']=='map-'+actual['request_fingerprint'][:24]
   check['snapshot_inputs']=actual['map']['inputs']==dict(request=json.loads(Path(row['request']).read_text()),config=json.loads(Path(row['config']).read_text()))
   projected=copy.deepcopy(actual);projected['map']['generator']['implementation']='mapgen/gdscript-candidate-0.4.0';audit=inspect_result(projected,library);check['source_graph_seals_all_rewards']=audit['status']=='PASS'
  else:audit={'status':actual['status'],'usable_map':False}
 records.append(dict(case=row['id'],status=actual['status'],checks=check,metrics=actual['metrics'],audit=audit,profile=record['profile'],snapshot_usec=record['result_snapshot_usec'],cancel=record['cancel']))
 (a.out/(path.name+'.gz')).write_bytes(gzip.compress(path.read_bytes(),mtime=0));path.unlink()
report={'status':'PASS' if all(all(r['checks'].values()) for r in records) else 'FAIL','mode':a.mode,'selection':a.selection,'cases':len(cases),'source_sha256':source,'records':records,'audit_projection':'existing independent source/graph/seal/all-reward validator on identity-projected COPY; original output retained'}
(a.out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status'],a.mode,a.selection,len(cases));raise SystemExit(0 if report['status']=='PASS' else 1)
