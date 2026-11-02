"""Verified input bytes, and a request-local prepared library; no installation globals."""
import copy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from types import MappingProxyType
import zipfile

from .contracts import require
from .geometry import placed_ports, connection_groups, permitted, segment_hits_rect
from .transform import materialize


def native_ability(value):
    return 'recoil' if value == 'shot_recoil' else value


@dataclass(frozen=True)
class ModuleLibrary:
    """Shareable immutable archive snapshot. File/network I/O is outside generate()."""
    sha256: str
    version: str
    _files: object

    @classmethod
    def from_zip(cls, path, *, expected_sha256):
        return cls.from_bytes(Path(path).read_bytes(), expected_sha256=expected_sha256)

    @classmethod
    def from_bytes(cls, data, *, expected_sha256):
        fingerprint = hashlib.sha256(data).hexdigest()
        require(fingerprint == expected_sha256, 'library: archive SHA-256 mismatch')
        require(zipfile.is_zipfile(io.BytesIO(data)), 'library: not a ZIP archive')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            require(len(names) == len(set(names)), 'library: duplicate archive paths')
            for name in names:
                require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts and '\\' not in name, 'library: unsafe path')
            files = {name: z.read(name) for name in names if not name.endswith('/')}
        manifest = json.loads(files['manifest.json'])
        require(manifest.get('schema') == 'map-edit/module-package/v1', 'library: unsupported package schema')
        for name, expected in manifest['files'].items():
            require(name in files and hashlib.sha256(files[name]).hexdigest() == expected, 'library: file checksum mismatch:' + name)
        return cls(fingerprint, manifest['version'], MappingProxyType(files))

    def read(self, name):
        return json.loads(self._files[name])


