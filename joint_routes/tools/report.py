"""Report full two-ability cohorts; compare layouts only on common successes."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path
from mapgen import ModuleLibrary
from runtime_iteration.tools.metrics import stats, aggregate
from runtime_iteration.tools.module_classes import build
from branch_routes.tools.report import compact
from branch_routes.tools.setup import ROOT

def read(path):return json.loads(gzip.decompress(path.read_bytes()))['result']

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--experimental-run',default='joint-controller40');p.add_argument('--out',type=Path,default=ROOT/'joint_routes/comparisons');a=p.parse_args()
    base=ROOT/'validation/joint-reward-20261104';library=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723');classes=build(library)
    raw={k:[] for k in ('old','new','perf')};rows=[];maps=[];sources=[];kinds={k:collections.Counter() for k in ('old','new')};paired={k:[] for k in ('old','new')};counts={k:collections.Counter() for k in ('old','new')};coverage={k:collections.Counter() for k in ('old','new')}
    for seed in range(930001,930041):
        results={}
        for label,folder in [('old','baseline-controller40'),('new',a.experimental_run),('perf','perf501-controller40')]:
            path=base/folder/('seed-'+str(seed)+'.json.gz');results[label]=read(path);raw[label].append(results[label]);sources.append(dict(label=label,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        old,new,perf=results['old'],results['new'],results['perf'];sa=stats(old,classes);sb=stats(new,classes)
        row=dict(seed=seed,old_status=old['status'],new_status=new['status'],perf_status=perf['status'],old_seconds=old['metrics']['generation_seconds'],new_seconds=new['metrics']['generation_seconds'],perf_seconds=perf['metrics']['generation_seconds'],old_repairs=old['metrics']['layout_repairs'],new_repairs=new['metrics']['layout_repairs'])
        if old['status']==new['status']=='PASS':
            paired['old'].append(sa);paired['new'].append(sb)
            for label,result in [('old',old),('new',new)]:
                counts[label].update(i['module_id'] for i in result['map']['instances']);coverage[label].update({i['module_id'] for i in result['map']['instances']})
        for label,result in [('old',old),('new',new)]:
            if result['status']=='PASS':kinds[label].update(b['kind'] for b in result['diagnostics']['details']['reward_branches'])
        rows.append(row);maps.append(dict(seed=seed,old=compact(old),new=compact(new),old_stats={k:v for k,v in sa.items() if k not in ['mask','modules','pairs','signature']},new_stats={k:v for k,v in sb.items() if k not in ['mask','modules','pairs','signature']}))
    summary={}
    for label,results in raw.items():
        ts=[r['metrics']['generation_seconds'] for r in results];summary[label]=dict(statuses=dict(collections.Counter(r['status'] for r in results)),mean_all_attempt_seconds=statistics.mean(ts),median_all_attempt_seconds=statistics.median(ts),p95_all_attempt_seconds=sorted(ts)[int((len(ts)-1)*.95)],max_all_attempt_seconds=max(ts),layout_repairs=sum(r['metrics']['layout_repairs'] for r in results))
    report=dict(cases=40,context='jump/shot_recoil, clearance12.0/18.0',experimental_run=a.experimental_run,all_attempts=summary,common_successes=len(paired['old']),common_layout_metrics={k:aggregate(v) for k,v in paired.items()},all_success_branch_kinds={k:dict(v) for k,v in kinds.items()},rows=rows,sources=sources,scope='All statuses retained. Timing from diagnostic batches, not dedicated CPU trials. Layout/115-module counts compare ONLY common successful seeds; new successes displayed individually; no physics.')
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with (a.out/'all-outcomes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    module_rows=[]
    for e in library.read('catalog.json')['modules']:
        mid=e['id'];module_rows.append(dict(module_id=mid,title=e['title'],paired_success_maps=len(paired['old']),old_instances=counts['old'][mid],new_instances=counts['new'][mid],old_map_coverage=coverage['old'][mid],new_map_coverage=coverage['new'][mid]))
    with (a.out/'module-usage.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(module_rows[0]));writer.writeheader();writer.writerows(module_rows)
    html=(ROOT/'branch_routes/tools/view.html').read_text().replace('0.4.2 varied-v1 → 新奖励路线算法','0.5.0 → 奖励联合规划实验').replace('同批60 seed','同批40个两能力请求 seed').replace('0.4.2 · varied-v1','0.5.0 · 原候选').replace('新候选 · stable-v4-reward-branches','联合规划研究原型 · stable-v5').replace('同批统计','共同成功seed的布局统计')
    html=html.replace('旧图未提供同口径的支路规划记录；不据此断言旧图没有长奖励路径。','两版均显示实际支路记录；归并顺序依据各自冻结的主路径，整图物理未验证。').replace('新算法会为奖励支路增加连接模块','两版都会为奖励支路增加连接模块')
    data=dict(maps=maps,summary=dict(old=report['common_layout_metrics']['old'],new=report['common_layout_metrics']['new']))
    (a.out/'index.html').write_text(html.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')))
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','sources']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
