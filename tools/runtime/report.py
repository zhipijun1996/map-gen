#!/usr/bin/env python3
"""Render exact generated placements and source content; summarize all trials."""
import hashlib
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/runtime-v1'
PACK = ROOT / 'godot/module_pack'


def load(path):
    return json.loads(path.read_text())


def render(path, output):
    data = load(path)
    entries = {m['id']: m for m in load(PACK / 'catalog.json')['modules']}
    content = {m['id']: load(PACK / m['compiled']) for m in entries.values()}
    x0 = min(i['origin'][0] for i in data['instances']) * 128 - 64
    map_top = min(i['origin'][1] for i in data['instances']) * 128
    x1 = max((i['origin'][0] + entries[i['module_id']]['sizeBlocks'][0]) * 128 for i in data['instances']) + 64
    y1 = max((i['origin'][1] + entries[i['module_id']]['sizeBlocks'][1]) * 128 for i in data['instances']) + 64
    width = x1 - x0
    unit = width / 1600
    y0 = map_top - 80 * unit
    height = y1 - y0
    legend_height = 26 * unit * (len(data['instances']) + 2)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{int((height+legend_height)/width*1600)}" viewBox="{x0} {y0} {width} {height+legend_height}">',
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#5dc8df"/></marker></defs>',
           f'<rect x="{x0}" y="{y0}" width="{width}" height="{height+legend_height}" fill="#0d1825"/>',
           '<g font-family="sans-serif" fill="#e7eef4">',
           f'<text x="{x0+20}" y="{y0+36*unit}" font-size="{22*unit}">Seed {data["seed"]} | {len(data["instances"])} real modules | {len(data["cycles"])} splits | {len(data["rewards"])} route-specific rewards</text>']
    scale = 128
    ports = {}
    for n, item in enumerate(data['instances']):
        e = entries[item['module_id']]
        c = content[e['id']]
        ox, oy = [v * scale for v in item['origin']]
        dx = ox - e['bounds']['x']
        dy = oy - e['bounds']['y']
        w, h = [v * scale for v in e['sizeBlocks']]
        svg.append(f'<g><title>{html.escape(e["id"])} {html.escape(e["title"])}</title><rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="6" fill="#172738" stroke="#7293af" stroke-width="3"/>')
        for p in c['platforms']:
            svg.append(f'<rect x="{p[0]+dx}" y="{p[1]+dy}" width="{p[2]}" height="{p[3]}" fill="#698e80"/>')
        for p in c.get('moving_platforms', []):
            a, b = p['start'], p['finish']
            svg.append(f'<path d="M{a[0]+dx},{a[1]+dy} L{b[0]+dx},{b[1]+dy}" stroke="#ba9f65" stroke-width="3" stroke-dasharray="8 8"/>')
        for p in c.get('saws', []):
            at = p['origin']
            svg.append(f'<circle cx="{at[0]+dx}" cy="{at[1]+dy}" r="{p["radius"]}" fill="#ad615d"/>')
        doc = load(PACK / e['scene'].replace('module.tscn', 'module.mapnote.json'))
        objects = {o['id']: o for o in doc['objects']}
        route_ids = {edge['route_id'] for edge in data['effective_edges']
                     if edge['kind'] == 'module_route' and edge['instance_id'] == item['instance_id']}
        active = [r for r in e['routes'] if r['id'] in route_ids]
        for r in active:
            points = objects.get(r.get('pathObjectId'), {}).get('points', [])
            if not points:
                continue
            at = ' '.join(f'{p["x"]+dx},{p["y"]+dy}' for p in points)
            svg.append(f'<polyline points="{at}" fill="none" stroke="#5dc8df" stroke-width="2" opacity="0.38" marker-end="url(#arrow)"/>')
        for seal in item['sealed_ports']:
            p = seal['rect_pixels']
            svg.append(f'<rect x="{p[0]+ox}" y="{p[1]+oy}" width="{p[2]}" height="{p[3]}" fill="#dc777c"/>')
        for p in e['ports']:
            at = p['position']
            if isinstance(at, dict):
                at = [at['x'], at['y']]
            x, y = at[0] + dx, at[1] + dy
            ports[(item['instance_id'], p['id'])] = (x, y)
            connected = p['id'] in item['connected_port_ids']
            color = '#6edeb9' if connected else '#fc8b94'
            svg.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{color}"/><text x="{x+13}" y="{y-10}" font-size="22" fill="{color}">{html.escape(p["id"])}</text>')
        svg.append(f'<text x="{ox+12}" y="{oy+19*unit}" font-size="{15*unit}" font-weight="bold">M{n:02d}</text></g>')
    for name, color in [('spawn', '#6de6b0'), ('goal', '#ffce74')]:
        x, y = data[name]['position']
        svg.append(f'<circle cx="{x}" cy="{y}" r="18" stroke="{color}" fill="none" stroke-width="5"/><text x="{x+24}" y="{y-25}" font-size="26" fill="{color}">{name}</text>')
    for r in data['rewards']:
        x, y = r['position']
        svg.append(f'<path d="M{x},{y-18} l18,18 l-18,18 l-18,-18 Z" fill="#dca0ed"/>')
    y = y1 + 28 * unit
    svg.append(f'<text x="{x0+20}" y="{y}" font-size="{14*unit}">Green: connected | Red: gear-sealed | Cyan: directed routes | Purple: route reward | physics: {data["validation"]["whole_map_physics"]}</text>')
    for n, item in enumerate(data['instances']):
        y += 24 * unit
        svg.append(f'<text x="{x0+20}" y="{y}" font-size="{13*unit}">M{n:02d} {html.escape(item["module_id"])} | ports {html.escape(",".join(item["connected_port_ids"]))} | origin {item["origin"]}</text>')
    svg.append('</g></svg>')
    output.write_text('\n'.join(svg))


