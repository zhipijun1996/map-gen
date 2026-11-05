"""Matched v7/v8 outcomes, actual forks, large-module usage and selection funnel."""
import argparse,collections,csv,json,statistics,gzip
from pathlib import Path
from role_growth.tools.metrics import read,metrics
from route_construction.tools.report import source
from branch_routes.tools.report import compact
from mapgen import ModuleLibrary
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'validation/role-growth-20261105'
def avg(rows):return {k:statistics.mean(r[k] for r in rows if r[k] is not None) for k in rows[0]} if rows else {}
def main():
 p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[];maps=[];raw={};funnel=collections.defaultdict(collections.Counter);sources=[]
 for seed in list(range(930001,930041))+list(range(980001,980011)):
  old=source('v7',seed) if seed<980001 else BASE/'fresh-baseline'/f'seed-{seed}.json.gz';new=BASE/('primary40' if seed<980001 else 'fresh10')/f'seed-{seed}.json.gz'
  if not new.exists() or not old.exists():continue
  pair={side:read(path) for side,path in [('v7',old),('v8',new)]};raw[seed]=pair;entry={'seed':seed}
  for side,r in pair.items():
   row=dict(seed=seed,algorithm=side,status=r['status'],generation_seconds=r['metrics']['generation_seconds'],expansions=r['metrics']['expansions'],**metrics(r));rows.append(row);entry['old' if side=='v7' else 'new']=compact(r);entry[('old' if side=='v7' else 'new')+'_stats']=row
   if r['status']=='PASS':
    ids={i['id']:i for i in r['map']['instances']}
    for i in entry['old' if side=='v7' else 'new']['instances']:
     actual=ids[i['id']];i['large']=actual['role']=='traversal' and len(actual['ports'])<=2 and actual['size_blocks'][0]*actual['size_blocks'][1]>=24
    entry['old' if side=='v7' else 'new']['role_metrics']=metrics(r)
   if side=='v8':
    for mid,counts in r['diagnostics']['details']['growth_roles']['funnel'].items():funnel[mid].update(counts)
  maps.append(entry);sources.append(dict(seed=seed,v7=str(old.relative_to(ROOT)),v8=str(new.relative_to(ROOT))))
 summary={}
 for group,seeds in [('primary40',list(range(930001,930041))),('fresh10',list(range(980001,980011))),('all',list(raw))]:
  available=[s for s in seeds if s in raw];common=[s for s in available if all(raw[s][x]['status']=='PASS' for x in ['v7','v8'])];summary[group]=dict(cases=len(available),common_success_seeds=common)
  for side in ['v7','v8']:
   rs=[r for r in rows if r['algorithm']==side and r['seed'] in available];summary[group][side]=dict(statuses=dict(collections.Counter(r['status'] for r in rs)),all_attempt_mean_seconds=statistics.mean(r['generation_seconds'] for r in rs) if rs else None,common_quality=avg([metrics(raw[s][side]) for s in common]))
 with (a.out/'outcomes.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
 library=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723');usage=[]
 common=summary['all']['common_success_seeds'];allsteps=sorted({k for counts in funnel.values() for k in counts})
 for e in library.read('catalog.json')['modules']:
  row=dict(module_id=e['id'],title=e['title'],width=e['sizeBlocks'][0],height=e['sizeBlocks'][1],ports=len(e['ports']),eligible_two_ability_routes=sum(set(r['validation'].get('availableAbilities',[]))<={'move','jump','shot_recoil'} for r in e['routes']))
  for side in ['v7','v8']:
   counts=[sum(i['module_id']==e['id'] for i in raw[s][side]['map']['instances']) for s in common];row[side+'_instances']=sum(counts);row[side+'_seed_coverage']=sum(n>0 for n in counts)
  row.update({k:funnel[e['id']].get(k,0) for k in allsteps});usage.append(row)
 with (a.out/'module-usage-and-funnel.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(usage[0]));w.writeheader();w.writerows(usage)
 report=dict(scope='Matched settings/budgets. Frozen primary40 plus new10; no discarded failure. Forks = reachable incoming context with >=2 distinct connected non-return exits; pairs = physical connections between such instances, not physical decision proof. Timing diagnostic, different runs; no formal speed claim. Funnel includes all attempts/retries; permission/parity/space/route and growth ranking stages, no uniform sampling promise.',summary=summary,provenance=sources);(a.out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 html=(ROOT/'branch_routes/tools/view.html').read_text().replace('0.4.2 varied-v1 → 新奖励路线算法','v7 → v8 路线职责生长').replace('0.4.2 · varied-v1','v7 · 联合构造').replace('新候选 · stable-v4-reward-branches','v8 · 职责生长').replace('同批60 seed',f'同批{len(maps)} seed').replace('旧图未提供同口径的支路规划记录；不据此断言旧图没有长奖励路径。','两版严格一归并＋五多模块折返；只按共同成功图比较结构，失败保留。')
 # Viewer expects the older general-layout metric names; supply those for display.
 from runtime_iteration.tools.metrics import stats,aggregate
 from runtime_iteration.tools.module_classes import build
 classes=build(library)
 for entry in maps:
  for side,name in [('old','v7'),('new','v8')]:entry[side+'_stats']={k:v for k,v in stats(raw[entry['seed']][name],classes).items() if k not in ['mask','modules','pairs','signature']}
 basic={side:aggregate([stats(raw[s][name],classes) for s in common]) for side,name in [('old','v7'),('new','v8')]}
 html=html.replace('新算法会为奖励支路增加连接模块，因此同时列出实例数和种类；不能把新增实例数等同于多样性改善。','两版保持相同奖励构造；表格按共同成功47张图比较，全部失败样本均保留。')
 html=html.replace('if(!bounds.length)return;','if(!bounds.length){for(const side of ["old","new"]){const c=document.querySelector("#"+side);c.width=c.width;document.querySelector("#"+side+"-stat").textContent=row[side].status;}document.querySelector("#notes").textContent="两版均未输出可用地图";return;}')
 html=html.replace('c.strokeRect(x,y,w,h);c.fillStyle=', 'c.strokeRect(x,y,w,h);if(i.large){c.strokeStyle="#e43837";c.lineWidth=2.5;c.strokeRect(x+1,y+1,w-2,h-2);}c.fillStyle=')
 html=html.replace(' · 重复邻接 ${st.repeated_neighbor_pairs}', ' · 重复邻接 ${st.repeated_neighbor_pairs} · 分叉相邻 ${m.role_metrics.adjacent_fork_pairs} · 大型双口 ${m.role_metrics.large_two_port_instances}')
 notes='<p>红框为大型双口普通实例。新实验作用于普通生长；奖励构造保持v7。完整结果、真实分叉相邻数和大型双口频率见metrics.json及module-usage-and-funnel.csv。静态图不等于物理可玩。</p>'
 html=html.replace('<div id="tip">',notes+'<div id="tip">');(a.out/'index.html').write_text(html.replace('__DATA__',json.dumps(dict(maps=maps,summary=basic),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
