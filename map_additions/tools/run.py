"""Run real GDScript postprocessing on immutable frozen algorithm outputs."""
import argparse,gzip,hashlib,json,subprocess,shutil
from pathlib import Path
from map_additions.tools.setup import ROOT
from route_construction.tools.report import source,read
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);p.add_argument('--algorithm',choices=['v5','v6returns','v6merge','v7'],required=True);p.add_argument('--seeds',required=True);p.add_argument('--config',type=Path,default=ROOT/'map_additions/profiles/default.json');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    lock=json.loads((a.project/'source-lock.json').read_text());(a.out/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n');snapshot=a.out/'runtime-source';snapshot.mkdir()
    for n in lock:(snapshot/(n+'.gz')).write_bytes(gzip.compress((a.project/'addons/mapgen_additions'/n).read_bytes(),mtime=0))
    rows=[]
    for seed in map(int,a.seeds.split(',')):
        path=source(a.algorithm,seed);base=read(path);row={'seed':seed,'algorithm':a.algorithm,'base_status':base['status'],'base_source':str(path.relative_to(ROOT)),'base_archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if base['status']!='PASS':rows.append(row|{'status':'BASE_FAILED','map_additions':False});continue
        folder=a.out/'inputs'/('seed-'+str(seed));folder.mkdir(parents=True);(folder/'result.json').write_text(json.dumps(base,ensure_ascii=False)+'\n');shutil.copyfile(a.config,folder/'config.json');output=a.out/('seed-'+str(seed)+'.json')
        with (a.out/('seed-'+str(seed)+'.log')).open('w') as log:r=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(a.project.resolve()),'--script','res://tests/run.gd','--',str((folder/'result.json').resolve()),str((folder/'config.json').resolve()),str(output.resolve())],stdout=log,stderr=subprocess.STDOUT,timeout=120)
        raw=(a.out/('seed-'+str(seed)+'.log')).read_text()
        if not output.exists():rows.append(row|{'status':'MISSING_RESULT','returncode':r.returncode});continue
        record=json.loads(output.read_text());value=record['result'];checks={'process':r.returncode==0 and 'SCRIPT ERROR' not in raw,'base_unchanged':record['source_unchanged'] and value.get('validation',{}).get('base_map_unchanged',False)}
        rows.append(row|{'status':value['status'],'checks':checks,'stats':value['stats'],'profile':record['profile'],'creation_usec':record['creation_usec']})
        # Inputs already live in immutable original archives; keep a compressed local snapshot.
        for inp in folder.glob('*.json'):
            inp.with_suffix('.json.gz').write_bytes(gzip.compress(inp.read_bytes(),mtime=0));inp.unlink()
        output.with_suffix('.json.gz').write_bytes(gzip.compress(output.read_bytes(),mtime=0));output.unlink()
    result={'status':'PASS' if all(all(x.get('checks',{}).values()) and x['status'] not in ['MISSING_RESULT','INVALID_INPUT','ERROR'] for x in rows) else 'FAIL','rows':rows,'scope':'sidecar data processing; PARTIAL sign coverage is not complete feature success; no main game/physics'};(a.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['status'],[(x['seed'],x['status'],x.get('stats')) for x in rows],flush=True)
if __name__=='__main__':main()
