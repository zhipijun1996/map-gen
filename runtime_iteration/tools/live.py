"""Replay a frozen real controller projection; does not run or alter the game."""
import copy,gzip,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/runtime-iteration-20261104/live-controller';OUT.mkdir(exist_ok=False)
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime_packages/tools'))
from validity import inspect_result
from mapgen import ModuleLibrary
# Keep the implementation/time projection local; original results stay intact.
def normalized(r):
 r=copy.deepcopy(r);r.pop('request_fingerprint');r['metrics'].pop('generation_seconds',None);r['diagnostics'].pop('implementation',None)
 if r['map']:r['map'].pop('map_id');r['map']['generator'].pop('implementation');r['map']['generator'].pop('request_fingerprint')
 return r
records=[]
for version,project in [('041','.cache/iteration-baseline041'),('042','.cache/iteration042-final')]:
 cases=[];folder=OUT/version;folder.mkdir()
 for label in ['default']+(['varied'] if version=='042' else []):
  prefix=folder/label;prefix.mkdir();shutil.copyfile(ROOT/'runtime_iteration/upstream/controller-request.json',prefix/'request.json');shutil.copyfile(ROOT/('profiles/stable-v3-varied-v1.json' if label=='varied' else 'runtime_iteration/upstream/controller-config.json'),prefix/'config.json');cases.append(dict(id=label,request=str(prefix/'request.json'),config=str(prefix/'config.json'),batch=1))
 (folder/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');shutil.copyfile(ROOT/'performance_revision/tests/regression.gd',ROOT/project/'live_suite.gd')
 with (folder/'godot.log').open('w') as log:
  run=subprocess.run([str(ROOT/'.cache/gunman-4.7.2/editor/godot-linux-x86_64'),'--headless','--path',str(ROOT/project),'--script','res://live_suite.gd','--',str(ROOT/'.cache/legacy-real-v2/modules.zip'),str(folder),str(folder/'cases.json')],stdout=log,stderr=subprocess.STDOUT,timeout=240)
 assert run.returncode==0 and 'SCRIPT ERROR' not in (folder/'godot.log').read_text()
 for case in cases:
  result=json.loads((folder/(case['id']+'.json')).read_text())['result'];records.append(dict(version=version,profile=case['id'],result=result));print(version,case['id'],result['status'],result['metrics'].get('expansions'),flush=True)
meta=json.loads((ROOT/'runtime_iteration/upstream/controller-source.json').read_text());assert records[0]['result']['request_fingerprint']==meta['request_fingerprint'];assert normalized(records[0]['result'])==normalized(records[1]['result'])
lib=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
for row in records:
 actual=row['result'];assert actual['status']=='PASS';projected=copy.deepcopy(actual);projected['map']['generator']['implementation']='mapgen/gdscript-candidate-0.4.0';row['audit']=inspect_result(projected,lib);row['fingerprint']=actual['request_fingerprint'];row['metrics']=actual['metrics'];row.pop('result')
(OUT/'summary.json').write_text(json.dumps({'status':'PASS','scope':'algorithm replay of actual frozen request only; not new host execution','old_fingerprint_reproduced':True,'default_complete_result_equal_except_identity_time':True,'records':records},indent=2)+'\n')
