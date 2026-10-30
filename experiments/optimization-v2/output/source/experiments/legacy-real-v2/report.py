#!/usr/bin/env python3
"""Post-generation audit and same-Block-scale diagrams, including all failures."""
from collections import Counter, defaultdict, deque
import html
import json
import statistics
from pathlib import Path
import argparse

from adapter import HERE, ROOT, SOURCE, RealLibrary, audit, legacy, package, read, sha
from run import write


def bounds(items):
    return legacy.bounds(items) if items else [0, 0, 1, 1]


def explain(seed, real, library, folder):
    graph=defaultdict(list)
    for a,b in real['independent_audit']['edges']:graph[a].append(b)
    previous={'START':None};queue=deque(['START'])
    while queue:
        current=queue.popleft()
        for node in graph[current]:
            if node not in previous:previous[node]=current;queue.append(node)
    instances={i['id']:i for i in real['instances']};dead=[]
    for node in previous:
        if not node.endswith(':arrive') or graph[node]:continue
        iid,pid=node[:-7].split('.',1);i=instances[iid];t=library.templates[i['module_id']]
        path=[];at=node
        while at is not None:path.append(at);at=previous[at]
        dead.append(dict(instance=iid,module_id=i['source_module_id'],port_id=i['ports'][pid]['source_port_id'],
            graph_node=node,from_start=list(reversed(path)),
            declared_outgoing_routes=[dict(route_id=r['id'],to_port=r['to_port'],retained=r['id']in i['retained_route_ids'])for r in t['all_routes']if r['from_port']==pid]))
    result=dict(seed=seed,dead_end_arrivals=dead)
    if real['generation'].get('error')=='RuntimeError: growth exhausted':
        raw=read(folder/'legacy-state.json');g=legacy.Generator(seed);g.items=raw['instances'];mids={k for k in library.templates if k.startswith('T')}
        rows=[]
        for item,pid,p in g.frontier():
            fits=list(g.candidates((item,pid,p),mids))
            rows.append(dict(instance=item['id'],module_id=library.templates[item['module_id']]['source_module_id'],
                port_id=pid,face=p['face'],surface=p['surface'],fitting_traversal_candidates=len(fits)))
        result['remaining_growth_frontier']=rows
        result['full_frontier_fitting_count']=sum(r['fitting_traversal_candidates']for r in rows)
        result['scope']='Post-failure full-frontier audit; no RNG, retry, or accepted placement; original grow samples at most 22 frontiers.'
    return result


