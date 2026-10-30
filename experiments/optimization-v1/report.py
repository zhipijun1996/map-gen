#!/usr/bin/env python3
"""All-seed ablations, five-row same-scale diagrams and a local comparison page."""
import argparse
from collections import Counter
import html
import importlib.util
import json
import math
from pathlib import Path
import statistics

from solver import HERE,ROOT,RealLibrary,legacy,package,read
from run import write,payload_path,read_payload
from adapter import sha

spec=importlib.util.spec_from_file_location('frozen_v2_drawing',ROOT/'experiments/legacy-real-v2/report.py')
drawing=importlib.util.module_from_spec(spec);spec.loader.exec_module(drawing)


def median(values):return statistics.median(values)if values else None


def aggregate(rows):
    good=[r for r in rows if r['status']=='STATIC_PASS'];times=sorted(r['generation_seconds']for r in rows if 'generation_seconds'in r)
    return dict(trials=len(rows),passed=len(good),rejected=len(rows)-len(good),
        errors=sum(r['status']=='ERROR'for r in rows),timeouts=sum(r['status']=='TIMEOUT'for r in rows),
        failure_causes=dict(Counter((r.get('error')or{}).get('message',r['status'])for r in rows if r['status']!='STATIC_PASS')),
        median_seconds=median(times),p95_seconds=times[max(0,math.ceil(len(times)*.95)-1)]if times else None,
        median_expansions=median([r['expansions']for r in rows if 'expansions'in r]),
        median_backtracks=median([r['backtracks']for r in rows if 'backtracks'in r]),
        passed_median_instances=median([r['instances']for r in good]),
        passed_median_base_modules=median([r['used_base_modules']for r in good]),
        passed_median_cycles=median([r['cycles']for r in good]),
        passed_with_three_main_paths=sum(r['main_paths']==3 for r in good),
        passed_bounds_median_blocks=[median([r['bounds_blocks'][k+2]-r['bounds_blocks'][k]for r in good])for k in(0,1)])


