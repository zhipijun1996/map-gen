#!/usr/bin/env python3
"""Standalone delivery verifier: Python standard library; ZIP or extracted root."""
import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
            'invalid_relative_path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == value, 'unsafe_relative_path:' + value)
    return value


def parse(data):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate_json_key:' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite_json_number:' + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def bundle_files(path):
    path = Path(path)
    if path.is_dir():
        files = {}
        for p in path.rglob('*'):
            require(not p.is_symlink(), 'symlink_in_delivery')
            if p.is_file():
                files[safe_path(p.relative_to(path).as_posix())] = p.read_bytes()
        return files
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        require(names and len(names) == len(set(names)), 'empty_or_duplicate_zip_paths')
        roots = {n.split('/')[0] for n in names}
        require(len(roots) == 1, 'zip_requires_one_root_folder')
        files = {}
        for info in z.infolist():
            if info.is_dir():
                continue
            safe_path(info.filename)
            require(not stat.S_ISLNK(info.external_attr >> 16), 'zip_symlink')
            rel = info.filename.split('/', 1)[1]
            files[safe_path(rel)] = z.read(info)
        return files


def permitted(port, direction):
    return port['permission'] in (('OUTPUT', 'INOUT') if direction == 'out' else ('INPUT', 'INOUT'))


def node_key(node):
    return json.dumps({k: v for k, v in node.items() if k != 'id'}, sort_keys=True, separators=(',', ':'))


def port_node(iid, pid, phase):
    return node_key(dict(kind='port_' + phase, instance_id=iid, port_id=pid))


def verify_graph(data):
    instances = {i['id']: i for i in data['instances']}
    ports = {(i['id'], p['id']): p for i in data['instances'] for p in i['ports']}
    nodes = data['graph']['nodes']
    by_id = {n['id']: node_key(n) for n in nodes}
    require(len(by_id) == len(nodes) == len(set(by_id.values())), 'duplicate_graph_node')
    expected = []
    for i in data['instances']:
        for r in i['routes']:
            chain = [port_node(i['id'], r['from_port'], 'arrive')]
            rewards = r['required_reward_ids']
            if rewards:
                groups = [rewards] if i['role'] == 'target_reward' else [[rid] for rid in rewards]
                chain += [node_key(dict(kind='reward', instance_id=i['id'], route_id=r['id'], reward_ids=group,
                                        target=i['role'] == 'target_reward')) for group in groups]
            chain.append(port_node(i['id'], r['to_port'], 'depart'))
            expected.extend(zip(chain, chain[1:]))
    for c in data['connections']:
        a, b = c['a'], c['b']
        pa, pb = ports[a['instance_id'], a['port_id']], ports[b['instance_id'], b['port_id']]
        for start, end, p, q in ((a, b, pa, pb), (b, a, pb, pa)):
            if permitted(p, 'out') and permitted(q, 'in'):
                expected.append((port_node(start['instance_id'], start['port_id'], 'depart'),
                                 port_node(end['instance_id'], end['port_id'], 'arrive')))
    start = data['anchors']['start_departure']; boss = data['anchors']['boss_arrival']
    start_key = node_key(dict(kind='start', instance_id=start['instance_id']))
    boss_key = node_key(dict(kind='boss', instance_id=boss['instance_id']))
    expected += [(start_key, port_node(start['instance_id'], start['port_id'], 'depart')),
                 (port_node(boss['instance_id'], boss['port_id'], 'arrive'), boss_key)]
    edges = data['graph']['edges']
    require(all(len(e) == 2 and all(n in by_id for n in e) for e in edges), 'unknown_graph_endpoint')
    actual = [(by_id[a], by_id[b]) for a, b in edges]
    require(Counter(actual) == Counter(expected), 'actual_graph_differs_from_declared_routes_and_permissions')
    require(set(by_id.values()) == {n for e in expected for n in e}, 'unused_or_missing_graph_node')
    graph = defaultdict(list)
    for a, b in actual:
        graph[a].append(b)
    def reach(start):
        seen = {start}; queue = deque([start])
        while queue:
            for n in graph[queue.popleft()]:
                if n not in seen:
                    seen.add(n); queue.append(n)
        return seen
    seen = reach(start_key)
    require(boss_key in seen, 'boss_unreachable')
    reached_instances = {parse(n)['instance_id'] for n in seen}
    require(set(instances) <= reached_instances, 'unreachable_instance')
    targets = [i['id'] for i in data['instances'] if i['role'] == 'target_reward']
    require(len(targets) == 6 and data['anchors']['target_reward_instances'] == targets, 'six_target_rewards_required')
    for iid in targets:
        claims = [node_key(n) for n in nodes if n['kind'] == 'reward' and n['instance_id'] == iid and node_key(n) in seen]
        require(claims and all(boss_key in reach(n) for n in claims), 'target_reward_claim_or_onward_invalid:' + iid)
    node_instances = {n['id']: n['instance_id'] for n in nodes}
    edge_set = set(map(tuple, edges)); paths = data['graph']['main_paths']; sequences = set()
    require(len(paths) == 3, 'three_main_paths_required')
    for path in paths:
        require(path and all(n in by_id for n in path) and len(path) == len(set(path)), 'invalid_main_path')
        require(by_id[path[0]] == start_key and by_id[path[-1]] == boss_key, 'wrong_main_path_terminals')
        require(all(e in edge_set for e in zip(path, path[1:])), 'invented_main_path_edge')
        sequences.add(tuple(dict.fromkeys(node_instances[n] for n in path)))
    require(len(sequences) == 3, 'main_paths_do_not_have_distinct_module_sequences')


