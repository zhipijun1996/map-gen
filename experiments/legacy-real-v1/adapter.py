"""Data adaptation only. The frozen Generator and model are imported unchanged.

Declared routes permit a diagnostic layout study, never an evidence upgrade.
Every certification mismatch is exported as a blocker; no accepted real map is
published on the strength of these declarations.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'experiments/seed-study/source'
# Both frozen files use a shared top-level model module. Fail rather than mixing
# it with prototype.model or a runtime from PR #1.
sys.path.insert(0, str(SOURCE))
import generate as legacy
import model
assert Path(legacy.__file__).resolve() == SOURCE / 'generate.py'
assert Path(model.__file__).resolve() == SOURCE / 'model.py'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package(archive=None):
    lock = read(HERE / 'package-lock.json')
    archive = Path(archive) if archive else ROOT / '.cache/legacy-real/modules.zip'
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(lock['url'], timeout=90) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != lock['sha256']:
            raise ValueError('package_sha256_mismatch')
        archive.write_bytes(data)
    if sha(archive) != lock['sha256']:
        raise ValueError('package_sha256_mismatch')
    dest = archive.parent / 'package'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:
                raise ValueError('unsafe_package_path:' + name)
        # Re-read from the verified ZIP on every run; stale extracted bytes are
        # never trusted. No imported installer, host dependencies or Godot runs.
        z.extractall(dest)
    manifest = read(dest / 'manifest.json')
    if manifest['version'] != lock['version'] or sha(dest / 'catalog.json') != lock['catalog_sha256']:
        raise ValueError('package_version_or_catalog_mismatch')
    for name, digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:
            raise ValueError('unsafe_manifest_path:' + name)
        if sha(dest / name) != digest:
            raise ValueError('package_file_hash_mismatch:' + name)
    return dest, manifest


def gear_seal(p, size):
    """PR #1 gear-seal/1 geometry, local to owned rectangle, in pixels."""
    x, y = [n * 64 for n in p['local2']]
    w, h = [n * 128 for n in size]
    rect = {'LEFT': [0, y-64, 32, 128], 'RIGHT': [w-32, y-64, 32, 128],
            'TOP': [x-64, 0, 128, 32], 'BOTTOM': [x-64, h-32, 128, 32]}[p['face']]
    return dict(port_id=p['id'], component='gear-seal/1', face=p['face'],
                rect_pixels=rect, opening_pixels=128, thickness_pixels=32,
                certified=False, physical_validation='NOT_RUN')


def segment_hits_rect(a, b, rect):
    """Closed segment/AABB intersection, including tangency and zero length."""
    lo, hi = 0.0, 1.0
    for k in (0, 1):
        delta = b[k] - a[k]
        minimum, maximum = rect[k], rect[k] + rect[k+2]
        if delta == 0:
            if not minimum <= a[k] <= maximum:
                return False
        else:
            u, v = sorted(((minimum-a[k])/delta, (maximum-a[k])/delta))
            lo, hi = max(lo, u), min(hi, v)
            if lo > hi:
                return False
    return True


