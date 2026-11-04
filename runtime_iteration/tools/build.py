"""Reproducible 0.4.2 Godot candidate with two explicitly selected profiles."""
import argparse,gzip,hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];VERSION='0.4.2';MODULE='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);p.add_argument('--module-zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args()
commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip();files={};sources={}
def add(name,path):
 raw=path.read_bytes();rel=path.relative_to(ROOT).as_posix();assert raw==subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT),rel
 files[name]=raw;sources[name]={'repository_path':rel,'sha256':sha(raw)}
project=ROOT/'godot_runtime'
for f in sorted((project/'addons/mapgen').glob('*.gd')):add('addons/mapgen/'+f.name,f)
for f in sorted((project/'tests').iterdir()):
 if f.suffix in ('.gd','.json','.tscn'):add('tests/'+f.name,f)
for n in ['project.godot','export_presets.cfg']:add(n,project/n)
for f in sorted((ROOT/'schemas').glob('*.json')):add('schemas/'+f.name,f)
for n in ['stable-v3-reward-space.json','stable-v3-varied-v1.json']:add('profiles/'+n,ROOT/'profiles'/n)
for n in ['README.md','REPORT.md','build_derived.gd']:add(n,ROOT/'runtime_iteration'/n)
add('plans/trial-v2.json',ROOT/'runtime_iteration/plan.json')
add('plans/selected-v3.json',ROOT/'runtime_iteration/plan-v3.json')
for f in sorted((ROOT/'runtime_iteration/comparisons').iterdir()):
 if f.is_file():add('comparisons/'+f.name,f)
evidence=ROOT/'validation/runtime-iteration-20261104'
for f in sorted(evidence.rglob('*')):
 if f.is_file() and (f.name in ['summary.json','report.json','checks.json','reachability.json']):add('evidence/'+f.relative_to(evidence).as_posix(),f)
samples=[]
for folder in ['default','varied-v3']:
 for case,suffix in [('validation-930001','930001'),('validation-930007','930007'),('failure','failure')]:
  name=('default' if folder=='default' else 'varied')+'-'+suffix;prefix='samples/'+name
  # Default regression predates input snapshot helper: these are its exact old inputs.
  source=evidence/folder/'inputs'/case if folder!='default' else ROOT/'validation/runtime-reward-B/replay/inputs'/case
  add(prefix+'/request.json',source/'request.json');add(prefix+'/config.json',source/'config.json')
  result=json.loads(gzip.decompress((evidence/folder/(case+'.json.gz')).read_bytes()))['result'];files[prefix+'/result.json']=enc(result)
  if result['map'] is not None:
   files[prefix+'/map.json']=enc(result['map']);files[prefix+'/content_store.json']=enc(result['content_store'])
   for ref,body in result['content_store'].items():
    assert not Path(ref).is_absolute() and '..' not in Path(ref).parts;files[prefix+'/'+ref]=enc(body)
  samples.append(dict(id=name,request=prefix+'/request.json',config=prefix+'/config.json',result=prefix+'/result.json'))
for label in ['default','varied']:
 name='controller-'+label;prefix='samples/'+name;source=evidence/'live-controller/042'/label
 add(prefix+'/request.json',source/'request.json');add(prefix+'/config.json',source/'config.json')
 raw=evidence/'live-controller/042'/(label+'.json');raw=raw.read_bytes() if raw.exists() else gzip.decompress(raw.with_suffix('.json.gz').read_bytes())
 result=json.loads(raw)['result'];files[prefix+'/result.json']=enc(result);files[prefix+'/map.json']=enc(result['map']);files[prefix+'/content_store.json']=enc(result['content_store'])
 for ref,body in result['content_store'].items():files[prefix+'/'+ref]=enc(body)
 samples.append(dict(id=name,request=prefix+'/request.json',config=prefix+'/config.json',result=prefix+'/result.json'))
