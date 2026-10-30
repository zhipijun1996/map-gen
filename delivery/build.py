#!/usr/bin/env python3
"""Export the frozen, accepted 930001 layout; never run or tune the generator."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VERSION = '0.1.0'
COMMIT = '41fe15d8b7450a27ff3b3c0e62eb217bffbf2145'
SEED = 930001
NAME = f'mapgen-delivery-{VERSION}'
STUDY = ROOT / 'experiments/optimization-v2/output'
CASE = STUDY / f'validation/stable/seed-{SEED}'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def safe_name(name):
    return bool(name) and not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts and '\\' not in name


def module_archive(lock):
    path = ROOT / '.cache/legacy-real-v2/modules.zip'
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(lock['url'], timeout=90) as response:
            data = response.read()
    if digest(data) != lock['sha256']:
        raise ValueError('module_archive_sha256_mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or not all(safe_name(n) for n in names):
            raise ValueError('unsafe_or_duplicate_module_path')
        files = {n: z.read(n) for n in names if not n.endswith('/')}
    manifest = json.loads(files['manifest.json'])
    if manifest['version'] != lock['version'] or digest(files['catalog.json']) != lock['catalog_sha256']:
        raise ValueError('module_lock_mismatch')
    for name, sha in manifest['files'].items():
        if digest(files[name]) != sha:
            raise ValueError('module_file_sha256_mismatch:' + name)
    return data, files


def export_map(source, catalog, source_row):
    entries = {e['id']: e for e in catalog['modules']}
    aliases = {i['id']: {pid: p['source_port_id'] for pid, p in i['ports'].items()}
               for i in source['instances']}
    instances, contents = [], {}
    for original in source['instances']:
        iid = original['id']; alias = aliases[iid]; entry = entries[original['source_module_id']]
        role = 'start' if original['module_id'] == 'START' else 'boss' if original['module_id'] == 'BOSS' else 'target_reward' if original['reward'] else 'traversal'
        ports = [dict(id=alias[pid], face=p['face'], surface=p['surface'], permission=p['permission'],
                      local_position_pixels=[v * 64 for v in p['local2']])
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
        contents[content_ref] = encoded(original['content'])
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
                        position_pixels=[v * 64 for v in c['world2']], surface=c['surface'])
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
    data = dict(schema='mapgen/runtime-map/v1', delivery_version=VERSION,
                map_id=f'stable-{COMMIT[:7]}-seed-{SEED}', seed=SEED,
                generator=dict(repository='https://github.com/zhipijun1996/map-gen', commit=COMMIT,
                               profile='stable', structural_sha256=source_row['structural_sha256']),
                module_package=dict(version=source['package']['version'], sha256=source['package']['sha256'], root='module_pack'),
                coordinates=dict(block_size_pixels=128, axes='x_right_y_down', local_frame='owned_rectangle_pixels',
                                 content_transform_applied=True, placement_rule='world_pixel = origin_blocks * 128 + local_pixel'),
                identity=dict(scope='run_id / map_id / instance_id / local_object_id',
                              rule='Host supplies a persistent run_id; never use array indexes for enemy/reward transaction identities.'),
                bounds_blocks=source['quality']['bounds_blocks'], instances=instances, connections=connections,
                anchors=anchors, graph=graph,
                validation=dict(static_generation='PASS', runtime_export='VERIFY_REQUIRED', whole_map_physics='NOT_RUN',
                                playable_in_host='NOT_RUN', source_quality=source['quality']))
    return data, contents


def build(out):
    if out.exists():
        raise ValueError('Refusing to overwrite a delivery; choose a new --out')
    results = load(STUDY / 'results.json')
    for rel, expected in results['source_sha256'].items():
        if digest((ROOT / rel).read_bytes()) != expected:
            raise ValueError('frozen_generation_source_changed:' + rel)
    row = next(r for r in results['results'] if r['variant'] == 'stable' and r['seed'] == SEED)
    raw = (CASE / 'map.json.gz').read_bytes()
    if digest(raw) != row['file_sha256'] or row['status'] != 'PASS':
        raise ValueError('frozen_source_map_changed_or_rejected')
    source = json.loads(gzip.decompress(raw))
    if source['blockers'] or not source['quality']['effect_pass']:
        raise ValueError('source_not_accepted')
    lock = load(ROOT / 'experiments/legacy-real-v2/package-lock.json')
    archive, package_files = module_archive(lock)
    catalog = json.loads(package_files['catalog.json'])
    runtime, content = export_map(source, catalog, row)
    files = {'module_pack/' + name: data for name, data in package_files.items()}
    files.update(content)
    files['dependencies/map-edit-modules-1.1.0.zip'] = archive
    files[f'maps/seed-{SEED}.json'] = encoded(runtime)
    files['reference/source-map.json.gz'] = raw
    files['reference/generation-result.json'] = (CASE / 'result.json').read_bytes()
    files['reference/generation-config.json'] = (ROOT / 'experiments/optimization-v2/config.json').read_bytes()
    files['reference/source-bindings.json'] = (ROOT / 'experiments/legacy-real-v2/bindings.json').read_bytes()
    files['reference/static-audit.json'] = encoded(source['independent_audit'])
    files['reference/physical-notes.json'] = encoded(source['physical_notes'])
    files['reference/stable-replays.json'] = (STUDY / 'validation/stable-replays.json').read_bytes()
    for name in ('README.md', 'CONTRACT.md', 'MAIN_GAME_PROMPT.md', 'runtime-map.schema.json'):
        files[name] = (HERE / 'templates' / name).read_bytes()
    for suffix in ('svg', 'png'):
        files[f'reference/seed-{SEED}.{suffix}'] = (HERE / 'reference' / f'seed-{SEED}.{suffix}').read_bytes()
    files['verify_delivery.py'] = (HERE / 'verify.py').read_bytes()
    stats = dict(instances=len(runtime['instances']), connections=len(runtime['connections']),
                 mirrored=sum(i['transform']['mirror_x'] for i in runtime['instances']),
                 seals=sum(len(i['seals']) for i in runtime['instances']),
                 enemy_records=sum(len(i['content'].get('enemies', [])) for i in source['instances']),
                 reward_sites=sum(len(i['reward_sites']) for i in source['instances']),
                 target_reward_instances=len(runtime['anchors']['target_reward_instances']), main_paths=len(runtime['graph']['main_paths']))
    validation = dict(schema='mapgen/delivery-validation/v1', source_static_generation='PASS',
                      export_checks='Run verify_delivery.py; hashes, real IDs, full content, topology and all goals are checked.',
                      stats=stats, whole_map_physics='NOT_RUN', playable_in_host='NOT_RUN',
                      unresolved=[dict(id='materialized_runtime_loader', status='HOST_IMPLEMENTATION_REQUIRED',
                                       detail='Packaged registry loads original scenes only. Add a host adapter accepting content_ref before node construction; do not edit the immutable module pack or instantiate both geometries.'),
                                  dict(id='player_spawn', status='UNRESOLVED', instance_id=start_id(source),
                                       detail=runtime['anchors']['player_spawn']['reason']),
                                  dict(id='boss_flow', status='UNRESOLVED', instance_id=runtime['anchors']['boss_arrival']['instance_id'],
                                       detail=runtime['anchors']['boss_completion']['reason']),
                                  dict(id='physics_and_actor_profile', status='NOT_RUN',
                                       detail='Whole-map seams, seals, transformed mechanics and continuous player resources require host verification. Catalog/route capability and qualification data remain scoped.'),
                                  dict(id='host_dependencies', status='HOST_CHECK_REQUIRED',
                                       detail='Game actor/assets are not bundled. The original module_pack runtime locks pin exact host commits; compare with current main game, do not overwrite its files or change player tuning to force a pass.')])
    files['reference/validation.json'] = encoded(validation)
    manifest = dict(schema='mapgen/delivery-manifest/v1', version=VERSION,
                    map_ref=f'maps/seed-{SEED}.json', generator=runtime['generator'], module_package=lock,
                    module_archive_ref='dependencies/map-edit-modules-1.1.0.zip',
                    source_map_sha256=digest(raw), exporter_source_sha256=digest(Path(__file__).read_bytes()),
                    stats=stats, certification=dict(static_generation='PASS', whole_map_physics='NOT_RUN', playable_in_host='NOT_RUN'),
                    files={name: digest(data) for name, data in sorted(files.items())})
    files['manifest.json'] = encoded(manifest)
    from verify import verify_bundle
    with tempfile.TemporaryDirectory(prefix='mapgen-delivery-build-') as temp:
        staged = Path(temp) / NAME
        for name, data in files.items():
            target = staged / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        receipt = verify_bundle(staged)
        zipped = Path(temp) / (NAME + '.zip')
        with zipfile.ZipFile(zipped, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
                z.writestr(info, data, compresslevel=9)
        verify_bundle(zipped)
        out.mkdir(parents=True)
        target = out / zipped.name; shutil.copyfile(zipped, target)
        (out / (target.name + '.sha256')).write_text(digest(target.read_bytes()) + '  ' + target.name + '\n')
        receipt.update(archive=target.name, archive_sha256=digest(target.read_bytes()), bytes=target.stat().st_size)
        (out / 'receipt.json').write_bytes(encoded(receipt))
    return receipt


def start_id(source):
    return next(i['id'] for i in source['instances'] if i['module_id'] == 'START')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE / 'releases' / VERSION)
    args = parser.parse_args()
    print(json.dumps(build(args.out), ensure_ascii=False, indent=2))