class RealLibrary:
    def __init__(self, root, bindings=None):
        self.root = Path(root)
        self.catalog = read(self.root / 'catalog.json')
        self.entries = {m['id']: m for m in self.catalog['modules']}
        self.bindings = bindings or {}
        self.templates = {}
        self.feedback = []
        self.role_gaps = []
        assigned = {v['module_id'] for k, v in self.bindings.items() if k in ('START', 'BOSS')}
        for mid, entry in self.entries.items():
            if mid not in assigned:
                self.templates['T:' + mid] = self.adapt('T:' + mid, entry, {})
        for role in ('START', 'BOSS'):
            if role not in self.bindings:
                self.role_gaps.append(dict(role=role, reason='missing_explicit_module_binding'))
                continue
            binding = self.bindings[role]
            self.templates[role] = self.adapt(role, self.entries[binding['module_id']], binding['port_aliases'])
            expected = 'R' if role == 'START' else 'L'
            p = next((p for p in self.templates[role]['ports'] if p['id'] == expected), None)
            if not p or not model.permitted(p, 'out' if role == 'START' else 'in'):
                raise ValueError('invalid_role_port:' + role)
            self.role_gaps.append(dict(role=role, module_id=binding['module_id'],
                port_id=next(k for k, v in binding['port_aliases'].items() if v == expected),
                reason='legacy_boundary_hook_has_no_interior_spawn_or_goal_route_contract'))
        # Only declare Q roles when every route used by legacy reward assembly
        # explicitly names a real reward. A chest or a route role alone is not
        # a proven visit/return edge. No PR #1 reward overrides are imported.
        for key, t in list(self.templates.items()):
            e = self.entries[t['source_module_id']]
            sites = {s['id'] for s in t['compiled_content']['reward_sites']}
            if sites and len(t['ports']) != 1:
                self.feedback.append(dict(module_id=e['id'], port_ids=[p['id'] for p in e['ports']],
                    reward_sites=sorted(sites),
                    explicit_reward_routes=[r['id'] for r in e['routes'] if r.get('resourceProfile', {}).get('requiredRewards')],
                    reason='reward_content_not_legacy_single_port_reward_role'))
            if len(t['ports']) == 1 and sites:
                valid = bool(t['routes']) and all(
                    r.get('resource_profile', {}).get('requiredRewards') and
                    set(r['resource_profile']['requiredRewards']) <= sites for r in t['routes'])
                if valid:
                    self.templates.pop(key)
                    t['id'] = 'Q:' + e['id']; t['reward'] = True
                    self.templates[t['id']] = t
                else:
                    self.feedback.append(dict(module_id=e['id'], route_ids=[r['id'] for r in e['routes']],
                        port_ids=[p['id'] for p in e['ports']], reward_sites=sorted(sites),
                        reason='single_port_reward_route_has_no_explicit_requiredRewards'))
        # Old AIR_A needs side ROCK input -> side AIR output; AIR_B requires
        # side AIR input -> side ROCK output. The delivered pool has neither.
        for role, a_surface, b_surface in [('AIR_A', 'ROCK', 'AIR'), ('AIR_B', 'AIR', 'ROCK')]:
            candidates = []
            for e in self.entries.values():
                pp = {p['id']: p for p in e['ports']}
                for r in e['routes']:
                    a, b = pp[r['from']], pp[r['to']]
                    if (a['surface'], b['surface']) == (a_surface, b_surface) and all(p['face'] in ('LEFT', 'RIGHT') for p in (a, b)):
                        candidates.append(dict(module_id=e['id'], route_id=r['id']))
            self.role_gaps.append(dict(role=role, reason='no_matching_side_air_route' if not candidates else 'explicit_binding_required', candidates=candidates))
        self.role_gaps.append(dict(role='Q', target_count=6, available_templates=sum(k.startswith('Q') for k in self.templates),
            reason='no_single_port_reward_with_explicit_visit_and_return_binding'))

    def adapt(self, key, e, aliases):
        ports = []
        for p in e['ports']:
            xy = p['position']
            if isinstance(xy, dict): xy = [xy['x'], xy['y']]
            local = [2*(xy[k]-e['bounds'][axis])/e['blockSize'] for k, axis in enumerate(('x', 'y'))]
            if any(v != round(v) for v in local): raise ValueError('non_block_port:' + e['id'] + ':' + p['id'])
            ports.append(dict(id=aliases.get(p['id'], p['id']), source_port_id=p['id'],
                local2=[int(v) for v in local], face=p['face'], surface=p['surface'],
                permission=p['permission'], closure='gear-seal/1',
                initial_permission_conditions=p.get('initialPermissionConditions', {})))
        if len({p['id'] for p in ports}) != len(ports): raise ValueError('duplicate_port_alias')
        pp = {p['id']: p for p in ports}; routes = []
        for r in e['routes']:
            a, b = aliases.get(r['from'], r['from']), aliases.get(r['to'], r['to'])
            # Keep every declaration; legacy assembles by endpoints and ability
            # subset. Its independent checks still enforce initial permission.
            caps = ['recoil' if v == 'shot_recoil' else v for v in r['validation']['availableAbilities'] if v != 'move']
            routes.append(dict(id=r['id'], from_port=a, to_port=b,
                displacement=[(pp[b]['local2'][k]-pp[a]['local2'][k])/2 for k in (0, 1)],
                required_abilities=caps, action_tags=r.get('actionTags', []),
                difficulty=r['difficulty'].get('score'), resource_profile=r.get('resourceProfile', {}),
                validation=r['validation'], source_route=copy.deepcopy(r)))
        compiled = read(self.root / e['compiled'])
        doc = read(self.root / e['scene'].replace('module.tscn', 'module.mapnote.json'))
        objects = {o['id']: o for o in doc['objects']}
        for r in routes:
            points = objects.get(r['source_route'].get('pathObjectId'), {}).get('points', [])
            r['path_points'] = [[p['x']-e['bounds']['x'], p['y']-e['bounds']['y']] for p in points]
        return dict(id=key, name=e['title'], size_blocks=e['sizeBlocks'], ports=ports,
            routes=routes, allow_mirror_x=e['mirrorX'] is True, reward=False,
            source_module_id=e['id'], content_version=e['contentVersion'],
            scene=e['scene'], scene_origin_offset=e['sceneOriginOffsetPixels'],
            compiled_content=compiled, source_bounds=e['bounds'])

    def install(self):
        model.LIB.clear()
        model.LIB.update(self.templates)

    def decorate(self, items):
        used = set()
        for (a, ap, _), (b, bp, _) in legacy.connection_groups(items):
            used.update(((a['id'], ap), (b['id'], bp)))
        issues = []
        for i in items:
            t = self.templates[i['module_id']]; e = self.entries[t['source_module_id']]
            i.update(source_module_id=e['id'], content_version=e['contentVersion'], scene=e['scene'],
                     scene_origin_offset=e['sceneOriginOffsetPixels'])
            i['connected_port_ids'] = [pid for pid in i['ports'] if (i['id'], pid) in used]
            i['sealed_ports'] = [gear_seal(p, i['size_blocks']) for pid, p in i['ports'].items() if (i['id'], pid) not in used]
            closed = {s['port_id'] for s in i['sealed_ports']}
            i['retained_route_ids'] = []
            for r in t['routes']:
                if r['from_port'] in closed or r['to_port'] in closed: continue
                if not set(r['required_abilities']) <= model.ABILITIES: continue
                i['retained_route_ids'].append(r['id'])
                base = dict(instance=i['id'], module_id=e['id'], route_id=r['id'])
                if set(r['required_abilities']) != model.ABILITIES:
                    issues.append(dict(**base, reason='ability_set_not_witnessed', actual=sorted(model.ABILITIES), witnessed=r['required_abilities']))
                src = r['source_route']
                if src['validation'].get('testNeighborFixtures'):
                    issues.append(dict(**base, reason='external_neighbor_fixture_required', fixtures=src['validation']['testNeighborFixtures']))
                if not model.permitted(i['ports'][r['from_port']], 'in') or not model.permitted(i['ports'][r['to_port']], 'out'):
                    issues.append(dict(**base, reason='route_violates_initial_port_permission'))
                for seal in i['sealed_ports']:
                    x, y, w, h = seal['rect_pixels']
                    # Match the delivered actor body, 24x36. Conservative author
                    # path clearance, not a simulated trajectory certificate.
                    expanded = [x-12, y-18, w+24, h+36]
                    points = r['path_points']
                    if any(segment_hits_rect(a, b, expanded) for a, b in zip(points, points[1:])):
                        issues.append(dict(**base, reason='gear_seal_intersects_author_path', sealed_port=seal['port_id'], rect_pixels=seal['rect_pixels']))
            if i['sealed_ports']:
                issues.append(dict(instance=i['id'], module_id=e['id'], reason='gear_seal_subset_not_physically_certified', connected_ports=i['connected_port_ids'], sealed_ports=sorted(closed)))
            if e['initialConfiguration'].get('nativeFixture') or e['initialConfiguration'].get('nativeTuning'):
                issues.append(dict(instance=i['id'], module_id=e['id'], reason='legacy_has_no_native_player_profile_binding', initial_configuration=e['initialConfiguration']))
        return issues


