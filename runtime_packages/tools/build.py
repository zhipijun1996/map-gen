"""Reproducible stage-specific portable bundle; verifies actual extracted ZIP."""
import argparse,gzip,hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['A','B'],required=True);p.add_argument('--version',required=True);p.add_argument('--source-commit',required=True);p.add_argument('--module-zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip();files={};sources={}
 def add(name,path):
  raw=path.read_bytes();rel=path.relative_to(ROOT).as_posix();assert raw==subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT),rel
  files[name]=raw;sources[name]={'repository_path':rel,'sha256':sha(raw)}
 project=ROOT/'godot_runtime'
 for x in (project/'addons/mapgen').glob('*.gd'):add('addons/mapgen/'+x.name,x)
 tests=['foundation.gd','numbers.gd','integer_hypot_probe.gd','suite.gd','preload.gd','web.gd','web.tscn','verify_bundle.gd','request.json','config.json','reference-vectors.json','number-vectors.json','hypot-vectors.json']
 if a.stage=='B':tests+=['reward_geometry.gd','budget.gd']
 for n in tests:add('tests/'+n,project/'tests'/n)
 for n in ['project.godot','export_presets.cfg']:add(n,project/n)
 for x in (ROOT/'schemas').glob('*.json'):add('schemas/'+x.name,x)
 add('README.md',ROOT/'runtime_packages'/('STAGE_'+a.stage+'.md'))
 for x in (ROOT/'runtime_packages/upstream').iterdir():
  if x.is_file():add('upstream/'+x.name,x)
 evidence=ROOT/'validation'/('runtime-scheduling-A' if a.stage=='A' else 'runtime-reward-B')
 for folder in ['replay','web']:
  add('evidence/'+folder+'/summary.json',evidence/folder/'summary.json')
 add('evidence/report.json',evidence/'report.json')
 if a.stage=='B':
  add('evidence/validity.json',evidence/'validity.json')
  add('evidence/geometry.json',evidence/'geometry/report.json')
  add('evidence/budget.json',evidence/'budget/report.json')
 for name in ['success','failure']:
  folder='samples/'+name
  add(folder+'/request.json',evidence/'replay'/'inputs'/name/'request.json')
  add(folder+'/config.json',evidence/'replay'/'inputs'/name/'config.json')
  r=json.loads(gzip.decompress((evidence/'replay'/(name+'.json.gz')).read_bytes()))['result'];files[folder+'/result.json']=enc(r)
  if r['map'] is not None:
   files[folder+'/map.json']=enc(r['map']);files[folder+'/content_store.json']=enc(r['content_store'])
   for ref,body in r['content_store'].items():files[folder+'/'+ref]=enc(body)
 module=a.module_zip.read_bytes();assert sha(module)=='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723';files['tests/dependencies/modules.zip']=module
 algorithm='stable-v2' if a.stage=='A' else 'stable-v3-reward-space'
 manifest={'schema':'mapgen/reference-package/v1','package':{'version':a.version,'algorithm':algorithm,'implementation':'mapgen/gdscript-candidate-'+a.version},'stage':a.stage,'runtime_target':'godot-standard-gdscript','readiness':{'status':'candidate','production_ready':False,'whole_map_physics':'NOT_RUN','hard_frame_budget':'NOT_GUARANTEED'},'source':{'commit':commit,'files':sources},'protocol':{'request':'mapgen/generation-request/v1','config':'mapgen/generator-config/v1','result':'mapgen/generation-result/v1','map':'mapgen/runtime-map/v2'},'module_package':{'version':'1.1.0','sha256':sha(module)},'seed_domain':['-9007199254740991','9007199254740991'],'samples':[dict(id=n,request='samples/'+n+'/request.json',config='samples/'+n+'/config.json',result='samples/'+n+'/result.json') for n in ['success','failure']],'files':{n:sha(b) for n,b in sorted(files.items())}}
 files['manifest.json']=enc(manifest);a.out.mkdir(parents=True,exist_ok=False);name='mapgen-godot-candidate-'+a.version
 dest=a.out/(name+'.zip')
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(files.items()):
   i=zipfile.ZipInfo(name+'/'+n,(2026,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,b,compresslevel=9)
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(dest) as z:z.extractall(tmp)
  root=Path(tmp)/name
  r=subprocess.run(['godot','--headless','--path',str(root),'--script','res://tests/verify_bundle.gd','--',str(root/'tests/dependencies/modules.zip')],cwd=tmp,text=True,capture_output=True,timeout=240)
  (a.out/'standalone.log').write_text(r.stdout+r.stderr);assert r.returncode==0 and 'SCRIPT ERROR' not in r.stderr,r.stdout+r.stderr
 digest=sha(dest.read_bytes());(a.out/(dest.name+'.sha256')).write_text(digest+'  '+dest.name+'\n')
 receipt={'status':'PASS','stage':a.stage,'archive':dest.name,'sha256':digest,'bytes':dest.stat().st_size,'source_commit':commit,'runtime_target':'godot-standard-gdscript','readiness':manifest['readiness'],'extracted_zip_verified':True};(a.out/'receipt.json').write_bytes(enc(receipt));print(json.dumps(receipt))
if __name__=='__main__':main()