def verify_bundle(path):
    files = bundle_files(path)
    manifest = parse(files['manifest.json'])
    require(manifest['schema'] == 'mapgen/delivery-manifest/v1' and manifest['version'] == '0.1.0', 'unsupported_delivery_version')
    require(set(files) == set(manifest['files']) | {'manifest.json'}, 'manifest_inventory_mismatch')
    for name, expected in manifest['files'].items():
        safe_path(name)
        require(digest(files[name]) == expected, 'file_sha256_mismatch:' + name)
    lock = manifest['module_package']; archive = files[safe_path(manifest['module_archive_ref'])]
    require(digest(archive) == lock['sha256'], 'original_module_zip_changed')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        require(len(names) == len(set(names)), 'duplicate_original_package_paths')
        require({p.removeprefix('module_pack/') for p in files if p.startswith('module_pack/')} == set(names), 'original_package_inventory_changed')
        for name in names:
            require(files['module_pack/' + safe_path(name)] == z.read(name), 'original_module_file_changed:' + name)
    native_manifest = parse(files['module_pack/manifest.json'])
    require(native_manifest['version'] == lock['version'], 'module_version_mismatch')
    for name, expected in native_manifest['files'].items():
        require(digest(files['module_pack/' + safe_path(name)]) == expected, 'native_manifest_hash_mismatch:' + name)
    require(digest(files['module_pack/catalog.json']) == lock['catalog_sha256'], 'catalog_hash_mismatch')
    entries = {e['id']: e for e in parse(files['module_pack/catalog.json'])['modules']}
    data = parse(files[safe_path(manifest['map_ref'])]); source_bytes = files['reference/source-map.json.gz']
    require(digest(source_bytes) == manifest['source_map_sha256'], 'source_map_sha256_mismatch')
    source = parse(gzip.decompress(source_bytes)); originals = {i['id']: i for i in source['instances']}
    require(data['schema'] == 'mapgen/runtime-map/v1' and data['delivery_version'] == manifest['version'], 'unsupported_map_schema')
    require(data['seed'] == source['seed'] == 930001 and data['generator']['profile'] == source['variant'] == 'stable', 'wrong_fixed_seed_or_profile')
    require(data['generator'] == manifest['generator'], 'generator_metadata_mismatch')
    require(data['module_package'] == dict(version=lock['version'], sha256=lock['sha256'], root='module_pack'), 'map_module_lock_mismatch')
    require(data['coordinates'] == dict(block_size_pixels=128, axes='x_right_y_down', local_frame='owned_rectangle_pixels',
                                       content_transform_applied=True, placement_rule='world_pixel = origin_blocks * 128 + local_pixel'), 'ambiguous_coordinate_contract')
    require(data['validation'] == dict(static_generation='PASS', runtime_export='VERIFY_REQUIRED', whole_map_physics='NOT_RUN',
                                        playable_in_host='NOT_RUN', source_quality=source['quality']), 'unearned_runtime_certification')
    require(manifest['certification'] == dict(static_generation='PASS', whole_map_physics='NOT_RUN', playable_in_host='NOT_RUN'), 'unearned_manifest_certification')
    require(source['status'] == 'PASS' and source['quality']['effect_pass'] and not source['blockers'], 'source_was_not_accepted')
    require(len(data['instances']) == len(originals) == len({i['id'] for i in data['instances']}), 'instance_count_or_identity_changed')
    occupied = set(); port_lookup = {}; aliases = {}; stats_enemies = stats_rewards = 0
    for i in data['instances']:
        iid = i['id']; original = originals[iid]; entry = entries[i['module_id']]
        alias = {pid: p['source_port_id'] for pid, p in original['ports'].items()}; aliases[iid] = alias
        require(i['module_id'] == original['source_module_id'] and i['content_version'] == original['content_version'] == entry['contentVersion'], 'real_module_identity_changed:' + iid)
        require(i['origin_blocks'] == original['origin'] and i['size_blocks'] == original['size_blocks'] == entry['sizeBlocks'], 'placement_changed:' + iid)
        require(i['transform'] == dict(mirror_x=original['mirror_x'], content_is_materialized=True), 'ambiguous_transform:' + iid)
        role = 'start' if original['module_id'] == 'START' else 'boss' if original['module_id'] == 'BOSS' else 'target_reward' if original['reward'] else 'traversal'
        require(i['role'] == role, 'instance_role_changed:' + iid)
        require(i['source_scene_ref'] == 'module_pack/' + entry['scene'] and i['source_compiled_ref'] == 'module_pack/' + entry['compiled'], 'wrong_original_resource_refs:' + iid)
        require(i['required_services'] == entry['requiredServices'], 'host_service_requirements_changed:' + iid)
        content = parse(files[safe_path(i['content_ref'])])
        require(content == original['content'], 'materialized_content_changed:' + iid)
        require(content['coordinate_frame'] == 'owned_rectangle_pixels' and content['world_bounds'] == [0, 0, i['size_blocks'][0] * 128, i['size_blocks'][1] * 128], 'content_not_normalized:' + iid)
        stats_enemies += len(content.get('enemies', [])); stats_rewards += len(content.get('reward_sites', []))
        x, y = i['origin_blocks']; w, h = i['size_blocks']
        require(all(type(v) is int for v in (x, y, w, h)) and w > 0 and h > 0, 'noninteger_occupancy:' + iid)
        cells = {(u, v) for u in range(x, x + w) for v in range(y, y + h)}
        require(not occupied & cells, 'module_overlap:' + iid); occupied |= cells
        expected_ports = [dict(id=alias[pid], face=p['face'], surface=p['surface'], permission=p['permission'],
                               local_position_pixels=[v * 64 for v in p['local2']]) for pid, p in original['ports'].items()]
        require(i['ports'] == expected_ports and len({p['id'] for p in i['ports']}) == len(i['ports']), 'port_alias_or_transform_changed:' + iid)
        source_ports = {p['id']: p for p in entry['ports']}
        for p in i['ports']:
            raw = source_ports[p['id']]; xy = raw['position']; xy = [xy['x'], xy['y']] if isinstance(xy, dict) else xy
            pos = [xy[0] - entry['bounds']['x'], xy[1] - entry['bounds']['y']]
            face = raw['face']
            if i['transform']['mirror_x']:
                pos[0] = w * 128 - pos[0]; face = {'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}.get(face, face)
            require(p['local_position_pixels'] == pos and p['face'] == face and p['permission'] == raw['permission'] and p['surface'] == raw['surface'], 'port_disagrees_with_native_catalog:' + iid)
            port_lookup[iid, p['id']] = (p, [x * 128 + pos[0], y * 128 + pos[1]])
        require(i['connected_port_ids'] == [alias[p] for p in original['connected_port_ids']], 'connected_port_subset_changed:' + iid)
        expected_seals = [dict(s, port_id=alias[s['port_id']]) for s in original['sealed_ports']]
        require(i['seals'] == expected_seals, 'seal_data_changed:' + iid)
        closed = [s['port_id'] for s in i['seals']]; connected = i['connected_port_ids']
        require(len(closed) == len(set(closed)) and len(connected) == len(set(connected)) and not set(closed) & set(connected) and set(closed) | set(connected) == set(source_ports), 'incomplete_seal_coverage:' + iid)
        for s in i['seals']:
            p, _ = port_lookup[iid, s['port_id']]; px, py = p['local_position_pixels']
            expected = {'LEFT': [0, py - 64, 32, 128], 'RIGHT': [w * 128 - 32, py - 64, 32, 128],
                        'TOP': [px - 64, 0, 128, 32], 'BOTTOM': [px - 64, h * 128 - 32, 128, 32]}[p['face']]
            require(s['rect_pixels'] == expected and s['component'] == 'gear-seal/1' and s['physical_validation'] == 'NOT_RUN' and not s['certified'], 'invalid_seal_geometry_or_certification:' + iid)
        require([r['id'] for r in i['routes']] == [r['id'] for r in original['effective_routes']], 'retained_route_set_changed:' + iid)
        native_routes = {r['id']: r for r in entry['routes']}
        for r, old in zip(i['routes'], original['effective_routes']):
            native = native_routes[r['id']]
            require((r['from_port'], r['to_port']) == (alias[old['from_port']], alias[old['to_port']]) == (native['from'], native['to']), 'route_direction_or_alias_changed:' + iid)
            require(r['from_port'] in connected and r['to_port'] in connected, 'route_uses_sealed_port:' + iid)
            require(r['required_reward_ids'] == old['reward_ids'] == native.get('resourceProfile', {}).get('requiredRewards', []), 'reward_association_changed:' + iid)
            require(r['required_abilities'] == ['shot_recoil' if a == 'recoil' else a for a in old['required_abilities']] and r['capability_requirements'] == native['capabilityRequirements'], 'ability_requirements_changed:' + iid)
            require(r['source_validation'] == old['validation'] and r['author_path_pixels'] == old['path_points'], 'route_evidence_or_path_changed:' + iid)
    require({p for p in files if p.startswith('content/')} == {i['content_ref'] for i in data['instances']}, 'content_inventory_mismatch')
    expected_connections = []
    for n, c in enumerate(source['connections'], 1):
        def endpoint(value):
            iid, pid = value.split('.', 1)
            return dict(instance_id=iid, port_id=aliases[iid][pid])
        expected_connections.append(dict(id=f'C{n:03}', a=endpoint(c['a']), b=endpoint(c['b']), position_pixels=[v * 64 for v in c['world2']], surface=c['surface']))
    require(data['connections'] == expected_connections, 'connection_set_or_alias_changed')
    used = set(); opposite = {'LEFT': 'RIGHT', 'RIGHT': 'LEFT', 'TOP': 'BOTTOM', 'BOTTOM': 'TOP'}
    for c in data['connections']:
        ka = (c['a']['instance_id'], c['a']['port_id']); kb = (c['b']['instance_id'], c['b']['port_id'])
        require(ka not in used and kb not in used, 'port_connected_twice'); used |= {ka, kb}
        (p, pos), (q, other) = port_lookup[ka], port_lookup[kb]
        require(pos == other == c['position_pixels'] and opposite[p['face']] == q['face'] and p['surface'] == q['surface'] == c['surface'], 'invalid_exact_seam')
        require(permitted(p, 'out') and permitted(q, 'in') or permitted(q, 'out') and permitted(p, 'in'), 'seam_has_no_initial_direction')
    require(used == {(i['id'], pid) for i in data['instances'] for pid in i['connected_port_ids']}, 'connected_ports_not_accounted_for')
    start = next(i for i in data['instances'] if i['role'] == 'start')
    boss = next(i for i in data['instances'] if i['role'] == 'boss')
    require(data['anchors']['start_departure'] == dict(instance_id=start['id'], port_id='exit', validation='STATIC_GRAPH_ONLY') and
            data['anchors']['boss_arrival'] == dict(instance_id=boss['id'], port_id='entry', validation='STATIC_GRAPH_ONLY'), 'terminal_anchor_identity_changed')
    require(data['anchors']['player_spawn']['status'] == 'UNRESOLVED' and data['anchors']['player_spawn']['position_pixels'] is None, 'invented_player_spawn')
    require(data['anchors']['boss_completion']['status'] == 'UNRESOLVED' and data['anchors']['boss_completion']['exit_port_id'] is None, 'invented_boss_completion')
    verify_graph(data)
    x0 = min(i['origin_blocks'][0] for i in data['instances']); y0 = min(i['origin_blocks'][1] for i in data['instances'])
    x1 = max(i['origin_blocks'][0] + i['size_blocks'][0] for i in data['instances']); y1 = max(i['origin_blocks'][1] + i['size_blocks'][1] for i in data['instances'])
    require(data['bounds_blocks'] == [x0, y0, x1, y1] and max((x1 - x0) / (y1 - y0), (y1 - y0) / (x1 - x0)) <= 3, 'shape_gate_failed')
    stats = dict(instances=len(data['instances']), connections=len(data['connections']),
                 mirrored=sum(i['transform']['mirror_x'] for i in data['instances']),
                 seals=sum(len(i['seals']) for i in data['instances']), enemy_records=stats_enemies, reward_sites=stats_rewards,
                 target_reward_instances=len(data['anchors']['target_reward_instances']), main_paths=len(data['graph']['main_paths']))
    require(stats == manifest['stats'], 'manifest_stats_mismatch')
    return dict(status='PASS', delivery_version=manifest['version'], seed=data['seed'], files_checked=len(files), stats=stats,
                checks=['all_file_hashes', 'original_module_package', 'native_ids', 'full_materialized_content', 'exact_geometry_and_seals', 'actual_directed_graph', 'three_paths_six_rewards', 'reference_fidelity'],
                whole_map_physics='NOT_RUN', playable_in_host='NOT_RUN')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', nargs='?', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.bundle), ensure_ascii=False, indent=2))