class PreparedLibrary:
    """All mutable caches and solver aliases belong to exactly one request."""
    def __init__(self, source, request, config):
        self.source = source; self.catalog = source.read('catalog.json'); self.request = request.to_dict()
        require(self.catalog.get('schema') == 'map-edit/delivery-catalog/v1', 'library: unsupported catalog schema')
        self.abilities = frozenset(native_ability(a) for a in self.request['player']['abilities'] if a != 'move')
        self.clearance = tuple(self.request['player']['clearance_half_extents_pixels'])
        self.seal_thickness = config.to_dict()['seals']['thickness_pixels']
        entries = self.catalog['modules']; ids = [e['id'] for e in entries]
        require(len(ids) == len(set(ids)), 'library: duplicate module IDs')
        available = set(ids); filters = self.request['module_filter']
        for field in ('include_ids', 'exclude_ids'):
            require(set(filters[field]) <= available, 'request.module_filter.' + field + ': unknown module IDs')
        require(set(filters['regions']) <= {e['region'] for e in entries}, 'request.module_filter.regions: unknown region')
        self.entries = {e['id']: e for e in entries if (not filters['regions'] or e['region'] in filters['regions'])
                        and (not filters['include_ids'] or e['id'] in filters['include_ids']) and e['id'] not in filters['exclude_ids']}
        bindings = self.request['terminals']
        for role, b in bindings.items():
            require(b['module_id'] in self.entries, 'request.terminals.' + role + ': module absent or filtered out')
            entry = self.entries[b['module_id']]; ports = {p['id']: p for p in entry['ports']}
            require(b['port_id'] in ports, 'request.terminals.' + role + ': unknown Port')
            direction = 'out' if role == 'start' else 'in'
            require(permitted(ports[b['port_id']], direction), 'request.terminals.' + role + ': initial permission mismatch')
            if role == 'boss':
                require(entry['purpose'] == 'boss_arena' and b['port_id'] in entry['entryPortIds'], 'request.terminals.boss: not a declared Boss arrival')
        sizes = {e['blockSize'] for e in self.entries.values()}
        require(len(sizes) == 1, 'library: mixed Block sizes')
        self.block_pixels = next(iter(sizes))
        require(type(self.block_pixels) is int and self.block_pixels > 0 and self.block_pixels % 2 == 0, 'library: invalid Block size')
        require(self.seal_thickness < self.block_pixels, 'config.seals: thickness must be smaller than a Block')
        self.templates = {}; self.feedback = []
        self.reward_gaps = source.read('reward-association-gaps.json')
        assigned = {b['module_id'] for b in bindings.values()}
        for mid, entry in self.entries.items():
            if mid in assigned:
                continue
            t = self.adapt('T:' + mid, entry, {})
            has_reward = any(r['reward_ids'] for r in t['routes'])
            if len(t['ports']) > 1 or not has_reward:
                self.templates[t['id']] = t
            if has_reward:
                q = dict(t, id='Q:' + mid, reward=True); self.templates[q['id']] = q
        for role, alias, source_role in (('START', 'R', 'start'), ('BOSS', 'L', 'boss')):
            b = bindings[source_role]; entry = self.entries[b['module_id']]
            # Private compatibility aliases preserve the frozen search sequence.
            aliases = {b['port_id']: alias}
            native_ids = {p['id'] for p in entry['ports']}
            if alias in native_ids and alias != b['port_id']:
                unused = '__source_' + alias
                while unused in native_ids:
                    unused = '_' + unused
                aliases[alias] = unused
            t = self.adapt(role, entry, aliases)
            t['ports'] = [p for p in t['all_ports'] if p['id'] == alias]
            t['routes'] = [r for r in t['all_routes'] if r['from_port'] == r['to_port'] == alias]
            self.templates[role] = t
        self.air_entries, self.air_returns = set(), set()
        for field, target in [('entry_module_ids', self.air_entries), ('return_module_ids', self.air_returns)]:
            for mid in self.request['air_loop'][field]:
                require('T:' + mid in self.templates, 'request.air_loop.' + field + ': module is not an available traversal template:' + mid)
                t = self.templates['T:' + mid]; ports = {p['id']: p for p in t['ports']}
                surfaces = ('ROCK', 'AIR') if field == 'entry_module_ids' else ('AIR', 'ROCK')
                require(any((ports[r['from_port']]['surface'], ports[r['to_port']]['surface']) == surfaces for r in t['routes']),
                        'request.air_loop.' + field + ': missing declared ' + ' -> '.join(surfaces) + ' Route:' + mid)
                target.add('T:' + mid)

    def adapt(self, key, entry, aliases):
        compiled = self.source.read(entry['compiled']); half = self.block_pixels / 2
        require(entry['reward_sites'] == compiled.get('reward_sites', []), 'library: reward site mismatch:' + entry['id'])
        ports = []
        for p in entry['ports']:
            xy = p['position']; xy = [xy['x'], xy['y']] if isinstance(xy, dict) else xy
            loc = [(xy[k] - entry['bounds'][axis]) / half for k, axis in enumerate(('x', 'y'))]
            require(all(v == round(v) for v in loc), 'library: non-Block Port:' + entry['id'])
            ports.append(dict(id=aliases.get(p['id'], p['id']), source_port_id=p['id'], face=p['face'], surface=p['surface'],
                              permission=p['permission'], local2=[int(v) for v in loc], closure='gear-seal/1'))
        pp = {p['id']: p for p in ports}; require(len(pp) == len(ports), 'library: duplicate Port alias')
        objects = {o['id']: o for o in self.source.read(entry['scene'].replace('module.tscn', 'module.mapnote.json'))['objects']}
        rewards = {r['id'] for r in entry['reward_sites']}; routes = []
        for r in entry['routes']:
            a, b = aliases.get(r['from'], r['from']), aliases.get(r['to'], r['to'])
            require(a in pp and b in pp, 'library: unknown Route Port:' + entry['id'])
            required = r.get('resourceProfile', {}).get('requiredRewards', [])
            require(set(required) <= rewards, 'library: unknown Route reward:' + entry['id'])
            caps = [native_ability(v) for v in r['validation']['availableAbilities'] if v != 'move']
            points = objects.get(r.get('pathObjectId'), {}).get('points', [])
            routes.append(dict(id=r['id'], from_port=a, to_port=b, displacement=[(pp[b]['local2'][k] - pp[a]['local2'][k]) / 2 for k in (0, 1)],
                               required_abilities=caps, action_tags=r.get('actionTags', []), difficulty=r['difficulty'].get('score'),
                               resource_profile=r.get('resourceProfile', {}), validation=r['validation'], reward_ids=required,
                               path_points=[[p['x'] - entry['bounds']['x'], p['y'] - entry['bounds']['y']] for p in points]))
        return dict(id=key, name=entry['title'], size_blocks=entry['sizeBlocks'], ports=ports, routes=routes, all_ports=ports, all_routes=routes,
                    allow_mirror_x=True, reward=False, source_module_id=entry['id'], content_version=entry['contentVersion'],
                    scene=entry['scene'], scene_origin_offset=entry['sceneOriginOffsetPixels'], compiled_content=compiled, source_bounds=entry['bounds'])

    def gear_seal(self, p, size):
        unit = self.block_pixels; half = unit / 2; x, y = [v * half for v in p['local2']]
        w, h = [v * unit for v in size]; thickness = self.seal_thickness
        rect = {'LEFT': [0, y-half, thickness, unit], 'RIGHT': [w-thickness, y-half, thickness, unit],
                'TOP': [x-half, 0, unit, thickness], 'BOTTOM': [x-half, h-thickness, unit, thickness]}[p['face']]
        return dict(port_id=p['id'], component='gear-seal/1', face=p['face'], rect_pixels=rect, opening_pixels=unit,
                    thickness_pixels=thickness, certified=False, physical_validation='NOT_RUN')

    def clearance_rect(self, rect):
        x, y, w, h = rect; cx, cy = self.clearance
        return [x-cx, y-cy, w+2*cx, h+2*cy]


    def decorate(self, items):
        used=set()
        for (a,ap,_),(b,bp,_)in connection_groups(items):used.update(((a['id'],ap),(b['id'],bp)))
        notes=[]; blockers=[]
        for i in items:
            t=self.templates[i['module_id']];e=self.entries[t['source_module_id']]
            i['solver_port_ids']=list(i['ports'])
            full=placed_ports(dict(t,ports=t['all_ports']),*i['origin'],i['mirror_x'])
            for pid,p in i['ports'].items():full[pid].update(p)
            i['ports']=full
            i.update(source_module_id=e['id'],content_version=e['contentVersion'],scene=e['scene'],
                scene_origin_offset=e['sceneOriginOffsetPixels'],source_bounds=e['bounds'])
            i['content']=materialize(t,i['mirror_x'],self.block_pixels)
            i['connected_port_ids']=[pid for pid in i['ports']if(i['id'],pid)in used]
            i['sealed_ports']=[self.gear_seal(p,i['size_blocks'])for pid,p in i['ports'].items()if(i['id'],pid)not in used]
            closed={s['port_id']for s in i['sealed_ports']};effective=[]
            for r0 in t['all_routes']:
                r=copy.deepcopy(r0)
                if i['mirror_x']:
                    r['displacement'][0]*=-1
                    r['path_points']=[[i['size_blocks'][0]*self.block_pixels-x,y]for x,y in r['path_points']]
                if r['from_port']in closed or r['to_port']in closed or not set(r['required_abilities'])<=self.abilities:continue
                effective.append(r)
                base=dict(instance=i['id'],module_id=e['id'],route_id=r['id'])
                if not permitted(i['ports'][r['from_port']],'in')or not permitted(i['ports'][r['to_port']],'out'):
                    blockers.append(dict(**base,reason='route_violates_initial_permission'))
                if set(r['required_abilities'])!=self.abilities:
                    notes.append(dict(**base,reason='available_ability_superset_not_physically_witnessed',witnessed=r['required_abilities']))
                if r['validation'].get('testNeighborFixtures'):
                    blockers.append(dict(**base,reason='external_neighbor_fixture_not_bound',fixtures=r['validation']['testNeighborFixtures']))
                if len(r['path_points'])<2:
                    blockers.append(dict(**base,reason='missing_author_path_for_seal_clearance'))
                for s in i['sealed_ports']:
                    expanded=self.clearance_rect(s['rect_pixels'])
                    if any(segment_hits_rect(a,b,expanded)for a,b in zip(r['path_points'],r['path_points'][1:])):
                        blockers.append(dict(**base,reason='gear_seal_intersects_author_path',port_id=s['port_id'],rect_pixels=s['rect_pixels']))
            i['effective_routes']=effective
            i['retained_route_ids']=[r['id']for r in effective]
            i['reward_sites']=copy.deepcopy(i['content']['reward_sites'])
            if i['mirror_x']or i['sealed_ports']:
                notes.append(dict(instance=i['id'],module_id=e['id'],reason='transformed_or_sealed_configuration_physics_not_run'))
            profile=e['initialConfiguration'].get('nativeFixture')or e['initialConfiguration'].get('nativeTuning')
            if profile:notes.append(dict(instance=i['id'],module_id=e['id'],reason='native_player_profile_requires_future_host_binding',profile=profile))
        return notes,blockers