def panel(items, library, x0, y0, block=10):
    bx, by, _, _ = bounds(items)
    parts = []
    colors = {'START': '#52d8ae', 'BOSS': '#ffcc77'}
    for i in items:
        x, y = i['origin']; w, h = i['size_blocks']
        x = x0+(x-bx)*block; y = y0+(y-by)*block
        color = colors.get(i['module_id'], '#ce9af3' if i['reward'] else '#6d91b4')
        label = i.get('source_module_id', i['module_id'])
        parts.append(f'<g><title>{html.escape(i["id"]+" "+label+" "+str(i["origin"]))}</title><rect x="{x}" y="{y}" width="{w*block}" height="{h*block}" fill="#1c2b3d" stroke="{color}" stroke-width="1"/>')
        for dx in range(1, w): parts.append(f'<path d="M{x+dx*block},{y} v{h*block}" stroke="#304052" stroke-width=".3"/>')
        for dy in range(1, h): parts.append(f'<path d="M{x},{y+dy*block} h{w*block}" stroke="#304052" stroke-width=".3"/>')
        if library:
            t = library.templates[i['module_id']]
            compiled = i['content']; source = {'x':0,'y':0}; unit = block/128
            for rect in compiled['platforms']:
                rx, ry, rw, rh = rect
                parts.append(f'<rect x="{x+(rx-source["x"])*unit}" y="{y+(ry-source["y"])*unit}" width="{rw*unit}" height="{rh*unit}" fill="#7db6a0"/>')
            def box(rect, fill, opacity=1):
                rx, ry, rw, rh = rect
                return f'<rect x="{x+(rx-source["x"])*unit}" y="{y+(ry-source["y"])*unit}" width="{rw*unit}" height="{rh*unit}" fill="{fill}" opacity="{opacity}"/>'
            for rect in compiled.get('hazards', []): parts.append(box(rect, '#df6e7e', .8))
            for obj in compiled.get('moving_platforms', []):
                a, b = obj['start'], obj['finish']; sw, sh = obj['size']
                parts.append(f'<path d="M{x+(a[0]-source["x"])*unit},{y+(a[1]-source["y"])*unit} L{x+(b[0]-source["x"])*unit},{y+(b[1]-source["y"])*unit}" stroke="#f2ce7a" stroke-width=".7" stroke-dasharray="2 2"/>')
                parts.append(box([a[0]-sw/2,a[1]-sh/2,sw,sh], '#d7bb6c'))
                points=obj.get('loop_points')
                if obj.get('trajectory_kind')=='clockwise_ellipse/v1':
                    from transform import ellipse_sample
                    points=[ellipse_sample(obj,n/64)for n in range(65)]
                if points:
                    line=' '.join(f'{x+a*unit},{y+b*unit}'for a,b in points)
                    parts.append(f'<polyline points="{line}" fill="none" stroke="#f2ce7a" stroke-width=".6" stroke-dasharray="2 2"/>')
            for obj in compiled.get('latches', []):
                for field in ('gate', 'paired_gate'):
                    if field in obj: parts.append(box(obj[field], '#b48edc', .65))
                a = obj.get('bell')
                if a: parts.append(f'<circle cx="{x+(a[0]-source["x"])*unit}" cy="{y+(a[1]-source["y"])*unit}" r="1.2" fill="#ffe993"/>')
            for obj in compiled.get('thorns', []):
                rect = compiled['platforms'][obj['platform_index']]
                rx, ry, rw, rh = rect; offset = obj['start_offset']; length = obj['length']; depth = obj['depth']
                thorn = {'top':[rx+offset,ry-depth,length,depth], 'bottom':[rx+offset,ry+rh,length,depth],
                         'left':[rx-depth,ry+offset,depth,length], 'right':[rx+rw,ry+offset,depth,length]}[obj['face']]
                parts.append(box(thorn, '#ff7d90'))
            for obj in compiled.get('hooks', []):
                parts.append(f'<circle cx="{x+(obj["x"]-source["x"])*unit}" cy="{y+(obj["y"]-source["y"])*unit}" r="2" stroke="#9ce1fc" stroke-width=".7" fill="none"/>')
            for obj in compiled.get('enemies', []):
                a = obj['position']; ex, ey = x+(a[0]-source['x'])*unit, y+(a[1]-source['y'])*unit
                parts.append(f'<path d="M{ex},{ey-2} l2,4 h-4 Z" fill="#ed9b70"/>')
            for obj in compiled.get('reward_sites', []):
                a = obj['position']; ex, ey = x+(a[0]-source['x'])*unit, y+(a[1]-source['y'])*unit
                parts.append(f'<path d="M{ex},{ey-2} l2,2 l-2,2 l-2,-2 Z" fill="#dda8f8"/>')
            for obj in compiled.get('saws', []):
                at = obj['origin']
                parts.append(f'<circle cx="{x+(at[0]-source["x"])*unit}" cy="{y+(at[1]-source["y"])*unit}" r="{obj["radius"]*unit}" fill="#d48881"/>')
            for r in i['effective_routes']:
                points = ' '.join(f'{x+a*unit},{y+b*unit}' for a,b in r['path_points'])
                if points: parts.append(f'<polyline points="{points}" fill="none" stroke="#6de0ec" opacity=".6" stroke-width=".6" marker-end="url(#arrow)"/>')
            for s in i['sealed_ports']:
                rx, ry, rw, rh = s['rect_pixels']
                parts.append(f'<rect x="{x+rx*unit}" y="{y+ry*unit}" width="{rw*unit}" height="{rh*unit}" fill="#ff6d7e"/>')
                for n in range(4):
                    sx = rx+rw/2 if s['face'] in ('LEFT','RIGHT') else rx+16+n*32
                    sy = ry+16+n*32 if s['face'] in ('LEFT','RIGHT') else ry+rh/2
                    parts.append(f'<circle cx="{x+sx*unit}" cy="{y+sy*unit}" r="{14*unit}" stroke="#ffd0d5" stroke-width=".5" fill="#c44e63"/>')
        for pid, p in i['ports'].items():
            u, v = p['local2']; closed = pid in (i.get('closures', []) if not library else [s['port_id'] for s in i['sealed_ports']])
            parts.append(f'<circle cx="{x+u*block/2}" cy="{y+v*block/2}" r="1.5" fill="{"#ff7186" if closed else "#65efba"}"/>')
        parts.append(f'<text x="{x+2}" y="{y+8}" font-size="7" fill="{color}">{i["id"]}{" MX" if i["mirror_x"] else ""}</text></g>')
    return '\n'.join(parts)


