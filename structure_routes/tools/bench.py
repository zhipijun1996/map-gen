"""Dedicated serial four-way timing; validate every output against its vector."""
import argparse,gzip,json,statistics,subprocess
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.native_perf import normalized
from structure_routes.tools.report import inputs

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--godot',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    counts={name:0 for name in ['v4','v5','returns','merge']};rows=[];order=['v4','v5','returns','merge','merge','returns','v5','v4']
    for name in order:
        counts[name]+=1;label=name+'-'+str(counts[name]);output=a.out/(label+'.json');project=ROOT/'.cache'/('structure-bench-'+name)
        with (a.out/(label+'.log')).open('w') as log:run=subprocess.run([str(a.godot.resolve()),'--headless','--path',str(project),'--',str(output.resolve()),'cpu','default'],stdout=log,stderr=subprocess.STDOUT,timeout=240)
        assert run.returncode==0 and 'SCRIPT ERROR' not in (a.out/(label+'.log')).read_text()
        report=json.loads(output.read_text())
        for row in report['records']:
            if row['stage']!='generate':continue
            expected=json.loads(gzip.decompress(inputs(name,row['seed']).read_bytes()))['result'];assert normalized(row['result'])==normalized(expected),(name,row['seed'])
            rows.append({k:v for k,v in row.items() if k!='result'}|{'algorithm':name,'run':label,'status':row['result']['status']})
        output.with_suffix('.json.gz').write_bytes(gzip.compress(output.read_bytes(),mtime=0));output.unlink()
    summary=dict(status='PASS',scope='dedicated serial native, no concurrent generation/browser; two repeats per seed, medians; v6 has extra hard structure goals so different workload; active=advance elapsed, not OS CPU',order=order,medians={name:{str(seed):statistics.median(r['wall_usec'] for r in rows if r['algorithm']==name and r['seed']==seed)/1e6 for seed in [930001,930007]} for name in counts},records=rows)
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary['medians']),flush=True)

if __name__=='__main__':main()
