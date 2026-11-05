"""Audit actual Web maps/cancellation; never equate a timeout with native replay."""
import gzip,json
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.native_perf import normalized
from branch_routes.tools.audit_branches import inspect as branch_audit
from structure_routes.tools.audit import inspect as structure_audit
from structure_routes.tools.report import inputs

def main():
    base=ROOT/'validation/structure-first-20261105';checks={};rows=[];full=0;aborted=[]
    for folder,mode in [('web-returns','returns'),('web-merge','merge'),('web-cancel-motif',None),('web-cancel-domain',None),('web-failure','failure')]:
        summary=json.loads((base/folder/'summary.json').read_text());report=json.loads(gzip.decompress((base/folder/'report.json.gz').read_bytes()));checks[folder+':browser']=not summary['errors']
        for index,row in enumerate(report['records']):
            if row['stage']=='preload':checks[folder+':preload'+str(index)]=row['status']=='PASS';continue
            r=row['result'];data={k:v for k,v in row.items() if k!='result'}|{'folder':folder,'status':r['status']}
            if mode:
                path=base/'contracts/failure.json.gz' if mode=='failure' else inputs(mode,row['seed']);expected=json.loads(gzip.decompress(path.read_bytes()))['result']
                if r['status']=='PASS' or r['status']==expected['status']:
                    checks[folder+':native'+str(row['seed'])]=normalized(r)==normalized(expected);full+=1
                    if r['status']=='PASS':
                        checks[folder+':branches'+str(row['seed'])]=branch_audit(r)['status']=='PASS';checks[folder+':structure'+str(row['seed'])]=structure_audit(r)['status']=='PASS'
                else:
                    aborted.append({'folder':folder,'seed':row['seed'],'status':r['status'],'native_status':expected['status']})
                    checks[folder+':explicit_wall_budget'+str(row['seed'])]=r['status']=='BUDGET_EXHAUSTED' and r['diagnostics']['error']['message']=='wall_clock_budget'
                if r['status']!='PASS':checks[folder+':empty'+str(index)]=r['map'] is None and r['content_store']=={}
            else:
                c=row['cancel'];checks[folder+':trusted']=c['trusted'] and c['finished_ms']>=c['handler_ms']>=c['intent_ms'];checks[folder+':empty']=r['status']=='CANCELLED' and r['map'] is None and r['content_store']=={}
                data['cancel_result_phase']=r['diagnostics']['error']['phase']
                checks[folder+':phase']=data['cancel_result_phase']==('motif_catalog' if folder=='web-cancel-motif' else 'structure_domains')
            rows.append(data)
    status='PASS' if all(checks.values()) else 'FAIL'
    result=dict(status=status,checks=checks,full_native_replays=full,web_aborted_before_native_result=aborted,records=rows,scope='actual threaded Web, advance(1), locked Godot4.7.2, two abilities; input-to-completed-cancel includes trusted DOM queue; no main game/physics; budget-aborted maps are not native replay passes')
    (base/'web-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(status,'full_native_replays',full,'aborted',aborted);assert status=='PASS'

if __name__=='__main__':main()
