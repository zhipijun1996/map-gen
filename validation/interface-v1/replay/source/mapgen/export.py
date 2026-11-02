"""In-memory runtime-map/v2 export. Native identities; full materialized content."""
import copy

def export_runtime(source, catalog, request, config, library, fingerprint):
    SEED=request.to_dict()["seed"]
    block=library.block_pixels
    entries = {e['id']: e for e in catalog['modules']}
    aliases = {i['id']: {pid: p['source_port_id'] for pid, p in i['ports'].items()}
               for i in source['instances']}
    instances, contents = [], {}
    for original in source['instances']:
        iid = original['id']; alias = aliases[iid]; entry = entries[original['source_module_id']]
        role = 'start' if original['module_id'] == 'START' else 'boss' if original['module_id'] == 'BOSS' else 'target_reward' if original['reward'] else 'traversal'
        ports = [dict(id=alias[pid], face=p['face'], surface=p['surface'], permission=p['permission'],
                      local_position_pixels=[v * (block / 2) for v in p['local2']])
                 for pid, p in original['ports'].items()]
        seals = copy.deepcopy(original['sealed_ports'])
        for seal in seals:
            seal['port_id'] = alias[seal['port_id']]
        routes = []
        authored = {r['id']: r for r in entry['routes']}
        for route in original['effective_routes']:
            routes.append(dict(id=route['id'], from_port=alias[route['from_port']],
                               to_port=alias[route['to_port']], required_reward_ids=route['reward_ids'],
                               required_abilities=['shot_recoil' if a == 'recoil' else a for a in route['required_abilities']],
                               author_path_pixels=route['path_points'], source_validation=route['validation'],
                               capability_requirements=authored[route['id']]['capabilityRequirements']))
        content_ref = f'content/{iid}.json'
        contents[content_ref] = copy.deepcopy(original['content'])
        instances.append(dict(id=iid, module_id=original['source_module_id'], content_version=original['content_version'],
                              role=role, origin_blocks=original['origin'], size_blocks=original['size_blocks'],
                              transform=dict(mirror_x=original['mirror_x'], content_is_materialized=True),
                              content_ref=content_ref, ports=ports, connected_port_ids=[alias[p] for p in original['connected_port_ids']],
                              seals=seals, routes=routes, required_services=entry['requiredServices'],
                              source_scene_ref='module_pack/' + entry['scene'], source_compiled_ref='module_pack/' + entry['compiled']))

    def endpoint(value):
        iid, pid = value.split('.', 1)
        return dict(instance_id=iid, port_id=aliases[iid][pid])

    connections = [dict(id=f'C{n:03}', a=endpoint(c['a']), b=endpoint(c['b']),
                        position_pixels=[v * (block / 2) for v in c['world2']], surface=c['surface'])
                   for n, c in enumerate(source['connections'], 1)]
    start = next(i for i in instances if i['role'] == 'start')
    boss = next(i for i in instances if i['role'] == 'boss')
    start_pin = endpoint(next(i['id'] for i in source['instances'] if i['module_id'] == 'START') + '.R')
    boss_pin = endpoint(next(i['id'] for i in source['instances'] if i['module_id'] == 'BOSS') + '.L')
    anchors = dict(start_departure={**start_pin, 'validation': 'STATIC_GRAPH_ONLY'},
                   player_spawn=dict(status='UNRESOLVED', position_pixels=None,
                                     reason='Only the start departure Port was validated; no interior player spawn/path was certified.'),
                   boss_arrival={**boss_pin, 'validation': 'STATIC_GRAPH_ONLY'},
                   boss_encounter=dict(instance_id=boss['id'], status='HOST_BINDING_REQUIRED'),
                   boss_completion=dict(status='UNRESOLVED', exit_port_id=None,
                                        reason='The unused Boss exit is sealed; host must define battle completion without silently opening it.'),
                   target_reward_instances=[i['id'] for i in instances if i['role'] == 'target_reward'])
    known = {'START': dict(kind='start', instance_id=start['id']),
             'BOSS': dict(kind='boss', instance_id=boss['id'])}
    for i in source['instances']:
        for pid in i['ports']:
            for phase in ('arrive', 'depart'):
                known[f'{i["id"]}.{pid}:{phase}'] = dict(kind='port_' + phase, instance_id=i['id'], port_id=aliases[i['id']][pid])
    for reward in source['independent_audit']['route_reward_nodes']:
        known[reward['node']] = dict(kind='reward', instance_id=reward['instance'], route_id=reward['route_id'],
                                     reward_ids=reward['reward_ids'], target=reward['target'])
    edge_nodes = sorted({node for edge in source['independent_audit']['edges'] for node in edge})
    ids = {old: f'n{n:04}' for n, old in enumerate(edge_nodes)}
    graph = dict(nodes=[dict(id=ids[old], **known[old]) for old in edge_nodes],
                 edges=[[ids[a], ids[b]] for a, b in source['independent_audit']['edges']],
                 main_paths=[[ids[n] for n in path] for path in source['main_paths']])
    data = dict(schema='mapgen/runtime-map/v2',
                map_id='map-' + fingerprint[:24], seed=SEED,
                generator=dict(repository='https://github.com/zhipijun1996/map-gen', implementation='mapgen/interface-v1', algorithm='stable-v2',
                               request_fingerprint=fingerprint),
                module_package=dict(version=library.source.version, sha256=library.source.sha256, root='module_pack'),
                coordinates=dict(block_size_pixels=block, axes='x_right_y_down', local_frame='owned_rectangle_pixels',
                                 content_transform_applied=True, placement_rule='world_pixel = origin_blocks * block_size_pixels + local_pixel'),
                identity=dict(scope='run_id / map_id / instance_id / local_object_id',
                              rule='Host supplies a persistent run_id; never use array indexes for enemy/reward transaction identities.'),
                bounds_blocks=source['quality']['bounds_blocks'], instances=instances, connections=connections,
                anchors=anchors, graph=graph,
                validation=dict(static_generation='PASS', runtime_export='PASS', whole_map_physics='NOT_RUN',
                                playable_in_host='NOT_RUN', source_quality=source['quality']))
    data['inputs']=dict(request=request.to_dict(),config=config.to_dict())
    return data, contents