def render(seed,panels,library,path):
    scale=8;bounds=[legacy.bounds(p['data']['instances'])for p in panels]
    width=max(1100,max((b[2]-b[0])*scale for b in bounds)+64)
    heights=[(b[3]-b[1])*scale+78 for b in bounds];height=sum(heights)+110
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4" fill="#6de0ec"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#0e1724"/><g font-family="sans-serif" fill="#e4edf7">',
        f'<text x="24" y="28" font-size="20">Seed {seed} | Five-way comparison | SAME SCALE: 8 px / Block</text>']
    y=60
    for p,b,h in zip(panels,bounds,heights):
        d=p['data'];color='#83e8b8'if p['status']in('STATIC_PASS','PASS')else '#ff9cab'
        svg.append(f'<text x="24" y="{y}" font-size="14" fill="{color}">{html.escape(p["label"])} | {p["status"]} | {len(d["instances"])} instances | {html.escape(p["detail"])}</text>')
        svg.append(drawing.panel(d['instances'],None if p['fixture']else library,24,y+14,scale))
        y+=h
    svg.append(f'<text x="24" y="{height-44}" font-size="12">Green Ports: connected | Red: gear-seal/1 | Purple rooms: six target rewards | MX: complete content reflected</text>')
    svg.append(f'<text x="24" y="{height-22}" font-size="12">Cyan: declared active author paths. STATIC_PASS is geometry/directed-graph validation; no Godot/playability certification.</text></g></svg>')
    path.write_text('\n'.join(svg))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=HERE/'output');args=parser.parse_args();out=args.out
    d=read(out/'results.json');pack,_=package();lib=RealLibrary(pack);lib.install()
    groups={v:[r for r in d['results']if r['variant']==v]for v in d['variants']}
    summary=dict(stage=d['stage'],seeds=d['seeds'],baseline=dict(trials=20,passed=0,rejected=20),
        variants={v:aggregate(rows)for v,rows in groups.items()},
        targets=dict(growth=32,rewards=6),package_version='1.1.0',module_content_changed=False,
        fallback_count=0,seed_replacement_count=0,whole_map_physics='NOT_RUN')
    write(out/'summary.json',summary)
    if d['stage']=='pilot':print(json.dumps(summary,ensure_ascii=False,indent=2));return
    figures=out/'figures';figures.mkdir(exist_ok=True)
    original=read(ROOT/'experiments/seed-study/output/results.json')
    for seed in d['seeds']:
        old=next(r for r in original['results']if r['seed']==seed);oldname='map.json'if old['status']=='PASS'else 'failed-candidate.json'
        oldmap=read(ROOT/f'experiments/seed-study/output/seed-{seed}'/oldname)
        base=read(ROOT/f'experiments/legacy-real-v2/output/seed-{seed}/failed-candidate.json')
        panels=[dict(label='Original fixture experiment',data=oldmap,status=old['status'],fixture=True,detail='historical 52 fixtures'),
            dict(label='Real 1.1.0 / frozen algorithm',data=base,status='REJECTED',fixture=False,detail=base['generation'].get('error',''))]
        for variant in d['variants']:
            row=next(r for r in groups[variant]if r['seed']==seed)
            name='map.json'if row['status']=='STATIC_PASS'else 'failed-candidate.json'
            path=out/variant/f'seed-{seed}'/name
            if not payload_path(path).exists():continue
            body=read_payload(path)
            detail=f"rewards {row['rewards']}/6; paths {row['main_paths']}; cycles {row['cycles']}; backtracks {row['backtracks']}"
            if row.get('error'):detail+='; '+row['error']['message']
            panels.append(dict(label=variant,data=body,status=row['status'],fixture=False,detail=detail))
        render(seed,panels,lib,figures/f'seed-{seed}.svg')
    statuses={str(seed):{v:next(r['status']for r in groups[v]if r['seed']==seed)for v in d['variants']}for seed in d['seeds']}
    options=''.join(f'<option value="{s}">{s}</option>'for s in d['seeds'])
    metricrows=''
    for v,stats in summary['variants'].items():
        metricrows+='<tr>'+''.join(f'<td>{html.escape(str(value))}</td>'for value in[v,f"{stats['passed']}/{stats['trials']}",stats['median_seconds'],stats['median_expansions'],stats['passed_median_instances'],stats['passed_with_three_main_paths'],json.dumps(stats['failure_causes'],ensure_ascii=False)])+'</tr>'
    caserows=''
    for seed in d['seeds']:
        caserows+=f'<tr><td>{seed}</td>'+''.join(f'<td>{statuses[str(seed)][v]}</td>'for v in d['variants'])+'</tr>'
    text='''<!doctype html><meta charset="utf-8"><title>真实模块生成优化实验</title>
<style>body{font:16px system-ui;background:#101a28;color:#e1edfb;margin:24px}a{color:#91dffc}select{font:inherit;padding:6px}iframe{display:block;width:100%;height:78vh;border:1px solid #526377;margin:12px 0}td,th{border:1px solid #526377;padding:8px}table{border-collapse:collapse;margin:16px 0}code{color:#ffb8c7}</style>
<h1>真实模块优化：同库、同 seed、同目标</h1><p>map-edit 1.1.0；32 个生长实例、6 个目标奖励；全部镜像和封口保留。旧算法真实库基线 0/20。每个优化组合只运行固定 seed，不用备用图或替代 seed。</p>
<p>route：前置实际入口和路线检查；expansion：再加有效扩展能力评分；backtrack：再加有界回退和终点空间修复。表中所有失败保留。通过仅代表静态几何与声明路线，不代表 Godot 可玩性。</p>
<table><tr><th>变体</th><th>通过</th><th>生成中位秒</th><th>候选求值中位数</th><th>通过图实例中位数</th><th>通过且有3主路</th><th>拒绝原因</th></tr>'''+metricrows+'''</table>
<label>Seed <select id="seed">'''+options+'''</select></label> <a id="svg">五图同尺度 SVG</a> · <a id="route">route 数据</a> · <a id="expansion">expansion 数据</a> · <a id="backtrack">backtrack 数据</a> · <a href="summary.json">汇总 JSON</a>
<iframe id="map" title="五图同尺度对照"></iframe>
<table><tr><th>Seed</th><th>route</th><th>expansion</th><th>backtrack</th></tr>'''+caserows+'''</table>
<script>const statuses='''+json.dumps(statuses)+''';const pick=document.querySelector('#seed');function show(){const seed=pick.value;document.querySelector('#svg').href='figures/seed-'+seed+'.svg';document.querySelector('#map').src='figures/seed-'+seed+'.svg';for(const variant of ['route','expansion','backtrack'])document.querySelector('#'+variant).href=variant+'/seed-'+seed+'/layout.json';}pick.addEventListener('change',show);show();</script>'''
    (out/'comparison.html').write_text(text)
    write(out/'SHA256.json',dict(source_sha256=d['source_sha256'],
        artifact_sha256={str(p.relative_to(out)):sha(p)for p in sorted(out.rglob('*'))if p.is_file()and p.name!='SHA256.json'}))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