def render(seed, old, real, library, dest):
    block = 10
    a, b = bounds(old['instances']), bounds(real['instances'])
    width = max(1000, (max(a[2]-a[0], b[2]-b[0]))*block+48)
    old_height = (a[3]-a[1])*block
    real_height = (b[3]-b[1])*block
    split = 100+old_height
    legend_y = split+80+real_height
    height = legend_y+55+14*len(real['instances'])
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4" fill="#6de0ec"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="#0e1724"/>', '<g font-family="sans-serif" fill="#e4edf7">',
        f'<text x="24" y="26" font-size="18">Seed {seed} | SAME SCALE: 10 px / Block (128 game px)</text>',
        f'<text x="24" y="52" font-size="14">OLD: {len(old["instances"])} fixture instances | archived result: {old["status"]}</text>',
        panel(old['instances'], None, 24, 70, block),
        f'<text x="24" y="{split+16}" font-size="15" fill="#ff99a9">REAL 1.1.0: {real["status"]} | {html.escape(real["generation"].get("error", ""))}</text>',
        f'<text x="24" y="{split+37}" font-size="12">Uniform full-content mirrors; Boss declared entry; 6 reward target unchanged; no retries or fallback. Cyan = declared path, not certified traversal.</text>',
        panel(real['instances'], library, 24, split+58, block),
        f'<text x="24" y="{legend_y+20}" font-size="12">Green Port = connected | Red = gear-seal/1 overlay | Rectangles = full ownership | Mxx labels match source records below</text>']
    for n, i in enumerate(real['instances']):
        label = f'{i["id"]}  {i["source_module_id"]}  origin={i["origin"]}  connected={i["connected_port_ids"]}'
        parts.append(f'<text x="24" y="{legend_y+45+n*14}" font-size="10">{html.escape(label)}</text>')
    parts.append('</g></svg>')
    dest.write_text('\n'.join(parts))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=HERE/'output')
    args = parser.parse_args(); out = args.out
    data = read(out/'results.json'); root, manifest = package()
    library = RealLibrary(root, data['bindings']); library.install()
    audits = []; causes = Counter(); selected = set(); map_rows = []; compatibility = []; explanations=[]
    dimensions = {'old': [], 'real': []}; port_counts = {'old': Counter(), 'real': Counter()}
    for row in data['real']:
        seed = row['seed']; name = 'map.json' if row['status']=='STATIC_PASS' else 'failed-candidate.json'; real = read(out/f'seed-{seed}'/name)
        result = audit(real['instances']); write(out/f'audits/seed-{seed}.json', result)
        explanations.append(explain(seed,real,library,out/f'seed-{seed}'))
        audits.append(dict(seed=seed, **{k:v for k,v in result.items() if k != 'edges'}))
        for issue in real['blockers']:
            causes[issue['reason']] += 1
            compatibility.append(dict(seed=seed, **issue))
        selected.update(i['source_module_id'] for i in real['instances'])
        old_row = next(r for r in data['baseline'] if r['seed'] == seed)
        old = read(ROOT/old_row['archive_path']); old['status'] = old_row['status']
        for kind, d in [('old', old), ('real', real)]:
            b = bounds(d['instances']); dimensions[kind].append([b[2]-b[0], b[3]-b[1]])
            port_counts[kind].update(len(i['ports']) for i in d['instances'])
        render(seed, old, real, library, out/f'seed-{seed}/comparison.svg')
        map_rows.append(dict(seed=seed, old_status=old['status'], old_instances=len(old['instances']),
            real_status=row['status'], real_instances=row['instances'], real_connections=row['connections'], mirrored=row['mirrored'], reward_sites=row['reward_sites'],
            reward_instances=row['rewards'], sealed_ports=row['sealed_ports'],
            real_error=row['generation'].get('error'), boss_reachable=result['boss_reachable'],
            unreachable_instances=len(result['unreachable_instances'])))
    write(out/'audits.json', audits)
    write(out/'failure-explanations.json',explanations)
    write(out/'compatibility-issues.json', compatibility)
    write(out/'summary.json', dict(seeds=data['seeds'], baseline_counts=dict(Counter(r['status'] for r in data['baseline'])),
        real_counts=dict(Counter(r['status'] for r in data['real'])), real_generation_causes=dict(Counter(r['generation'].get('error') for r in data['real'])),
        instance_range=[min(r['instances'] for r in data['real']), max(r['instances'] for r in data['real'])],
        total_gear_seals=sum(r['sealed_ports'] for r in data['real']), total_mirrored=sum(r['mirrored'] for r in data['real']),
        legacy_static_pass_count=sum(r['generation']['status']=='LEGACY_STATIC_PASS' for r in data['real']),
        median_bounds_blocks={k: [statistics.median(row[n] for row in v) for n in (0,1)] for k,v in dimensions.items()},
        placed_port_count_distribution={k:dict(v) for k,v in port_counts.items()},
        compatibility_counts=dict(causes), selected_module_ids=sorted(selected), comparison=map_rows))
    write(out/'adapter-feedback.json', dict(bindings=library.bindings, module_feedback=library.feedback,
        missing_air_roles=library.air_roles, reward_association_gaps=library.reward_gaps))
    options = ''.join(f'<option value="{r["seed"]}">{r["seed"]}: old {r["old_status"]} / real {r["real_status"]}</option>' for r in map_rows)
    rows = ''.join('<tr>'+''.join(f'<td>{html.escape(str(r[k]))}</td>' for k in ('seed','old_status','old_instances','real_instances','real_connections','sealed_ports','real_error'))+'</tr>' for r in map_rows)
    (out/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>旧算法 / 真实模块 · 同 seed 对照</title>
<style>body{font:16px system-ui;background:#101a28;color:#dfebfa;margin:24px}a{color:#8cddfa}select,button{font:inherit;padding:6px}iframe{display:block;width:100%;height:75vh;border:1px solid #526377;background:#0e1724;margin-top:12px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #526377}code{color:#ffb7c0}</style>
<h1>旧算法 / 真实模块 1.1.0：20 个相同 seed</h1><p>旧版 16 通过 / 4 拒绝，精确复现。真实版的结果见下表；REJECTED 是失败候选，STATIC_PASS 也不表示 Godot 可玩性认证。</p>
<p>原算法、默认参数、32 生长目标、6 奖励目标未变。已识别全部宝箱和明确取宝路线；全部模块允许完整镜像和部分 Port 连接。没有重试、回退或补路线。真实内容、未用 Port 的齿轮覆盖层和原始候选均可检查。每张 SVG 上下两图使用相同 Block 比例，可浏览器缩放。</p>
<label>Seed <select id="seed">'''+options+'''</select></label> <a id="svg">打开 SVG</a> · <a id="raw">原始候选 JSON</a> · <a href="summary.json">汇总</a> · <a href="compatibility-issues.json">具体接口/路线问题</a>
<iframe id="map" title="同 seed 地图对照"></iframe><p>图中绿口已连接，红口为 gear-seal/1；青色为作者声明路径。封口、接缝和全图物理未认证。未把能力超集当作已认证配置。</p>
<table><thead><tr><th>Seed</th><th>旧结果</th><th>旧实例</th><th>真实候选实例</th><th>连接</th><th>齿轮封口</th><th>原算法拒绝原因</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<script>const pick=document.querySelector('#seed');function show(){const base='seed-'+pick.value+'/';const status=pick.selectedOptions[0].textContent.includes('STATIC_PASS')?'STATIC_PASS':'REJECTED';document.querySelector('#map').src=base+'comparison.svg';document.querySelector('#svg').href=base+'comparison.svg';document.querySelector('#raw').href=base+(status==='STATIC_PASS'?'map.json':'failed-candidate.json');}pick.addEventListener('change',show);show();</script>''')
    # A real mirrored module with unused Ports, enlarged for seal inspection.
    for row in data['real']:
        name='map.json' if row['status']=='STATIC_PASS' else 'failed-candidate.json'
        sample=read(out/f"seed-{row['seed']}"/name)
        selected=next((i for i in sample['instances'] if i['mirror_x'] and i['sealed_ports']),None)
        if selected:
            width=max(1000,selected['size_blocks'][0]*80+100);height=selected['size_blocks'][1]*80+200
            detail=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#0e1724"/><g font-family="sans-serif" fill="#e4edf7"><text x="24" y="30" font-size="20">Seed {row["seed"]} / {selected["id"]} MX / real mirrored content and gear-seal/1</text>'+panel([selected],library,40,80,80)+f'<text x="24" y="{height-30}" font-size="13">{html.escape(selected["source_module_id"])} | red = unused Port seals; physics NOT RUN</text></g></svg>'
            (out/'gear-seal-detail.svg').write_text(detail);break
    sources = {str(p.relative_to(ROOT)): sha(p) for p in sorted(HERE.glob('*.py'))}
    sources.update({str(p.relative_to(ROOT)): sha(p) for p in sorted(HERE.glob('*.json'))})
    sources.update({str(p.relative_to(ROOT)): sha(p) for p in sorted(HERE.glob('*.md'))})
    hashes = {}
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name != 'SHA256.json': hashes[str(p.relative_to(out))] = sha(p)
    write(out/'SHA256.json', dict(source_sha256=sources, artifact_sha256=hashes,
        frozen_source_sha256={p.name:sha(p) for p in SOURCE.glob('*.py')}))
    print(json.dumps(dict(real_generation_causes=dict(Counter(r['generation'].get('error') for r in data['real'])), compatibility=dict(causes)), indent=2))


if __name__ == '__main__':
    main()
