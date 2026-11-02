"""Independent geometry, seal coverage and actual directed reward audit."""
from .geometry import permitted, connection_groups

class AuditError(RuntimeError):
    pass

def check(ok,message):
    if not ok:raise AuditError(message)

def configured_connections(items):
    views=[dict(i,ports={pid:p for pid,p in i["ports"].items()if pid in i.get("solver_port_ids",i["ports"])})for i in items]
    return connection_groups(views)

def audit(items, library, reward_target):
    """Validate every layout, including those rejected inside legacy assemble."""
    from collections import defaultdict, deque
    occupied = set()
    graph = defaultdict(list)
    reward_nodes = []
    blockers = []
    used = set()
    ids = {i['id']: i for i in items}
    for i in items:
        x, y = i['origin']
        w, h = i['size_blocks']
        check(all((type(n) is int for n in (x, y, w, h))), 'static geometry/Port invariant: all((type(n) is int for n in (x, y, w, h)))')
        for bx in range(x, x + w):
            for by in range(y, y + h):
                check((bx, by) not in occupied, 'static geometry/Port invariant: (bx, by) not in occupied')
                occupied.add((bx, by))
        for pid, p in i['ports'].items():
            u, v = p['local2']
            f = p['face']
            check(p['world2'] == [2 * x + u, 2 * y + v], "static geometry/Port invariant: p['world2'] == [2 * x + u, 2 * y + v]")
            if f in ('LEFT', 'RIGHT'):
                check(u == (0 if f == 'LEFT' else 2 * w) and v % 2 == 1 and (0 < v < 2 * h), "static geometry/Port invariant: u == (0 if f == 'LEFT' else 2 * w) and v % 2 == 1 and (0 < v < 2 * h)")
            else:
                check(v == (0 if f == 'TOP' else 2 * h) and u % 2 == 1 and (0 < u < 2 * w), "static geometry/Port invariant: v == (0 if f == 'TOP' else 2 * h) and u % 2 == 1 and (0 < u < 2 * w)")
            check(p['surface'] != 'ROCK' or f in ('LEFT', 'RIGHT'), "static geometry/Port invariant: p['surface'] != 'ROCK' or f in ('LEFT', 'RIGHT')")
            check(not (p['surface'] == 'AIR' and f == 'BOTTOM' and permitted(p, 'in')), "static geometry/Port invariant: not (p['surface'] == 'AIR' and f == 'BOTTOM' and permitted(p, 'in'))")
        closed = {s['port_id'] for s in i['sealed_ports']}
        check(set(i['ports']) == set(i['connected_port_ids']) | closed, "static geometry/Port invariant: set(i['ports']) == set(i['connected_port_ids']) | closed")
        check(not set(i['connected_port_ids']) & closed, "static geometry/Port invariant: not set(i['connected_port_ids']) & closed")
        for s in i['sealed_ports']:
            sx, sy, sw, sh = s['rect_pixels']
            check(0 <= sx < sx + sw <= w * library.block_pixels and 0 <= sy < sy + sh <= h * library.block_pixels, 'static geometry/Port invariant: 0 <= sx < sx + sw <= w * library.block_pixels and 0 <= sy < sy + sh <= h * library.block_pixels')
        for r in i['effective_routes']:
            check(r['from_port'] not in closed and r['to_port'] not in closed, "static geometry/Port invariant: r['from_port'] not in closed and r['to_port'] not in closed")
            a = i['ports'][r['from_port']]['world2']
            b = i['ports'][r['to_port']]['world2']
            check(r['displacement'] == [(b[k] - a[k]) / 2 for k in (0, 1)], "static geometry/Port invariant: r['displacement'] == [(b[k] - a[k]) / 2 for k in (0, 1)]")
            chain = [i['id'] + '.' + r['from_port'] + ':arrive']
            if i['reward'] and r['reward_ids']:
                node = i['id'] + ':reward:' + r['id']
                chain.append(node)
                reward_nodes.append(dict(node=node, instance=i['id'], module_id=i['source_module_id'], route_id=r['id'], reward_ids=r['reward_ids'], target=True))
            else:
                for rid in r['reward_ids']:
                    node = i['id'] + ':reward:' + r['id'] + ':' + rid
                    chain.append(node)
                    reward_nodes.append(dict(node=node, instance=i['id'], module_id=i['source_module_id'], route_id=r['id'], reward_ids=[rid], target=False))
            chain.append(i['id'] + '.' + r['to_port'] + ':depart')
            for a, b in zip(chain, chain[1:]):
                graph[a].append(b)
    for (a, ap, p), (b, bp, q) in configured_connections(items):
        for item, pid in ((a, ap), (b, bp)):
            check((item['id'], pid) not in used, "static geometry/Port invariant: (item['id'], pid) not in used")
            used.add((item['id'], pid))
        if permitted(p, 'out') and permitted(q, 'in'):
            graph[a['id'] + '.' + ap + ':depart'].append(b['id'] + '.' + bp + ':arrive')
        if permitted(q, 'out') and permitted(p, 'in'):
            graph[b['id'] + '.' + bp + ':depart'].append(a['id'] + '.' + ap + ':arrive')
    graph['START'].append('M01.R:depart')
    boss = next((i for i in items if i['module_id'] == 'BOSS'), None)
    if boss:
        graph[boss['id'] + '.L:arrive'].append('BOSS')

    def reach(start):
        seen = {start}
        queue = deque([start])
        while queue:
            for n in graph[queue.popleft()]:
                if n not in seen:
                    seen.add(n)
                    queue.append(n)
        return seen
    seen = reach('START')
    if not boss:
        blockers.append(dict(reason='boss_not_placed'))
    elif 'L' not in boss['connected_port_ids']:
        blockers.append(dict(reason='boss_declared_entry_not_connected', instance=boss['id'], module_id=boss['source_module_id'], connected_ports=boss['connected_port_ids']))
    if 'BOSS' not in seen:
        blockers.append(dict(reason='boss_unreachable'))
    for i in items:
        if not i['reward']:
            continue
        ns = [r for r in reward_nodes if r['instance'] == i['id'] and r['node'] in seen]
        if not ns:
            blockers.append(dict(reason='target_reward_unreachable', instance=i['id'], module_id=i['source_module_id']))
        for r in ns:
            if 'BOSS' not in reach(r['node']):
                blockers.append(dict(reason='target_reward_cannot_continue_to_boss', **r))
    reward_count = sum((i['reward'] for i in items))
    if reward_count != reward_target:
        blockers.append(dict(reason='reward_target_not_met', expected=reward_target, actual=reward_count))
    reached = {n.split('.')[0].split(':')[0] for n in seen}
    missing = [dict(instance=i['id'], module_id=i['source_module_id']) for i in items if i['id'] not in reached]
    if missing:
        blockers.append(dict(reason='unreachable_instances', instances=missing))
    for r in reward_nodes:
        r['reachable'] = r['node'] in seen
        r['can_continue_to_boss'] = 'BOSS' in reach(r['node'])
    return dict(geometry='PASS', gear_seal_coverage='PASS', boss_reachable='BOSS' in seen, target_reward_instances=reward_count, all_reward_sites=sum((len(i['reward_sites']) for i in items)), route_reward_nodes=reward_nodes, unreachable_instances=missing, blockers=blockers, edges=[[a, b] for a in sorted(graph) for b in graph[a]])
