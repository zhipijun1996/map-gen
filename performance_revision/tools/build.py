"""Build a pinned, independently runnable Godot performance candidate, never latest."""
import argparse,gzip,hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MODULE='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(obj):return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);p.add_argument('--module-zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args()
commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip();files={};sources={}
def add(name,path):
 raw=path.read_bytes();rel=path.relative_to(ROOT).as_posix()
 assert raw==subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT),rel
 files[name]=raw;sources[name]={'repository_path':rel,'sha256':sha(raw)}
project=ROOT/'godot_runtime'
for f in sorted((project/'addons/mapgen').glob('*.gd')):add('addons/mapgen/'+f.name,f)
for f in sorted((project/'tests').iterdir()):
 if f.suffix in ('.gd','.json','.tscn'):add('tests/'+f.name,f)
for name in ['project.godot','export_presets.cfg']:add(name,project/name)
for f in sorted((ROOT/'schemas').glob('*.json')):add('schemas/'+f.name,f)
for src,dst in [('README.md','README.md'),('REPORT.md','REPORT.md'),('build_derived.gd','build_derived.gd')]:add(dst,ROOT/'performance_revision'/src)
for f in sorted((ROOT/'performance_revision/upstream').iterdir()):
 if f.is_file():add('upstream/'+f.name,f)
evidence=ROOT/'validation/performance-0.4.1'
for f in sorted(evidence.rglob('*')):
 if f.is_file() and (f.name=='summary.json' or f.name in ['report.json','geometry.json','budget.json','checks.json','cache_rebuild.json']):add('evidence/'+f.relative_to(evidence).as_posix(),f)
replay=evidence/'final/replay'
for case,name in [('success','success'),('validation-930007','gears-930007'),('failure','failure')]:
 folder='samples/'+name
 add(folder+'/request.json',ROOT/'validation/runtime-reward-B/replay/inputs'/case/'request.json')
 add(folder+'/config.json',ROOT/'validation/runtime-reward-B/replay/inputs'/case/'config.json')
 record=json.loads(gzip.decompress((replay/(case+'.json.gz')).read_bytes()));result=record['result'];files[folder+'/result.json']=enc(result)
 if result['map'] is not None:
  files[folder+'/map.json']=enc(result['map']);files[folder+'/content_store.json']=enc(result['content_store'])
  for ref,body in result['content_store'].items():
   assert not Path(ref).is_absolute() and '..' not in Path(ref).parts
   files[folder+'/'+ref]=enc(body)
module=a.module_zip.read_bytes();assert sha(module)==MODULE;files['tests/dependencies/modules.zip']=module
manifest={'schema':'mapgen/reference-package/v1','package':{'version':'0.4.1','algorithm':'stable-v3-reward-space','implementation':'mapgen/gdscript-candidate-0.4.1'},'revision_kind':'performance; stable-v3 semantics unchanged','runtime_target':'godot-standard-gdscript','readiness':{'status':'candidate','production_ready':False,'whole_map_physics':'NOT_RUN','host_default_double_fresh_300_seconds':'NOT_RUN','hard_frame_budget':'NOT_GUARANTEED'},'source':{'commit':commit,'baseline_release':'6bf07ab5a655ea056461b935ae4354e15ef83482','baseline_source':'b21c889077ec97eb11a210d0ceab4fbddd862e48','files':sources},'protocol':{'request':'mapgen/generation-request/v1','config':'mapgen/generator-config/v1','result':'mapgen/generation-result/v1','map':'mapgen/runtime-map/v2'},'module_package':{'version':'1.1.0','sha256':MODULE,'compatibility':'exact SHA; source ZIP required even with derived data'},'seed_domain':['-9007199254740991','9007199254740991'],'derived_cache':{'path':'addons/mapgen/derived_library.gd','schema':'mapgen/derived-library/v1','module_sha256':MODULE,'implementation':'mapgen/gdscript-candidate-0.4.1','contents':'only parsed source JSON, integer types and binary64 bits preserved','rebuild':'build_derived.gd with original ZIP, PreloadJob allow_derived=false','integrity':'full ZIP SHA and all 657 manifest members freshly checked; cache optional; original JSON fallback'},'addon_files':{n:sha(b) for n,b in sorted(files.items()) if n.startswith('addons/mapgen/')},'samples':[dict(id=n,request='samples/'+n+'/request.json',config='samples/'+n+'/config.json',result='samples/'+n+'/result.json') for n in ['success','gears-930007','failure']],'files':{n:sha(b) for n,b in sorted(files.items())}}
files['manifest.json']=enc(manifest);a.out.mkdir(parents=True,exist_ok=False);name='mapgen-godot-candidate-0.4.1';dest=a.out/(name+'.zip')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n,b in sorted(files.items()):
  info=zipfile.ZipInfo(name+'/'+n,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b,compresslevel=9)
with tempfile.TemporaryDirectory(prefix='mapgen041-independent-') as tmp:
 with zipfile.ZipFile(dest) as z:z.extractall(tmp)
 root=Path(tmp)/name
 r=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(root),'--script','res://tests/verify_bundle.gd','--',str(root/'tests/dependencies/modules.zip')],cwd=tmp,text=True,capture_output=True,timeout=240)
 (a.out/'standalone.log').write_text(r.stdout+r.stderr);assert r.returncode==0 and 'SCRIPT ERROR' not in r.stdout+r.stderr,r.stdout+r.stderr
 receipt={'status':'PASS','archive':dest.name,'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,'source_commit':commit,'engine_sha256':sha(a.godot.read_bytes()),'extracted_zip_verified':True,'independent_directory':True,'readiness':manifest['readiness']}
(a.out/(dest.name+'.sha256')).write_text(receipt['sha256']+'  '+dest.name+'\n');(a.out/'receipt.json').write_bytes(enc(receipt));print(json.dumps(receipt))
