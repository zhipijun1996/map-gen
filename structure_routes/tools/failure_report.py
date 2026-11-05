"""Expose failed finite domains and exact final attempted module/Port context."""
import collections,json,gzip
from pathlib import Path
from branch_routes.tools.setup import ROOT

def main():
    base=ROOT/'validation/structure-first-20261105';rows=[]
    for cohort in ['primary-returns','primary-merge','fresh-returns','fresh-merge']:
        for path in sorted((base/cohort).glob('seed*.json.gz')):
            result=json.loads(gzip.decompress(path.read_bytes()))['result']
            if result['status']=='PASS':continue
            d=result['diagnostics']['details'];instances=d['solver_state']['instances'];context=[]
            request=json.loads((base/cohort/'inputs'/path.name.removesuffix('.json.gz')/'request.json').read_text())
            for item in instances:
                terminal=request['terminals']['start' if item['module_id']=='START' else 'boss'] if item['module_id'] in ['START','BOSS'] else None
                context.append(dict(instance_id=item['id'],template_id=item['module_id'],module_id=item['module_id'][2:] if item['module_id'].startswith(('T:','Q:')) else terminal['module_id'],origin=item['origin'],mirror_x=item['mirror_x'],ports=[dict(solver_port_id=pid,source_port_id=terminal['port_id'] if terminal else pid,face=p['face'],surface=p['surface'],world2=p['world2'],permission=p.get('permission')) for pid,p in item['ports'].items()],port_scope='solver active ports; terminal aliases mapped, full source ports in locked catalog'))
            domains=d['structure_search']['domain_sizes']
            rows.append(dict(path=str(path.relative_to(ROOT)),status=result['status'],error=result['diagnostics']['error'],metrics=result['metrics'],plan=d['structure_plan'],failure_events=dict(collections.Counter(f['reason'] for f in d['failures'])),finite_domains=domains,empty_forward_domains=sum(x[0]==0 for x in domains) if cohort.endswith('merge') else None,final_attempted_context=context,scope='Partial debug state only, NOT a usable map. Empty bounded domain does NOT prove source library globally impossible. Context records actual modules/Port coordinates, not invented missing Routes.'))
    (base/'failure-analysis.json').write_text(json.dumps(dict(rows=rows,failures=len(rows),scope='All v6 failures in both predefined cohorts; map=null/content_store={} preserved'),ensure_ascii=False,indent=2)+'\n');print('Recorded',len(rows),'failures')

if __name__=='__main__':main()
