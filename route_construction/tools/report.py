"""Matched-style algorithm comparisons plus route coverage, not only module counts."""
import argparse,collections,csv,gzip,json,math,statistics
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.report import compact
from runtime_iteration.tools.metrics import stats,aggregate
from runtime_iteration.tools.module_classes import build
from mapgen import ModuleLibrary
BASE=ROOT/'validation/joint-route-construction-20261105'
LABELS={'v7':'0.8.0 / 联合构造','v6merge':'0.7.0 / 先骨架后归并','v6returns':'0.7.0 / 六多模块折返','v5':'0.6.0 / 联合支路'}
SEEDS=list(range(930001,930041))+list(range(960001,960021))+list(range(970001,970021))
def source(name,seed):
    case='seed-'+str(seed)+'.json.gz'
    if name=='v7':return BASE/('primary40' if seed<960001 else 'prior-fresh20' if seed<970001 else 'fresh20')/case
    if name=='v6merge' and seed>=970001:return BASE/'fresh-v6-merge20'/case
    if seed>=970001:return None
    if name=='v5':return ROOT/('validation/joint-reward-20261104/joint-controller40' if seed<960001 else 'validation/structure-first-20261105/fresh-baseline-v5')/case
    suffix='merge' if name=='v6merge' else 'returns'
    return ROOT/'validation/structure-first-20261105'/('primary-'+suffix if seed<960001 else 'fresh-'+suffix)/case
def read(path):return json.loads(gzip.decompress(path.read_bytes()))['result']
def quality(r):
    if r['status']!='PASS':return {}
    m=r['map'];nodes={n['id']:n for n in m['graph']['nodes']};edges=m['graph']['edges'];g={n:[] for n in nodes};back={n:[] for n in nodes}
    for a,b in edges:g[a].append(b);back[b].append(a)
    start=next(n for n,v in nodes.items() if v['kind']=='start');boss=next(n for n,v in nodes.items() if v['kind']=='boss')
    def walk(graph,begin):
        q=collections.deque([begin]);parent={begin:None}
        while q:
            for b in graph[q.popleft()]:
                if b not in parent:parent[b]=None;q.append(b)
        return set(parent)
    def shortest(excluded):
        q=collections.deque([start]);parent={start:None}
        while q and boss not in parent:
            a=q.popleft()
            for b in g[a]:
                if b not in parent and nodes[b]['instance_id'] not in excluded:parent[b]=a;q.append(b)
        if boss not in parent:return None
        path=[];cur=boss
        while cur is not None:path.append(cur);cur=parent[cur]
        return len({nodes[n]['instance_id'] for n in path if nodes[n]['kind'] not in ['start','boss']})
    reached=walk(g,start);finish=walk(back,boss);ids={nodes[n]['instance_id'] for n in reached&finish};ordinary=[i for i in m['instances'] if i['role']=='traversal'];core=set(r['diagnostics']['details']['reward_core_ids']);core_items=[i for i in ordinary if i['id'] in core];counts=collections.Counter(i['module_id'] for i in core_items)
    by={i['id']:i for i in m['instances']};pairs=collections.Counter(tuple(sorted([by[c['a']['instance_id']]['module_id'],by[c['b']['instance_id']]['module_id']])) for c in m['connections'] if c['a']['instance_id'] in core and c['b']['instance_id'] in core and by[c['a']['instance_id']]['role']=='traversal' and by[c['b']['instance_id']]['role']=='traversal')
    a=by[m['anchors']['start_departure']['instance_id']]['origin_blocks'];b=by[m['anchors']['boss_arrival']['instance_id']]['origin_blocks'];branches={i for x in r['diagnostics']['details']['reward_branches'] for i in x['instance_ids']}
    return dict(core_ordinary=len(core_items),core_unique=len(counts),core_unique_fraction=len(counts)/len(core_items),core_repeated_neighbors=sum(n-1 for n in pairs.values()),ordinary_visit_and_finish_fraction=sum(i['id'] in ids for i in ordinary)/len(ordinary),core_visit_and_finish_fraction=sum(i['id'] in ids for i in core_items)/len(core_items),boss_origin_distance=math.hypot(b[0]-a[0],b[1]-a[1]),shortest_full_path_instances=shortest(set()),shortest_core_path_instances=shortest(branches))
