"""Compare all outcomes and only paired successful layouts across algorithms."""
import argparse,collections,csv,gzip,hashlib,json,statistics,itertools
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.report import compact
from runtime_iteration.tools.metrics import stats,aggregate
from runtime_iteration.tools.module_classes import build
from mapgen import ModuleLibrary

BASE=ROOT/'validation/structure-first-20261105'
LABELS={'v4':'0.5.1 · stable-v4','v5':'0.6.0 · stable-v5','returns':'0.7.0 · 六条多模块折返','merge':'0.7.0 · 一条向前归并＋五条多模块折返'}
def read(p):return json.loads(gzip.decompress(p.read_bytes()))['result']
def inputs(name,seed):
    if seed<960001:
        if name in ['v4','v5']:
            folder='perf501-controller40' if name=='v4' else 'joint-controller40'
            return ROOT/'validation/joint-reward-20261104'/folder/('seed-'+str(seed)+'.json.gz')
        return BASE/('primary-'+name)/('seed-'+str(seed)+'.json.gz')
    folder='fresh-baseline-'+name if name in ['v4','v5'] else 'fresh-'+name
    return BASE/folder/('seed-'+str(seed)+'.json.gz')

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    library=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723');classes=build(library)
    seeds=list(range(930001,930041))+list(range(960001,960021));raw={name:{} for name in LABELS};provenance=[];outcomes=[]
    for name in LABELS:
        for seed in seeds:
            path=inputs(name,seed);r=read(path);raw[name][seed]=r
            provenance.append(dict(algorithm=name,seed=seed,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            kinds=collections.Counter(b['kind'] for b in r['diagnostics']['details'].get('reward_branches',[])) if r['status']=='PASS' else {}
            outcomes.append(dict(algorithm=name,seed=seed,cohort='primary40' if seed<960001 else 'fresh20',status=r['status'],seconds=r['metrics']['generation_seconds'],expansions=r['metrics']['expansions'],repairs=r['metrics']['layout_repairs'],terminal_states=r['metrics']['terminal_states'],single_return=kinds.get('single_return',0),multi_return=kinds.get('multi_return',0),core_merge=kinds.get('core_merge',0),forward_merge=kinds.get('forward_merge',0)))
    summaries={}
    for name,rs in raw.items():
        subsets={'primary40':list(range(930001,930041)),'fresh20':list(range(960001,960021)),'all60':seeds}
        summaries[name]={}
        for cohort,ss in subsets.items():
            rows=[r for r in outcomes if r['algorithm']==name and r['seed'] in ss];ts=sorted(r['seconds'] for r in rows)
            kinds=collections.Counter();failures=collections.Counter()
            for seed in ss:
                r=rs[seed]
                if r['status']=='PASS':kinds.update(b['kind'] for b in r['diagnostics']['details']['reward_branches'])
                else:failures.update(f['reason'] for f in r['diagnostics']['details']['failures'])
            summaries[name][cohort]=dict(statuses=dict(collections.Counter(r['status'] for r in rows)),mean_all_attempt_seconds=statistics.mean(ts),p95_all_attempt_seconds=ts[int((len(ts)-1)*.95)],max_all_attempt_seconds=max(ts),repairs=sum(r['repairs'] for r in rows),expansions=sum(r['expansions'] for r in rows),branch_counts_all_successes=dict(kinds),failure_events=dict(failures),all_multi_style_maps=sum(r['multi_return']==6 for r in rows if r['status']=='PASS'),one_forward_five_multi_maps=sum(r['forward_merge']==1 and r['multi_return']==5 for r in rows if r['status']=='PASS'))
    with (a.out/'all-outcomes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(outcomes[0]));w.writeheader();w.writerows(outcomes)
    paired={};links=[]
    for left,right in [('v4','returns'),('v5','returns'),('v5','merge'),('returns','merge')]:
        common=[seed for seed in seeds if raw[left][seed]['status']==raw[right][seed]['status']=='PASS']
        if len(common)<2:continue
        key=left+'-vs-'+right;metrics={name:aggregate([stats(raw[name][seed],classes) for seed in common]) for name in [left,right]}
        core_metrics={}
        for name in [left,right]:
            core_rows=[]
            for seed in common:
                result=raw[name][seed];core=set(result['diagnostics']['details']['reward_core_ids']);ordinary={i['id']:i for i in result['map']['instances'] if i['id'] in core and i['role']=='traversal'}
                counts=collections.Counter(i['module_id'] for i in ordinary.values());pairs=collections.Counter()
                for connection in result['map']['connections']:
                    u,v=connection['a']['instance_id'],connection['b']['instance_id']
                    if u in ordinary and v in ordinary:pairs[tuple(sorted([ordinary[u]['module_id'],ordinary[v]['module_id']]))]+=1
                core_rows.append(dict(ordinary=len(ordinary),unique=len(counts),unique_fraction=len(counts)/len(ordinary),repeated_neighbor_pairs=sum(n-1 for n in pairs.values())))
            core_metrics[name]={field:statistics.mean(row[field] for row in core_rows) for field in core_rows[0]}
        paired[key]=dict(common_success_seeds=common,metrics=metrics,core_only_ordinary=core_metrics)
        maps=[]
        for seed in seeds:
            row=dict(seed=seed)
            for side,name in [('old',left),('new',right)]:
                row[side]=compact(raw[name][seed]);st=stats(raw[name][seed],classes);row[side+'_stats']={k:v for k,v in st.items() if k not in ['mask','modules','pairs','signature']}
            maps.append(row)
        template=(ROOT/'branch_routes/tools/view.html').read_text()
        template=template.replace('0.4.2 varied-v1 → 新奖励路线算法',LABELS[left]+' → '+LABELS[right]).replace('同批60 seed','同批40回归＋20新seed').replace('0.4.2 · varied-v1',LABELS[left]).replace('新候选 · stable-v4-reward-branches',LABELS[right])
        template=template.replace('旧图未提供同口径的支路规划记录；不据此断言旧图没有长奖励路径。','两版均展示实际支路；归并不证明物理单向，整图动作未认证。').replace('新算法会为奖励支路增加连接模块','不同算法的连接实例数不同')
        template=template.replace('同批统计','共同成功seed布局统计（'+str(len(common))+'例）')
        template=template.replace('if(!bounds.length)return;','if(!bounds.length){for(const side of ["old","new"]){const c=document.querySelector("#"+side);c.width=c.width;document.querySelector("#"+side+"-stat").textContent=row[side].status;}document.querySelector("#notes").textContent="两版均未输出可用地图";return;}')
        cm=core_metrics
        note=f'<p>排除奖励支路连接模块的核心统计（共同成功）：左侧实例{cm[left]["ordinary"]:.2f}、源种类{cm[left]["unique"]:.2f}、重复邻接{cm[left]["repeated_neighbor_pairs"]:.2f}；右侧实例{cm[right]["ordinary"]:.2f}、源种类{cm[right]["unique"]:.2f}、重复邻接{cm[right]["repeated_neighbor_pairs"]:.2f}。</p>'
        template=template.replace('<div id="tip">',note+'<div id="tip">')
        data=dict(maps=maps,summary={'old':metrics[left],'new':metrics[right]});(a.out/(key+'.html')).write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')))
        links.append('<a href="'+key+'.html">'+LABELS[left]+' / '+LABELS[right]+'（共同成功'+str(len(common))+'）</a>')
        module_rows=[]
        for e in library.read('catalog.json')['modules']:
            row={'module_id':e['id'],'title':e['title'],'common_success_maps':len(common)}
            for name in [left,right]:
                instances=0;coverage=0
                for seed in common:
                    count=sum(i['module_id']==e['id'] for i in raw[name][seed]['map']['instances']);instances+=count;coverage+=count>0
                row[name+'_instances']=instances;row[name+'_coverage']=coverage
            module_rows.append(row)
        with (a.out/(key+'-module-usage.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(module_rows[0]));w.writeheader();w.writerows(module_rows)
    report=dict(scope='All60 outcomes retained; layout comparisons use ONLY common successes; timing is diagnostic, not dedicated benchmark; v6 adds hard branch-style constraints, not equivalent workloads; no physics/main game',summaries=summaries,paired=paired,provenance=provenance)
    (a.out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    table='<tr><th>算法</th><th>回归40</th><th>新20</th><th>60例结果</th></tr>'
    for name in LABELS:
        s=summaries[name];table+='<tr><td>'+LABELS[name]+'</td><td>'+str(s['primary40']['statuses'])+'</td><td>'+str(s['fresh20']['statuses'])+'</td><td>'+str(s['all60']['statuses'])+'</td></tr>'
    (a.out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>不同地图生成算法对照</title><style>body{font:16px system-ui;margin:32px;line-height:1.8}td,th{border:1px solid #ccc;padding:10px}table{border-collapse:collapse}a{display:block}</style><h1>版本化结构生成实验：全部60个seed</h1><p>同模块1.1.0、真实两能力请求及32/6/3和90秒/500000预算。新算法有额外奖励结构硬要求，不能把时差全部当作等价加速。失败不显示候选地图；静态检查不代表物理可玩。</p><table>'+table+'</table><h2>地图与共同成功布局对照</h2>'+''.join(links)+'<p>完整结果、实例数、全部模块频率、失败与计时见metrics.json及CSV。没有筛seed，也没有自动替换默认算法。</p>')
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
