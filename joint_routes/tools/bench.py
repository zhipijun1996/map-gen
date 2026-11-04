"""Sequential old/index/joint/joint/index/old native benchmark, frozen outputs."""
import argparse
import gzip
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from branch_routes.tools.native_perf import normalized
from branch_routes.tools.setup import ROOT

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--old',type=Path,required=True);p.add_argument('--perf',type=Path,required=True);p.add_argument('--joint',type=Path,required=True);p.add_argument('--godot',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    projects={'old':a.old,'perf':a.perf,'joint':a.joint};cohorts={'old':'baseline-controller40','perf':'perf501-controller40','joint':'joint-controller40'};counts={k:0 for k in projects};rows=[]
    for label in ['old','perf','joint','joint','perf','old']:
        counts[label]+=1;name=label+'-'+str(counts[label]);output=a.out/(name+'.json')
        with (a.out/(name+'.log')).open('w') as log:
            run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(projects[label]),'--',str(output.resolve()),'cpu','default'],stdout=log,stderr=subprocess.STDOUT,timeout=240)
        assert run.returncode==0 and 'SCRIPT ERROR' not in (a.out/(name+'.log')).read_text()
        report=json.loads(output.read_text())
        for row in report['records']:
            if row['stage']!='generate':continue
            expected=json.loads(gzip.decompress((ROOT/'validation/joint-reward-20261104'/cohorts[label]/('seed-'+str(row['seed'])+'.json.gz')).read_bytes()))['result']
            assert normalized(row['result'])==normalized(expected),(label,row['seed'])
            rows.append({k:v for k,v in row.items() if k!='result'}|{'label':label,'run':name})
        output.with_suffix('.json.gz').write_bytes(gzip.compress(output.read_bytes(),mtime=0));output.unlink()
    report=dict(status='PASS',scope='Dedicated serial two-ability native host; old/perf/joint/joint/perf/old; n=2 per seed, active=advance wall durations not OS CPU',engine_sha256=hashlib.sha256(a.godot.read_bytes()).hexdigest(),source_locks={k:json.loads((v/'source-lock.json').read_text()) for k,v in projects.items()},medians={k:{str(seed):statistics.median(r['wall_usec'] for r in rows if r['label']==k and r['seed']==seed)/1e6 for seed in [930001,930007]} for k in projects},records=rows)
    (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['medians']),flush=True)

if __name__=='__main__':main()