def means(rows):return {key:statistics.mean(r[key] for r in rows if r[key] is not None) for key in rows[0]}
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    library=ModuleLibrary.from_zip(ROOT/'.cache/legacy-real-v2/modules.zip',expected_sha256='5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723');classes=build(library);raw={};rows=[];provenance=[]
    for name in LABELS:
        raw[name]={}
        for seed in SEEDS:
            path=source(name,seed)
            if path is None:continue
            r=read(path);raw[name][seed]=r;kinds=collections.Counter(x['kind'] for x in r['diagnostics']['details'].get('reward_branches',[])) if r['status']=='PASS' else {}
            rows.append(dict(algorithm=name,seed=seed,status=r['status'],seconds=r['metrics']['generation_seconds'],expansions=r['metrics']['expansions'],repairs=r['metrics']['layout_repairs'],style_pass=r['status']=='PASS' and kinds=={'forward_merge':1,'multi_return':5},**quality(r)))
            provenance.append(dict(algorithm=name,seed=seed,path=str(path.relative_to(ROOT))))
    summaries={}
    for name in LABELS:
        summaries[name]={}
        for group,seeds in [('primary40',SEEDS[:40]),('prior-fresh20',SEEDS[40:60]),('fresh20',SEEDS[60:]),('common60',SEEDS[:60]),('all',SEEDS)]:
            ss=[x for x in rows if x['algorithm']==name and x['seed'] in seeds]
            if not ss:continue
            ts=sorted(x['seconds'] for x in ss);kinds=collections.Counter()
            for x in ss:
                if x['status']=='PASS':kinds.update(b['kind'] for b in raw[name][x['seed']]['diagnostics']['details']['reward_branches'])
            summaries[name][group]=dict(cases=len(ss),statuses=dict(collections.Counter(x['status'] for x in ss)),style_pass=sum(x['style_pass'] for x in ss),mean_all_attempt_seconds=statistics.mean(ts),p95_all_attempt_seconds=ts[int((len(ts)-1)*.95)],max_all_attempt_seconds=max(ts),total_repairs=sum(x['repairs'] for x in ss),branch_counts_success_maps=dict(kinds))
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with (a.out/'all-outcomes.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    paired={};links=[]
    for left,right in [('v6merge','v7'),('v6returns','v7'),('v5','v7')]:
        seeds=[s for s in SEEDS if s in raw[left] and s in raw[right]];common=[s for s in seeds if raw[left][s]['status']==raw[right][s]['status']=='PASS'];key=left+'-vs-'+right
        if len(common)<2:continue
        metrics={n:aggregate([stats(raw[n][s],classes) for s in common]) for n in [left,right]};qm={n:means([quality(raw[n][s]) for s in common]) for n in [left,right]};paired[key]=dict(cases=len(seeds),common_success_seeds=common,metrics=metrics,route_quality=qm)
        maps=[]
        for seed in seeds:
            row={'seed':seed}
            for side,name in [('old',left),('new',right)]:row[side]=compact(raw[name][seed]);row[side+'_stats']={k:v for k,v in stats(raw[name][seed],classes).items() if k not in ['mask','modules','pairs','signature']}
            maps.append(row)
        html=(ROOT/'branch_routes/tools/view.html').read_text().replace('0.4.2 varied-v1 → 新奖励路线算法',LABELS[left]+' → '+LABELS[right]).replace('同批60 seed',f'同批{len(seeds)} seed').replace('0.4.2 · varied-v1',LABELS[left]).replace('新候选 · stable-v4-reward-branches',LABELS[right]).replace('旧图未提供同口径的支路规划记录；不据此断言旧图没有长奖励路径。','两版均画真实支路；向前归并不证明物理单向。').replace('新算法会为奖励支路增加连接模块','算法间额外连接实例数不同').replace('同批统计',f'共同成功seed统计（{len(common)}例）')
        html=html.replace('if(!bounds.length)return;','if(!bounds.length){for(const side of ["old","new"]){const c=document.querySelector("#"+side);c.width=c.width;document.querySelector("#"+side+"-stat").textContent=row[side].status;}document.querySelector("#notes").textContent="两版均未输出可用地图";return;}')
        notes='<p>核心排除奖励连接模块：'+''.join(f'{LABELS[n]} 源种类{qm[n]["core_unique"]:.2f}、核心可访问并返回Boss比例{qm[n]["core_visit_and_finish_fraction"]:.3f}、最短核心路线实例{qm[n]["shortest_core_path_instances"]:.2f}；' for n in [left,right])+'这些是静态图指标，不是物理试玩。</p>'
        html=html.replace('<div id="tip">',notes+'<div id="tip">');data=dict(maps=maps,summary={'old':metrics[left],'new':metrics[right]});(a.out/(key+'.html')).write_text(html.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')));links.append(f'<a href="{key}.html">{LABELS[left]} / {LABELS[right]}（{len(seeds)}例，共同成功{len(common)}）</a>')
        modules=[]
        for e in library.read('catalog.json')['modules']:
            row=dict(module_id=e['id'],title=e['title'],common_successes=len(common))
            for name in [left,right]:
                counts=[sum(i['module_id']==e['id'] for i in raw[name][s]['map']['instances']) for s in common];row[name+'_instances']=sum(counts);row[name+'_coverage']=sum(c>0 for c in counts)
            modules.append(row)
        with (a.out/(key+'-module-usage.csv')).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(modules[0]));w.writeheader();w.writerows(modules)
    report=dict(scope='Same hard 1-forward/5-multi objective for v6merge vs v7, 80 predefined seeds; other comparisons share60 and different styles. All failures retained; layout/quality ONLY common successes. Reachability metrics are graph-walk capability, not physical proof. Timing is diagnostic, see dedicated serial benchmark.',summaries=summaries,paired=paired,provenance=provenance);(a.out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    table='<tr><th>算法</th><th>同批60</th><th>全新20</th><th>严格归并风格完成</th></tr>'
    for n in LABELS:
        s=summaries[n];allrow=s['all'];table+=f'<tr><td>{LABELS[n]}</td><td>{s["common60"]["statuses"]}</td><td>{s.get("fresh20",{}).get("statuses","未测")}</td><td>{allrow["style_pass"]}/{allrow["cases"]}</td></tr>'
    (a.out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>联合构造算法对照</title><style>body{font:16px system-ui;margin:30px;line-height:1.8}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:9px}a{display:block}</style><h1>0.8.0真实路线联合构造实验</h1><p>模块1.1.0、两能力、32/6/3、90秒/500000预算。0.7归并与0.8同为一向前归并＋五多模块折返；其他配置风格目标不同。失败不输出可用地图，所有样本保留。</p><table>'+table+'</table>'+''.join(links)+'<p>报告同时检查Boss路线长度及核心可访问比例，避免把提前放Boss产生的短流程误当全面质量提升。没有物理或主游戏认证。</p>');print(json.dumps(summaries,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
