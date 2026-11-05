"""Separate additions package: never modifies/rebuilds old algorithm bundles."""
import argparse,gzip,hashlib,json,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from map_additions.tools.setup import ROOT,assemble
from map_additions.tools.fixtures import fixture,shop_anchors
p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
with tempfile.TemporaryDirectory(prefix='map-additions-build-') as tmp:
 root=Path(tmp)/'mapgen-map-additions-candidate-0.1.0';assemble(root);(root/'examples').mkdir();shutil.copytree(ROOT/'map_additions/profiles',root/'profiles');shutil.copytree(ROOT/'map_additions/schemas',root/'schemas')
 for seed in [930001,930007]:
  inp=ROOT/'validation/map-additions-20261105/cohort-v7/inputs'/('seed-'+str(seed))/'result.json.gz';(root/'examples'/('real-'+str(seed)+'.json')).write_bytes(gzip.decompress(inp.read_bytes()));record=json.loads(gzip.decompress((ROOT/'validation/map-additions-20261105/cohort-v7'/('seed-'+str(seed)+'.json.gz')).read_bytes()));(root/'examples'/('real-'+str(seed)+'.expected.json')).write_text(json.dumps(record['result'],ensure_ascii=False)+'\n')
 (root/'examples/synthetic-shop.json').write_text(json.dumps(fixture())+'\n');(root/'examples/shops.json').write_text(json.dumps(shop_anchors())+'\n')
 output=Path(tmp)/'fixture-result.json';run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(root),'--script','res://tests/run.gd','--',str(root/'examples/synthetic-shop.json'),str(root/'profiles/default.json'),str(output),'1',str(root/'examples/shops.json')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60);assert run.returncode==0 and 'SCRIPT ERROR' not in run.stdout,run.stdout;(root/'examples/synthetic-shop.expected.json').write_text(json.dumps(json.loads(output.read_text())['result'])+'\n')
 # Tests/contracts includes genuine negative protocol/budget/cancellation executions.
 shutil.copytree(ROOT/'map_additions/comparison',root/'comparison')
 for name in ['README.md','CONTRACT.md','REPORT.md','DELIVERY.md']:shutil.copyfile(ROOT/'map_additions'/name,root/name)
 shutil.copyfile(ROOT/'map_additions/tools/verify_bundle.py',root/'verify_bundle.py')
 (root/'dependencies.lock.json').write_text(json.dumps({'runtime':'Godot Standard 4.7.2 (tested custom_build.gunman_sd1.ed1daf0bf)','engine_sha256':'eeaec2b65dc3234168be1e1cbcc89731514bbb78dfb2c1b502920c50830a0638','module_package':{'version':'1.1.0','sha256':'5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723','loading':'materialized source map/content_store input; no implicit module ZIP download'},'verify':'Python3 standard library; actual Godot execution','runtime_external_dependencies':[]},indent=2)+'\n')
 if (root/'.godot').exists():shutil.rmtree(root/'.godot')
 lock=json.loads((root/'source-lock.json').read_text());files={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(root.rglob('*')) if f.is_file()}
 manifest=dict(package='mapgen-map-additions-candidate',version='0.1.0',runtime_target='godot-standard-pure-gdscript',readiness='research-prototype',source_commit=source_commit,protocol='mapgen/map-additions/v1',source_protocol='mapgen/runtime-map/v2',config_protocol='mapgen/map-additions-config/v1',runtime_files=lock,files=files,core_generator='separate existing algorithm package; core identities/expectations unchanged',tested_module_lock=json.load(open(root/'dependencies.lock.json'))['module_package']);(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 path=a.out/(root.name+'.zip')
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(root.rglob('*')):
   if f.is_file():
    info=zipfile.ZipInfo(str(f.relative_to(root.parent)),date_time=(2026,11,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,f.read_bytes())
 digest=hashlib.sha256(path.read_bytes()).hexdigest();path.with_suffix('.zip.sha256').write_text(digest+'  '+path.name+'\n');receipt=dict(path=str(path.relative_to(ROOT)),sha256=digest,bytes=path.stat().st_size,source_commit=source_commit,manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),runtime_file_count=len(lock),runtime_target=manifest['runtime_target'],readiness=manifest['readiness']);(a.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
