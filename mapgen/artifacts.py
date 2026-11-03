"""Public result validation and hashing; no LevelPlan, engine or generation I/O."""
from collections import Counter, defaultdict, deque
import copy
import hashlib
import json
from pathlib import PurePosixPath

from .contracts import GenerationRequest, GeneratorConfig, canonical, require, request_fingerprint
from .geometry import permitted, segment_hits_rect
from .package_info import ALGORITHM_ID, IMPLEMENTATION_ID, SCHEMAS
from .transform import materialize

STATUSES = {'PASS', 'INVALID_INPUT', 'SEARCH_EXHAUSTED', 'BUDGET_EXHAUSTED', 'CANCELLED', 'REJECTED', 'ERROR'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value):
    return sha256(canonical(value).encode('utf-8'))


def input_hashes(request, config, library):
    """request_fingerprint keeps its existing combined meaning and exact encoding."""
    return dict(request_sha256=canonical_sha256(request.to_dict()), config_sha256=canonical_sha256(config.to_dict()),
                library_sha256=library.sha256, request_fingerprint=request_fingerprint(request, config, library))


def deterministic_result(value):
    value = copy.deepcopy(value)
    value.get('metrics', {}).pop('generation_seconds', None)
    return value


def result_hashes(value):
    return dict(deterministic_result_sha256=canonical_sha256(deterministic_result(value)),
                map_content_sha256=canonical_sha256(dict(map=value['map'], content_store=value['content_store'])))


def safe_ref(value):
    require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value, 'invalid content/file reference')
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == value, 'unsafe content/file reference:' + value)
    return value


def _key(node):
    return canonical({k: v for k, v in node.items() if k != 'id'})


def _port(iid, pid, phase):
    return _key(dict(kind='port_' + phase, instance_id=iid, port_id=pid))


def _graph(data, goals, port_lookup):
    nodes = data['graph']['nodes']; ids = {n['id']: _key(n) for n in nodes}
    require(len(ids) == len(nodes) == len(set(ids.values())), 'duplicate graph node identity')
    expected = []
    for i in data['instances']:
        for r in i['routes']:
            chain = [_port(i['id'], r['from_port'], 'arrive')]
            rewards = r['required_reward_ids']
            if rewards:
                groups = [rewards] if i['role'] == 'target_reward' else [[rid] for rid in rewards]
                chain.extend(_key(dict(kind='reward', instance_id=i['id'], route_id=r['id'], reward_ids=group,
                                       target=i['role'] == 'target_reward')) for group in groups)
            chain.append(_port(i['id'], r['to_port'], 'depart')); expected.extend(zip(chain, chain[1:]))
    for c in data['connections']:
        a, b = c['a'], c['b']; pa = port_lookup[a['instance_id'], a['port_id']][0]; pb = port_lookup[b['instance_id'], b['port_id']][0]
        for start, end, p, q in ((a, b, pa, pb), (b, a, pb, pa)):
            if permitted(p, 'out') and permitted(q, 'in'):
                expected.append((_port(start['instance_id'], start['port_id'], 'depart'), _port(end['instance_id'], end['port_id'], 'arrive')))
    start, boss = data['anchors']['start_departure'], data['anchors']['boss_arrival']
    first = _key(dict(kind='start', instance_id=start['instance_id'])); last = _key(dict(kind='boss', instance_id=boss['instance_id']))
    expected.extend([(first, _port(start['instance_id'], start['port_id'], 'depart')), (_port(boss['instance_id'], boss['port_id'], 'arrive'), last)])
    edges = data['graph']['edges']
    require(all(len(e) == 2 and all(n in ids for n in e) for e in edges), 'unknown graph endpoint')
    require(Counter((ids[a], ids[b]) for a, b in edges) == Counter(expected), 'graph differs from explicit routes/initial permissions')
    require(set(ids.values()) == {n for edge in expected for n in edge}, 'missing or extraneous graph node')
    graph = defaultdict(list)
    for a, b in expected:
        graph[a].append(b)
    def reachable(at):
        seen = {at}; queue = deque([at])
        while queue:
            for node in graph[queue.popleft()]:
                if node not in seen:
                    seen.add(node); queue.append(node)
        return seen
    seen = reachable(first)
    require(last in seen, 'Boss not reachable')
    require({i['id'] for i in data['instances']} <= {json.loads(n)['instance_id'] for n in seen}, 'unreachable instance')
    targets = [i['id'] for i in data['instances'] if i['role'] == 'target_reward']
    require(targets == data['anchors']['target_reward_instances'] and len(targets) == goals['reward_target'], 'reward goal mismatch')
    for iid in targets:
        claims = [_key(n) for n in nodes if n['kind'] == 'reward' and n['instance_id'] == iid and _key(n) in seen]
        require(claims and all(last in reachable(n) for n in claims), 'reward claim/onward failure:' + iid)
    paths = data['graph']['main_paths']; node_instances = {n['id']: n['instance_id'] for n in nodes}; sequences = set(); edge_set = set(map(tuple, edges))
    require(len(paths) >= goals['main_paths_required'], 'main path goal mismatch')
    for path in paths:
        require(path and all(n in ids for n in path) and len(path) == len(set(path)), 'invalid main path')
        require(ids[path[0]] == first and ids[path[-1]] == last and all(e in edge_set for e in zip(path, path[1:])), 'invented main path')
        sequences.add(tuple(dict.fromkeys(node_instances[n] for n in path)))
    require(len(sequences) == len(paths), 'duplicate module-sequence main path')


