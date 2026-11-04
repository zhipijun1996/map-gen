"""Check actual two-ability Web outputs against corresponding native vectors."""
import gzip
import json
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.native_perf import normalized
from branch_routes.tools.audit_branches import inspect

def main():
    base=ROOT/'validation/joint-reward-20261104';checks={};rows=[]
    for folder,cohort in [('web-old','baseline-controller40'),('web-perf','perf501-controller40'),('web-joint','joint-controller40'),('web-cancel',None),('web-joint-cancel',None),('web-failure','perf501-controller-final')]:
        summary=json.loads((base/folder/'summary.json').read_text());report=json.loads(gzip.decompress((base/folder/'report.json.gz').read_bytes()));checks[folder+':browser']=not summary['errors']
        for n,row in enumerate(report['records']):
            if row['stage']=='preload':checks[folder+':preload'+str(n)]=row['status']=='PASS';continue
            result=row['result'];record={k:v for k,v in row.items() if k!='result'}|{'folder':folder,'status':result['status']}
            if cohort:
                name='failure' if folder=='web-failure' else 'seed-'+str(row['seed']);expected=json.loads(gzip.decompress((base/cohort/(name+'.json.gz')).read_bytes()))['result'];checks[folder+':native'+str(row['seed'])]=normalized(result)==normalized(expected)
                if result['status']=='PASS':record['branch_audit']=inspect(result)
                else:checks[folder+':failure_empty']=result['map'] is None and result['content_store']=={}
            else:
                c=row['cancel'];checks[folder+':trusted']=c['trusted'] and c['finished_ms']>=c['handler_ms']>=c['intent_ms'];checks[folder+':cancelled']=result['status']=='CANCELLED' and result['map'] is None and result['content_store']=={};checks[folder+':phase']=result['diagnostics']['error']['phase']=='reward_branches'
            rows.append(record)
    status='PASS' if all(checks.values()) else 'FAIL';(base/'web-audit.json').write_text(json.dumps(dict(status=status,checks=checks,records=rows,scope='actual threaded Web, two abilities; full native result except generation_seconds; DOM trusted input-to-completed-cancel latency; no main game/physics'),ensure_ascii=False,indent=2)+'\n');print(status,len(checks));assert status=='PASS'

if __name__=='__main__':main()