def main():
    batch = load(OUT / 'data-08/data-suite.json')
    assembly = load(OUT / 'assembly-suite.json')
    figures = OUT / 'figures'
    figures.mkdir(exist_ok=True)
    for path in sorted((OUT / 'data-08/layouts').glob('*.json')):
        render(path, figures / (path.stem + '.svg'))
    render(ROOT / 'godot/configs/fallback.json', figures / 'verified-fallback.svg')
    cases = batch['seeds']
    summary = {'schema': 'mapgen/runtime-report/1', 'environment': batch['environment'],
               'package': load(ROOT / 'godot/configs/package-lock.json'),
               'trials': len(cases), 'generated': sum(c['ok'] and not c['fallback'] for c in cases),
               'fallbacks': sum(c['fallback'] for c in cases),
               'failures': [c for c in cases if not c['ok']],
               'data_checks': batch['checks'], 'data_failures': batch['failures'],
               'assembled': len(assembly['cases']), 'assembly_failures': assembly['failures'],
               'package_load_ms': batch['package_load_usec'] / 1000, 'timings_ms': {}}
    for key in ['validation_usec', 'preload_usec', 'assembly_usec', 'peak_step_usec']:
        a = sorted(c[key] / 1000 for c in assembly['cases'] if c['ok'])
        summary['timings_ms'][key] = {'median': statistics.median(a), 'p95': a[int((len(a)-1)*.95)], 'max': max(a)}
    a = sorted(c['diagnostics']['elapsed_usec'] / 1000 for c in cases)
    summary['timings_ms']['solve'] = {'median': statistics.median(a), 'p95': a[int((len(a)-1)*.95)], 'max': max(a)}
    hashes = {}
    for folder in ['godot/addons/mapgen', 'godot/example', 'godot/tests', 'godot/configs', 'tools/runtime']:
        for p in sorted((ROOT / folder).rglob('*')):
            if p.is_file() and p.suffix not in ['.uid', '.pyc']:
                hashes[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    summary['source_sha256'] = hashes
    feedback = {}
    for case in cases:
        for row in case['diagnostics'].get('configuration_feedback', []):
            key = json.dumps([row['module_id'], row['connected_ports'], row['reason']], sort_keys=True)
            feedback.setdefault(key, {**row, 'seeds': []})['seeds'].append(case['seed'])
    (OUT / 'module-feedback.json').write_text(json.dumps({
        'scope': 'candidate exclusions, not a claim that the base module is invalid',
        'configuration_exclusions': list(feedback.values()),
        'external_neighbor_requirements': [r for r in batch['pool_rejections'] if r['reason'] == 'external_neighbor_fixture_required'],
        'profile_exclusions': [r for r in batch['pool_rejections'] if r['reason'] == 'different_initial_player_profile'],
        'remaining_interfaces': ['route-specific reward visits and return/onward evidence for UNKNOWN records',
                                 'incremental/baked scene construction for strict frame budgets',
                                 'closed-Port physical sweeps with neighbor geometry and persistent mechanisms',
                                 'runtime-host 5f55716 route requalification; native evidence is not transferable',
                                 'boundary non-Port crossing and seal ledge/shortcut checks beyond the witnessed playback']
    }, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ['source_sha256', 'package']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