def audit(items):
    """Independent old geometry/Port/initial directed graph checks on failures."""
    from collections import defaultdict, deque
    occupied = set(); graph = defaultdict(list); geometry = []
    for i in items:
        x, y = i['origin']; w, h = i['size_blocks']
        assert all(type(v) is int for v in (x, y, w, h))
        for bx in range(x, x+w):
            for by in range(y, y+h):
                assert (bx, by) not in occupied, ('overlap', i['id'], bx, by)
                occupied.add((bx, by))
        for pid, p in i['ports'].items():
            u, v = p['local2']; f = p['face']
            assert p['world2'] == [2*x+u, 2*y+v]
            if f in ('LEFT', 'RIGHT'):
                assert u == (0 if f == 'LEFT' else 2*w) and v % 2 == 1 and 0 < v < 2*h
            else:
                assert v == (0 if f == 'TOP' else 2*h) and u % 2 == 1 and 0 < u < 2*w
            assert p['surface'] != 'ROCK' or f in ('LEFT', 'RIGHT')
            assert not (p['surface'] == 'AIR' and f == 'BOTTOM' and model.permitted(p, 'in'))
        closed = {s['port_id'] for s in i['sealed_ports']}
        assert set(i['connected_port_ids']).isdisjoint(closed)
        assert set(i['ports']) == set(i['connected_port_ids']) | closed
        for seal in i['sealed_ports']:
            sx, sy, sw, sh = seal['rect_pixels']
            assert 0 <= sx < sx+sw <= w*128 and 0 <= sy < sy+sh <= h*128
        for r in model.LIB[i['module_id']]['routes']:
            if r['id'] not in i['retained_route_ids']: continue
            graph[i['id']+'.'+r['from_port']+':arrive'].append(i['id']+'.'+r['to_port']+':depart')
    used = set()
    for (a, ap, p), (b, bp, q) in legacy.connection_groups(items):
        for i, pid in ((a, ap), (b, bp)):
            assert (i['id'], pid) not in used
            used.add((i['id'], pid))
        if model.permitted(p, 'out') and model.permitted(q, 'in'):
            graph[a['id']+'.'+ap+':depart'].append(b['id']+'.'+bp+':arrive')
        if model.permitted(q, 'out') and model.permitted(p, 'in'):
            graph[b['id']+'.'+bp+':depart'].append(a['id']+'.'+ap+':arrive')
    if items:
        graph['START'].append('M01.R:depart')
    boss = next((i for i in items if i['module_id'] == 'BOSS'), None)
    if boss:
        graph[boss['id']+'.L:arrive'].append('BOSS')
    seen = {'START'}; queue = deque(seen)
    while queue:
        for n in graph[queue.popleft()]:
            if n not in seen:
                seen.add(n); queue.append(n)
    reached = {n.split('.')[0].split(':')[0] for n in seen}
    return dict(rectangles='PASS', boundary_block_ports='PASS', seam_geometry_and_permissions='PASS',
        complete_gear_seal_coverage='PASS',
        declared_graph_only=True, boss_reachable='BOSS' in seen,
        unreachable_instances=[dict(instance=i['id'], module_id=i['source_module_id']) for i in items if i['id'] not in reached],
        boss_hook_connected=bool(boss and 'L' in boss['connected_port_ids']),
        main_paths='NOT_REACHED_BECAUSE_GENERATION_REJECTED',
        reward_target=6, reward_instances=sum(i['reward'] for i in items),
        edges=[[a, b] for a in sorted(graph) for b in graph[a]])