def validate_result(value, request, config, library):
    """Check the existing result protocol, full content and actual static map semantics.

    SHA integrity and reference replay are separate checks. This function never
    turns scoped source evidence into engine, Web or whole-map certification.
    """
    require(set(value) == {'schema', 'status', 'request_fingerprint', 'map', 'content_store', 'metrics', 'diagnostics'}, 'invalid result fields')
    require(value['schema'] == SCHEMAS['result'] and value['status'] in STATUSES, 'unknown result schema/status')
    require(isinstance(value['metrics'], dict) and isinstance(value['diagnostics'], dict), 'invalid metrics/diagnostics')
    expected_fp = request_fingerprint(request, config, library)
    require(value['request_fingerprint'] == expected_fp or value['status'] in ('INVALID_INPUT', 'ERROR') and value['request_fingerprint'] is None, 'request fingerprint mismatch')
    if value['status'] != 'PASS':
        require(value['map'] is None and value['content_store'] == {}, 'failed result exposes a usable map/content')
        return dict(status='PASS', generation_status=value['status'], usable_map=False)
    data = value['map']; store = value['content_store']; cfg = config.to_dict(); req = request.to_dict()
    require(isinstance(data, dict) and isinstance(store, dict) and data['schema'] == SCHEMAS['map'], 'invalid runtime-map/content_store')
    require(data['inputs'] == dict(request=req, config=cfg) and data['seed'] == req['seed'], 'resolved input mismatch')
    require(data['generator']['algorithm'] == ALGORITHM_ID and data['generator']['implementation'] == IMPLEMENTATION_ID and
            data['generator']['request_fingerprint'] == expected_fp and data['map_id'] == 'map-' + expected_fp[:24], 'generator identity mismatch')
    require(data['module_package'] == dict(version=library.version, sha256=library.sha256, root='module_pack'), 'module package mismatch')
    catalog = library.read('catalog.json'); entries = {e['id']: e for e in catalog['modules']}
    unit = data['coordinates']['block_size_pixels']
    require(data['coordinates'] == dict(block_size_pixels=unit, axes='x_right_y_down', local_frame='owned_rectangle_pixels', content_transform_applied=True,
                                        placement_rule='world_pixel = origin_blocks * block_size_pixels + local_pixel'), 'coordinate/transform mismatch')
    require(data['validation']['static_generation'] == data['validation']['runtime_export'] == 'PASS' and
            data['validation']['whole_map_physics'] == data['validation']['playable_in_host'] == 'NOT_RUN', 'unearned certification')
    instances = data['instances']; ids = [i['id'] for i in instances]
    require(len(ids) == len(set(ids)) and len(instances) >= cfg['goals']['growth_target'] + cfg['goals']['reward_target'] + 1, 'invalid instance population')
    require(set(store) == {i['content_ref'] for i in instances} and len(store) == len(instances), 'incomplete or unused content_store')
    occupied = set(); ports = {}; roles = defaultdict(list)
    for i in instances:
        iid = i['id']; safe_ref(i['content_ref']); entry = entries[i['module_id']]; content = store[i['content_ref']]
        roles[i['role']].append(i)
        filters = req['module_filter']
        require((not filters['regions'] or entry['region'] in filters['regions']) and (not filters['include_ids'] or i['module_id'] in filters['include_ids']) and i['module_id'] not in filters['exclude_ids'], 'instance outside module filter')
        require(i['content_version'] == entry['contentVersion'] and i['size_blocks'] == entry['sizeBlocks'] and entry['blockSize'] == unit, 'module identity/size mismatch')
        require(i['transform']['content_is_materialized'] is True and type(i['transform']['mirror_x']) is bool, 'unmaterialized transform')
        template = dict(compiled_content=library.read(entry['compiled']), source_bounds=entry['bounds'], size_blocks=entry['sizeBlocks'])
        require(content == materialize(template, i['transform']['mirror_x'], unit), 'incomplete/changed transformed module:' + iid)
        require(content['schema'] == SCHEMAS['content'], 'unsupported content schema')
        require(i['source_scene_ref'] == 'module_pack/' + entry['scene'] and i['source_compiled_ref'] == 'module_pack/' + entry['compiled'] and i['required_services'] == entry['requiredServices'], 'source resource/service mismatch')
        x, y = i['origin_blocks']; w, h = i['size_blocks']
        require(all(type(v) is int for v in (x, y, w, h)) and w > 0 and h > 0, 'invalid integer occupancy')
        cells = {(a, b) for a in range(x, x+w) for b in range(y, y+h)}
        require(not occupied & cells, 'module overlap'); occupied |= cells
        expected_ports = []
        for p in entry['ports']:
            xy = p['position']; xy = [xy['x'], xy['y']] if isinstance(xy, dict) else xy
            pos = [xy[0]-entry['bounds']['x'], xy[1]-entry['bounds']['y']]; face = p['face']
            if i['transform']['mirror_x']:
                pos[0] = w*unit-pos[0]; face = {'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}.get(face, face)
            expected_ports.append(dict(id=p['id'], face=face, surface=p['surface'], permission=p['permission'], local_position_pixels=pos))
        require(i['ports'] == expected_ports and len({p['id'] for p in expected_ports}) == len(expected_ports), 'native Port/transform mismatch')
        local_ports = {p['id']: p for p in i['ports']}; connected = i['connected_port_ids']; closed = [s['port_id'] for s in i['seals']]
        require(len(connected) == len(set(connected)) and len(closed) == len(set(closed)) and not set(connected) & set(closed) and set(connected) | set(closed) == set(local_ports), 'seal coverage mismatch')
        for pid, p in local_ports.items():
            ports[iid, pid] = (p, [x*unit+p['local_position_pixels'][0], y*unit+p['local_position_pixels'][1]])
        for s in i['seals']:
            p = local_ports[s['port_id']]; px, py = p['local_position_pixels']; t = cfg['seals']['thickness_pixels']
            rect = {'LEFT': [0, py-unit/2, t, unit], 'RIGHT': [w*unit-t, py-unit/2, t, unit], 'TOP': [px-unit/2, 0, unit, t], 'BOTTOM': [px-unit/2, h*unit-t, unit, t]}[p['face']]
            require(s == dict(port_id=p['id'], component='gear-seal/1', face=p['face'], rect_pixels=rect, opening_pixels=unit, thickness_pixels=t, certified=False, physical_validation='NOT_RUN'), 'invalid seal data')
        native_routes = {r['id']: r for r in entry['routes']}
        eligible = [r['id'] for r in entry['routes'] if r['from'] in connected and r['to'] in connected and set(r['validation']['availableAbilities']) - {'move'} <= set(req['player']['abilities'])]
        require([r['id'] for r in i['routes']] == eligible, 'missing/invented effective Route')
        objects = {o['id']: o for o in library.read(entry['scene'].replace('module.tscn', 'module.mapnote.json'))['objects']}
        for r in i['routes']:
            native = native_routes[r['id']]
            require((r['from_port'], r['to_port']) == (native['from'], native['to']), 'Route direction mismatch')
            require(r['required_reward_ids'] == native.get('resourceProfile', {}).get('requiredRewards', []) and r['source_validation'] == native['validation'] and r['capability_requirements'] == native['capabilityRequirements'], 'Route reward/evidence mismatch')
            require(r['required_abilities'] == [v for v in native['validation']['availableAbilities'] if v != 'move'], 'Route ability mismatch')
            points = [[p['x']-entry['bounds']['x'], p['y']-entry['bounds']['y']] for p in objects.get(native.get('pathObjectId'), {}).get('points', [])]
            if i['transform']['mirror_x']:
                points = [[w*unit-px, py] for px, py in points]
            require(r['author_path_pixels'] == points and len(points) >= 2, 'author path mismatch')
            require(permitted(local_ports[r['from_port']], 'in') and permitted(local_ports[r['to_port']], 'out') and not native['validation'].get('testNeighborFixtures'), 'initial Route permission/fixture mismatch')
            cx, cy = req['player']['clearance_half_extents_pixels']
            for seal in i['seals']:
                sx, sy, sw, sh = seal['rect_pixels']; rect = [sx-cx, sy-cy, sw+2*cx, sh+2*cy]
                require(not any(segment_hits_rect(a, b, rect) for a, b in zip(points, points[1:])), 'seal intersects retained author path')
    require(len(roles['start']) == len(roles['boss']) == 1 and not set(roles) - {'start', 'boss', 'traversal', 'target_reward'}, 'invalid terminal roles')
    for role, anchor in [('start', 'start_departure'), ('boss', 'boss_arrival')]:
        i = roles[role][0]; bind = req['terminals'][role]
        require(i['module_id'] == bind['module_id'] and data['anchors'][anchor] == dict(instance_id=i['id'], port_id=bind['port_id'], validation='STATIC_GRAPH_ONLY'), 'terminal binding mismatch')
    require(roles['start'][0]['origin_blocks'] == req['start_origin_blocks'], 'start origin mismatch')
    require(data['anchors']['player_spawn']['status'] == data['anchors']['boss_completion']['status'] == 'UNRESOLVED', 'invented gameplay certification')
    require(data['anchors']['player_spawn']['position_pixels'] is None and data['anchors']['boss_completion']['exit_port_id'] is None, 'invented spawn/exit')
    used = set(); connection_ids = set(); opposite = {'LEFT': 'RIGHT', 'RIGHT': 'LEFT', 'TOP': 'BOTTOM', 'BOTTOM': 'TOP'}
    for c in data['connections']:
        require(c['id'] not in connection_ids, 'duplicate connection identity'); connection_ids.add(c['id'])
        a = (c['a']['instance_id'], c['a']['port_id']); b = (c['b']['instance_id'], c['b']['port_id'])
        require(a != b and a not in used and b not in used, 'Port used more than once'); used |= {a, b}
        (p, pos), (q, other) = ports[a], ports[b]
        require(pos == other == c['position_pixels'] and opposite[p['face']] == q['face'] and p['surface'] == q['surface'] == c['surface'], 'seam mismatch')
        require(permitted(p, 'out') and permitted(q, 'in') or permitted(q, 'out') and permitted(p, 'in'), 'seam has no initial direction')
    require(used == {(i['id'], p) for i in instances for p in i['connected_port_ids']}, 'missing connection')
    x0 = min(i['origin_blocks'][0] for i in instances); y0 = min(i['origin_blocks'][1] for i in instances)
    x1 = max(i['origin_blocks'][0]+i['size_blocks'][0] for i in instances); y1 = max(i['origin_blocks'][1]+i['size_blocks'][1] for i in instances)
    require(data['bounds_blocks'] == [x0, y0, x1, y1] and max((x1-x0)/(y1-y0), (y1-y0)/(x1-x0)) <= cfg['shape']['max_aspect'], 'shape/bounds mismatch')
    _graph(data, cfg['goals'], ports)
    from .metrics import quality
    minimal = [dict(origin=i['origin_blocks'], size_blocks=i['size_blocks'], reward=i['role'] == 'target_reward') for i in instances]
    actual_quality = quality(minimal, data['graph']['main_paths'], True, dict(cfg['goals'], shape=cfg['shape']))
    require(data['validation']['source_quality'] == actual_quality, 'quality metadata mismatch')
    return dict(status='PASS', generation_status='PASS', usable_map=True, instances=len(instances), content_refs=len(store),
                whole_map_physics='NOT_RUN', **result_hashes(value))
