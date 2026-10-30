#!/usr/bin/env python3
"""Separate calibration/held-out results, fixed release gate and same-scale maps."""
import argparse
from collections import Counter
import html
import importlib.util
import json
import math
import statistics

from solver import HERE,ROOT,RealLibrary,legacy,package,read
from run import write,read_payload,payload_path
from adapter import sha

spec=importlib.util.spec_from_file_location('frozen_module_drawing',ROOT/'experiments/legacy-real-v2/report.py')
drawing=importlib.util.module_from_spec(spec);spec.loader.exec_module(drawing)


def quantile(values,fraction):
    values=sorted(values)
    return values[max(0,math.ceil(len(values)*fraction)-1)]if values else None


def wilson(passed,total):
    if not total:return None
    z=1.96;p=passed/total;denom=1+z*z/total
    center=(p+z*z/(2*total))/denom
    spread=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denom
    return [center-spread,center+spread]


def aggregate(rows):
    target=[r for r in rows if r.get('quality',{}).get('targets_pass')]
    aspects=[r['quality']['aspect']for r in target]
    times=[r['generation_seconds']for r in rows if 'generation_seconds'in r]
    ops=[r['expansions']for r in rows if 'expansions'in r]
    passed=sum(r['status']=='PASS'for r in rows)
    return dict(trials=len(rows),passed=passed,static_pass=sum(r.get('quality',{}).get('static_pass',False)for r in rows),
        targets_pass=len(target),rejected=len(rows)-passed,errors=sum(r['status']=='ERROR'for r in rows),
        timeouts=sum(r['status']=='TIMEOUT'for r in rows),wilson_95=wilson(passed,len(rows)),
        target_map_aspect_p50=statistics.median(aspects)if aspects else None,
        target_map_aspect_p95=quantile(aspects,.95),target_map_aspect_max=max(aspects)if aspects else None,
        generation_seconds_p50=statistics.median(times)if times else None,generation_seconds_p95=quantile(times,.95),
        expansions_p95=quantile(ops,.95),expansions_max=max(ops)if ops else None,
        failures=[dict(seed=r['seed'],status=r['status'],error=r.get('error'),reasons=r.get('blocker_reasons',[]))for r in rows if r['status']!='PASS'])