for f in sorted((ROOT/'runtime_iteration/upstream').glob('*.json')):add('upstream/'+f.name,f)
module=a.module_zip.read_bytes();assert sha(module)==MODULE;files['tests/dependencies/modules.zip']=module
manifest={'schema':'mapgen/reference-package/v1','package':{'version':VERSION,'algorithm':'stable-v3-reward-space','implementation':'mapgen/gdscript-candidate-'+VERSION},'runtime_target':'godot-standard-gdscript','readiness':{'status':'candidate','production_ready':False,'whole_map_physics':'NOT_RUN','host_integration_042':'NOT_RUN','hard_frame_budget':'NOT_GUARANTEED'},'source':{'commit':commit,'baseline_main':'b15c32e045347e0fcf282d541ea3eaa4661f0835','baseline_archive_sha256':'f5c84e5e51dff01d16429783b957c0d5214056b9d2fea47a830baac12ecedb4e','files':sources},'protocol':{'request':'mapgen/generation-request/v1','config':'mapgen/generator-config/v1','result':'mapgen/generation-result/v1','map':'mapgen/runtime-map/v2'},'module_package':{'version':'1.1.0','sha256':MODULE,'compatibility':'exact SHA; source ZIP remains required'},'profiles':{'default':{'path':'profiles/stable-v3-reward-space.json','sha256':sha(files['profiles/stable-v3-reward-space.json']),'behavior':'0.4.1 default preserved except implementation identity/time'},'varied-v1':{'path':'profiles/stable-v3-varied-v1.json','sha256':sha(files['profiles/stable-v3-varied-v1.json']),'behavior':'explicit opt-in; only scoring.repeat_module 5 to 8; no fallback profile switch'}},'seed_domain':['-9007199254740991','9007199254740991'],'addon_files':{n:sha(b) for n,b in sorted(files.items()) if n.startswith('addons/mapgen/')},'derived_cache':{'path':'addons/mapgen/derived_library.gd','schema':'mapgen/derived-library/v1','module_sha256':MODULE,'implementation':'mapgen/gdscript-candidate-'+VERSION,'contents':'only parsed source JSON; source data payload identical to 0.4.1','rebuild':'build_derived.gd; forced original JSON parsing; no generation outputs'},'samples':samples,'files':{n:sha(b) for n,b in sorted(files.items())}}
files['manifest.json']=enc(manifest);a.out.mkdir(parents=True,exist_ok=False);name='mapgen-godot-candidate-'+VERSION;dest=a.out/(name+'.zip')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,b in sorted(files.items()):
  info=zipfile.ZipInfo(name+'/'+n,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b,compresslevel=9)
with tempfile.TemporaryDirectory(prefix='mapgen042-independent-') as tmp:
 with zipfile.ZipFile(dest) as z:z.extractall(tmp)
 root=Path(tmp)/name;cmd=[str(a.godot.resolve()),'--headless','--path',str(root),'--script','res://tests/verify_bundle.gd','--',str(root/'tests/dependencies/modules.zip')]
 run=subprocess.run(cmd,cwd=tmp,text=True,capture_output=True,timeout=240);raw=run.stdout+run.stderr;(a.out/'standalone.log').write_text(raw)
 assert run.returncode==0 and 'SCRIPT ERROR' not in raw,raw
 verified=json.loads(next(s for s in reversed(raw.splitlines()) if s.startswith('{')));assert verified['status']=='PASS'
receipt=dict(status='PASS',archive=dest.name,sha256=sha(dest.read_bytes()),bytes=dest.stat().st_size,source_commit=commit,engine_sha256=sha(a.godot.read_bytes()),verify_checks=len(verified['checks']),independent_extract_verified=True,readiness=manifest['readiness'])
(a.out/(dest.name+'.sha256')).write_text(receipt['sha256']+'  '+dest.name+'\n');(a.out/'receipt.json').write_bytes(enc(receipt));print(json.dumps(receipt))
