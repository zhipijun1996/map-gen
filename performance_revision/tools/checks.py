"""Required native contract and repository guards; no performance assertions."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--godot',type=Path,required=True);p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--only',nargs='*');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
for script in ['foundation','numbers','integer_hypot_probe','reward_geometry','budget','performance_contract','jobs']:
 if a.only and script not in a.only:continue
 shutil.copyfile(ROOT/'godot_runtime/tests'/(script+'.gd'),a.project/'tests'/(script+'.gd'))
 cmd=[str(a.godot.resolve()),'--headless','--path',str(a.project),'--script','res://tests/'+script+'.gd','--',str((ROOT/'.cache/legacy-real-v2/modules.zip').resolve()),str((a.out/(script+'.json')).resolve())]
 start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=180);raw=r.stdout+r.stderr;(a.out/(script+'.log')).write_text(raw)
 rows.append(dict(check=script,exit_code=r.returncode,seconds=time.monotonic()-start,status='PASS' if r.returncode==0 and 'SCRIPT ERROR' not in raw else 'FAIL',argv=cmd,log_sha256=hashlib.sha256(raw.encode()).hexdigest()));print(script,rows[-1]['status'],flush=True)
for name,cmd in [('interface',['python','-m','unittest','discover','-s','tests/interface','-v']),('reference',['python','-m','unittest','discover','-s','tests/reference','-v']),('prototype',['python','prototype/verify.py']),('progress-replay',['python','tools/verify_progress.py','--replay'])]:
 if a.only and name not in a.only:continue
 env=os.environ.copy();env['MAPGEN_REFERENCE_MODULE_ZIP']=str((ROOT/'.cache/legacy-real-v2/modules.zip').resolve())
 start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=300);raw=r.stdout+r.stderr;(a.out/(name+'.log')).write_text(raw);rows.append(dict(check=name,exit_code=r.returncode,status='PASS' if r.returncode==0 else 'FAIL',seconds=time.monotonic()-start,argv=cmd,log_sha256=hashlib.sha256(raw.encode()).hexdigest()));print(name,rows[-1]['status'],flush=True)
report=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',engine_sha256=hashlib.sha256(a.godot.read_bytes()).hexdigest(),checks=rows);(a.out/'checks.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(0 if report['status']=='PASS' else 1)