def render(cohort,seed,panels,library,path):
    scale=9;bounds=[legacy.bounds(d['instances'])for _,d in panels]
    width=max(1100,max((b[2]-b[0])*scale for b in bounds)+60)
    heights=[(b[3]-b[1])*scale+76 for b in bounds];height=sum(heights)+105
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<defs><marker id="arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4" fill="#6de0ec"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#0e1724"/><g font-family="sans-serif" fill="#e4edf7">',
        f'<text x="24" y="30" font-size="19">{cohort} / Seed {seed} | SAME SCALE: 9 px / Block</text>']
    y=65
    for(row,d),height_row in zip(panels,heights):
        q=row['quality'];color='#87e6b7'if row['status']=='PASS'else '#ff9cab'
        label=f"{row['variant']} | {row['status']} | static {q['static_pass']} | paths {q['main_paths']}/3 | rewards {q['target_rewards']}/6 | aspect {q['aspect']:.2f} | {len(d['instances'])} instances"
        svg.append(f'<text x="24" y="{y}" fill="{color}" font-size="14">{html.escape(label)}</text>')
        svg.append(drawing.panel(d['instances'],library,24,y+14,scale));y+=height_row
    svg.append(f'<text x="24" y="{height-42}" font-size="12">PASS requires actual directed routes, three main paths, six target rewards, full seal checks and aspect at most 3.</text>')
    svg.append(f'<text x="24" y="{height-20}" font-size="12">Green Ports = connected | Red = gear seal | Purple = target reward | Physics/Godot NOT RUN</text></g></svg>')
    path.write_text('\n'.join(svg))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=__import__('pathlib').Path,default=HERE/'output');args=parser.parse_args();out=args.out
    d=read(out/'results.json');cfg=d['config'];cohorts={}
    for cohort,seeds in d['cohorts'].items():
        cohorts[cohort]={v:aggregate([r for r in d['results']if r['cohort']==cohort and r['variant']==v])for v in d['variants']}
    gate=cfg['release_gate'];ready=False
    if 'calibration'in cohorts and 'validation'in cohorts:
        c=cohorts['calibration'][cfg['recommended_profile']];v=cohorts['validation'][cfg['recommended_profile']]
        ready=c['passed']>=gate['min_calibration_passes']and v['passed']>=gate['min_validation_passes']and c['errors']+v['errors']==0 and c['timeouts']+v['timeouts']==0
    summary=dict(cohorts=cohorts,recommended_profile=cfg['recommended_profile'],statistical_gate_passed=ready,
        release_gate=gate,replay_gate='see validation test receipt; statistical gate alone is not release approval',
        whole_map_physics='NOT_RUN',module_content_changed=False)
    write(out/'summary.json',summary)
    pack,_=package();library=RealLibrary(pack);library.install();figures=out/'figures';figures.mkdir(exist_ok=True)
    for cohort,seeds in d['cohorts'].items():
        for seed in seeds:
            panels=[]
            for variant in d['variants']:
                row=next(r for r in d['results']if r['cohort']==cohort and r['seed']==seed and r['variant']==variant)
                path=out/cohort/variant/f'seed-{seed}'/('map.json'if row['status']=='PASS'else 'failed-candidate.json')
                if payload_path(path).exists():panels.append((row,read_payload(path)))
            if panels:render(cohort,seed,panels,library,figures/f'{cohort}-{seed}.svg')
    cohort_options=''.join(f'<option value="{c}">{c}</option>'for c in d['cohorts'])
    metrics=''
    for cohort,variants in cohorts.items():
        for name,a in variants.items():
            values=[cohort,name,f"{a['passed']}/{a['trials']}",a['static_pass'],a['targets_pass'],a['target_map_aspect_p50'],a['target_map_aspect_p95'],a['target_map_aspect_max'],a['expansions_p95']]
            metrics+='<tr>'+''.join(f'<td>{html.escape(str(value))}</td>'for value in values)+'</tr>'
    text='''<!doctype html><meta charset="utf-8"><title>地图效果稳定性实验 v2</title><style>body{font:16px system-ui;background:#101a28;color:#e2edfa;margin:24px}a{color:#90dffc}select{font:inherit;padding:6px}iframe{width:100%;height:80vh;border:1px solid #526377;display:block;margin:12px 0}table{border-collapse:collapse}td,th{border:1px solid #526377;padding:7px}</style>
<h1>地图效果稳定性：同库、同目标、明确形态门槛</h1><p>原 20 个回归 seed 与 20 个未用于调参的验证 seed 分开统计。Module 库不改；32 生长实例、三主路、六奖励、全部路线/封口检查及宽高比≤3缺一不可。</p>
<p>baseline = 上一版；shape = 宽高目标/周长评分；spatial = 再加实际纵向扩展；stable = 再加奖励空间预留及最终目标约束。宽高比分布统计完整目标图，未先筛掉长条。</p>
<table><tr><th>样本组</th><th>配置</th><th>全部通过</th><th>静态通过</th><th>三路六奖励</th><th>宽高比中位</th><th>P95</th><th>最大</th><th>候选求值P95</th></tr>'''+metrics+'''</table>
<p><select id="cohort">'''+cohort_options+'''</select> <select id="seed"></select> <a id="svg">同尺度 SVG</a> · <a id="baseline">baseline 数据</a> · <a id="shape">shape 数据</a> · <a id="spatial">spatial 数据</a> · <a id="stable">stable 数据</a> · <a href="summary.json">完整统计</a></p>
<iframe id="map" title="同seed效果对照"></iframe><p>所有失败保留；PASS 仅是声明图与静态形态检查，尚无 Godot 全图物理认证。有限样本通过率不是所有 seed 的保证。</p>
<script>const cohorts='''+json.dumps(d['cohorts'])+''';const group=document.querySelector('#cohort'),pick=document.querySelector('#seed');function show(){const c=group.value,s=pick.value,file='figures/'+c+'-'+s+'.svg';document.querySelector('#map').src=file;document.querySelector('#svg').href=file;for(const v of ['baseline','shape','spatial','stable'])document.querySelector('#'+v).href=c+'/'+v+'/seed-'+s+'/layout.json';}function change(){pick.innerHTML='';for(const seed of cohorts[group.value])pick.add(new Option(seed,seed));show();}group.addEventListener('change',change);pick.addEventListener('change',show);if(cohorts.validation)group.value='validation';change();</script>'''
    (out/'comparison.html').write_text(text)
    write(out/'SHA256.json',dict(source_sha256=d['source_sha256'],artifact_sha256={str(p.relative_to(out)):sha(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='SHA256.json'}))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
