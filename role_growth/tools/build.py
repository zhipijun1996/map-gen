"""Freeze standalone research candidate and verify actual Godot outside repository."""
import argparse,gzip,hashlib,json,subprocess,tempfile,zipfile,shutil
from pathlib import Path
from role_growth.tools.setup import ROOT,assemble,ALGORITHM

def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
def main():
 p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 # A committed clean runtime/config is required; artifacts may be new/untracked.
 assert not subprocess.check_output(['git','diff','HEAD','--','role_growth','route_construction','structure_routes','joint_routes','branch_routes','godot_runtime/addons/mapgen'],text=True)
 with tempfile.TemporaryDirectory(prefix='mapgen-role-independent-') as tmp:
  project=Path(tmp)/'assembled';assemble(project,ROOT/'role_growth/profiles/default.json');files={}
  for folder in ['addons','schemas','tests']:
   for path in (project/folder).rglob('*'):
    if path.is_file():files[path.relative_to(project).as_posix()]=path.read_bytes()
  for name in ['project.godot','source-lock.json']:files[name]=(project/name).read_bytes()
  for name in ['README.md','REPORT.md','HANDOFF.md','PACKAGE_USAGE.md','plan.json']:files[name]=(ROOT/'role_growth'/name).read_bytes()
  for path in (ROOT/'role_growth/profiles').glob('*.json'):files['profiles/'+path.name]=path.read_bytes()
  for path in (ROOT/'role_growth/comparison').iterdir():files['comparison/'+path.name]=path.read_bytes()
  base=ROOT/'validation/role-growth-20261105'
  for name in ['selection.json','baseline-equivalence.json','jobs.json','isolation.json','web-audit.json','protected-packages.json','review.json']:files['evidence/'+name]=(base/name).read_bytes()
  files['tests/verify_bundle.gd']=(ROOT/'godot_runtime/tests/verify_bundle.gd').read_bytes().replace(b'"readiness":"candidate"',b'"readiness":"research-prototype"');files['tests/dependencies/modules.zip']=(ROOT/'.cache/legacy-real-v2/modules.zip').read_bytes()
  samples=[]
  for folder,case,label in [('primary40','seed-930001','success1'),('primary40','seed-930007','success7'),('fresh10','seed-980005','fresh-budget-failure'),('fresh10','seed-980010','fresh-search-failure'),('contracts','failure','jump-only-failure')]:
   src=base/folder;result=json.loads(gzip.decompress((src/(case+'.json.gz')).read_bytes()))['result'];prefix='samples/'+label
   assert json.load(open(src/'source-lock.json'))==json.load(open(project/'source-lock.json'))
   for name in ['request.json','config.json']:files[prefix+'/'+name]=(src/'inputs'/case/name).read_bytes()
   files[prefix+'/result.json']=enc(result)
   if result['map']:
    files[prefix+'/map.json']=enc(result['map']);files[prefix+'/content_store.json']=enc(result['content_store'])
   samples.append(dict(id=label,request=prefix+'/request.json',config=prefix+'/config.json',result=prefix+'/result.json'))
  impl=next(x.split('"')[1] for x in (project/'addons/mapgen/protocol.gd').read_text().splitlines() if x.startswith('const IMPLEMENTATION'))
  manifest=dict(schema='mapgen/reference-package/v1',package=dict(version='0.9.0-experiment',algorithm=ALGORITHM,implementation=impl),source=dict(commit=commit,assembly='role_growth/tools/setup.py'),runtime_target='godot-standard-gdscript',readiness=dict(status='research-prototype',production_ready=False,default_replacement=False,host_integration='NOT_RUN',whole_map_physics='NOT_RUN'),module_package=dict(version='1.1.0',sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723',compatibility='exact SHA'),toolchain=dict(engine_sha256=sha(a.godot.read_bytes()),engine='4.7.2.stable.custom_build.gunman_sd1.ed1daf0bf'),protocol=dict(request='mapgen/generation-request/v1',config='mapgen/generator-config/v1',result='mapgen/generation-result/v1',map='mapgen/runtime-map/v2'),addon_files={n:sha(raw) for n,raw in files.items() if n.startswith('addons/')},samples=samples,files={n:sha(raw) for n,raw in sorted(files.items())});files['manifest.json']=enc(manifest);name='mapgen-godot-experiment-0.9.0';dest=a.out/(name+'.zip')
  with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
   for rel,raw in sorted(files.items()):
    info=zipfile.ZipInfo(name+'/'+rel,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,raw,compresslevel=9)
  with zipfile.ZipFile(dest) as z:z.extractall(Path(tmp)/'external')
  package=Path(tmp)/'external'/name
  run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(package),'--script','res://tests/verify_bundle.gd','--',str(package/'tests/dependencies/modules.zip')],cwd=tmp,capture_output=True,text=True,timeout=300);log=run.stdout+run.stderr;(a.out/'standalone.log').write_text(log);assert run.returncode==0 and 'SCRIPT ERROR' not in log,log[-2000:];verified=json.loads(next(x for x in reversed(log.splitlines()) if x.startswith('{')));assert verified['status']=='PASS'
  receipt=dict(status='PASS',archive=dest.name,sha256=sha(dest.read_bytes()),manifest_sha256=sha(files['manifest.json']),source_commit=commit,implementation=impl,algorithm=ALGORITHM,addon_files=len(manifest['addon_files']),bytes=dest.stat().st_size,independent_extract_verified=True,verify_checks=len(verified['checks']),readiness=manifest['readiness']);(a.out/'receipt.json').write_bytes(enc(receipt));dest.with_suffix('.zip.sha256').write_text(receipt['sha256']+'  '+dest.name+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
