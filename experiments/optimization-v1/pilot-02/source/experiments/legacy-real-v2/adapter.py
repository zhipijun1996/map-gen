"""Data adaptation only. The frozen Generator and model are imported unchanged.

Declared routes permit a diagnostic layout study, never an evidence upgrade.
Certification differences are reported independently of static generation.
The user authorizes uniform mirroring and partial Port connections.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
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
    archive = Path(archive) if archive else ROOT / '.cache/legacy-real-v2/modules.zip'
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(lock['url'], timeout=90) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != lock['sha256']:
            raise ValueError('package_sha256_mismatch')
        with tempfile.NamedTemporaryFile(dir=archive.parent,delete=False)as temp:
            staged=Path(temp.name);temp.write(data)
        os.replace(staged,archive)
    if sha(archive) != lock['sha256']:
        raise ValueError('package_sha256_mismatch')
    dest = archive.parent / 'package'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:
                raise ValueError('unsafe_package_path:' + name)
        manifest_bytes=z.read('manifest.json')
        manifest=json.loads(manifest_bytes)
        if manifest['version']!=lock['version']:raise ValueError('package_version_mismatch')
        for name in manifest['files']:
            if Path(name).is_absolute()or'..'in Path(name).parts or'\\'in name:
                raise ValueError('unsafe_manifest_path:'+name)
        def verify(target):
            if sha(target/'manifest.json')!=hashlib.sha256(manifest_bytes).hexdigest():
                raise ValueError('manifest_hash_mismatch')
            if sha(target/'catalog.json')!=lock['catalog_sha256']:
                raise ValueError('catalog_hash_mismatch')
            for name,digest in manifest['files'].items():
                if sha(target/name)!=digest:raise ValueError('package_file_hash_mismatch:'+name)
        # A verified cache is immutable. Concurrent workers never rewrite files
        # while another reader verifies or reads them. A new extraction becomes
        # visible only after all files have been verified in a private directory.
        if not dest.exists():
            with tempfile.TemporaryDirectory(dir=archive.parent,prefix='package-stage-')as temp:
                staged=Path(temp)/'package';z.extractall(staged);verify(staged)
                try:staged.rename(dest)
                except OSError:
                    if not dest.is_dir():raise
                    verify(dest)
        verify(dest)
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


from transform import materialize


class RealLibrary:
    def __init__(self, root, bindings=None):
        self.root = Path(root)
        self.catalog = read(self.root/'catalog.json')
        self.entries = {e['id']:e for e in self.catalog['modules']}
        if len(self.entries) != len(self.catalog['modules']): raise ValueError('duplicate_module_id')
        self.bindings = bindings if bindings is not None else read(HERE/'bindings.json')
        self.templates = {}; self.feedback = []
        self.reward_gaps = read(self.root/'reward-association-gaps.json')
        assigned = {v['module_id'] for v in self.bindings.values()}
        for mid, e in self.entries.items():
            if mid in assigned: continue
            t = self.adapt('T:'+mid, e, {})
            # One immutable content base may fill both traversal and reward
            # roles. These are ABI aliases for old T*/Q* dispatch, not copied
            # modules or duplicated connected-Port subset templates.
            has_reward_route = any(r['reward_ids'] for r in t['routes'])
            if len(t['ports']) > 1 or not has_reward_route:
                self.templates[t['id']] = t
            if has_reward_route:
                q = dict(t, id='Q:'+mid, reward=True)
                self.templates[q['id']] = q
                if not all(r['reward_ids'] for r in t['routes']):
                    self.feedback.append(dict(module_id=mid, reason='legacy_module_reward_phase_requires_route_level_audit'))
        for role, binding in self.bindings.items():
            e = self.entries[binding['module_id']]
            if role == 'BOSS':
                if e['purpose'] != 'boss_arena': raise ValueError('boss_purpose_mismatch')
                target = next(k for k,v in binding['port_aliases'].items() if v=='L')
                if target not in e['entryPortIds']: raise ValueError('boss_port_not_declared_entry')
            t = self.adapt(role, e, binding['port_aliases'])
            # The original algorithm's terminal roles each expose one Port.
            # Express that as an instance configuration over the full source,
            # never alter a physical Port permission or delete base content.
            selected = {'R'} if role=='START' else {'L'}
            t['ports'] = [p for p in t['all_ports'] if p['id'] in selected]
            t['routes'] = [r for r in t['all_routes'] if r['from_port'] in selected and r['to_port'] in selected]
            self.templates[role] = t
        self.air_roles = {}
        for role, surfaces in [('AIR_A',('ROCK','AIR')),('AIR_B',('AIR','ROCK'))]:
            hits=[]
            for e in self.entries.values():
                ports={p['id']:p for p in e['ports']}
                for r in e['routes']:
                    a,b=ports[r['from']],ports[r['to']]
                    if (a['surface'],b['surface'])==surfaces and a['face'] in ('LEFT','RIGHT') and b['face'] in ('LEFT','RIGHT'):
                        hits.append(dict(module_id=e['id'],route_id=r['id']))
            self.air_roles[role]=hits
        # No template invents AIR routes or moves top/bottom interfaces sideways.

    def adapt(self, key, e, aliases):
        if e['blockSize'] != 128: raise ValueError('block_size_mismatch:'+e['id'])
        compiled = read(self.root/e['compiled'])
        if e['reward_sites'] != compiled.get('reward_sites',[]): raise ValueError('reward_site_export_mismatch:'+e['id'])
        ports=[]
        for p in e['ports']:
            xy=p['position']; xy=[xy['x'],xy['y']] if isinstance(xy,dict) else xy
            loc=[(xy[k]-e['bounds'][axis])/64 for k,axis in enumerate(('x','y'))]
            if any(n!=round(n) for n in loc): raise ValueError('non_block_port:'+e['id']+':'+p['id'])
            ports.append(dict(id=aliases.get(p['id'],p['id']),source_port_id=p['id'],
                face=p['face'],surface=p['surface'],permission=p['permission'],
                local2=[int(n)for n in loc],closure='gear-seal/1'))
        pp={p['id']:p for p in ports}
        if len(pp)!=len(ports): raise ValueError('duplicate_port_alias')
        objects={o['id']:o for o in read(self.root/e['scene'].replace('module.tscn','module.mapnote.json'))['objects']}
        rewards={s['id']for s in e['reward_sites']}; routes=[]
        for r in e['routes']:
            a,b=aliases.get(r['from'],r['from']),aliases.get(r['to'],r['to'])
            if a not in pp or b not in pp: raise ValueError('unknown_route_port:'+e['id']+':'+r['id'])
            required=r.get('resourceProfile',{}).get('requiredRewards',[])
            if not set(required)<=rewards: raise ValueError('unknown_route_reward:'+e['id']+':'+r['id'])
            caps=['recoil' if v=='shot_recoil' else v for v in r['validation']['availableAbilities'] if v!='move']
            points=objects.get(r.get('pathObjectId'),{}).get('points',[])
            routes.append(dict(id=r['id'],from_port=a,to_port=b,
                displacement=[(pp[b]['local2'][k]-pp[a]['local2'][k])/2 for k in (0,1)],
                required_abilities=caps,action_tags=r.get('actionTags',[]),
                difficulty=r['difficulty'].get('score'),resource_profile=r.get('resourceProfile',{}),
                validation=r['validation'],reward_ids=required,
                path_points=[[p['x']-e['bounds']['x'],p['y']-e['bounds']['y']]for p in points]))
        # Internal ABI for the frozen solver, always True. The package exports
        # no per-module mirror eligibility gate; every base has two orientations.
        return dict(id=key,name=e['title'],size_blocks=e['sizeBlocks'],ports=ports,routes=routes,
            all_ports=ports,all_routes=routes,
            allow_mirror_x=True,reward=False,source_module_id=e['id'],content_version=e['contentVersion'],
            scene=e['scene'],scene_origin_offset=e['sceneOriginOffsetPixels'],
            compiled_content=compiled,source_bounds=e['bounds'])

    def install(self):
        model.LIB.clear(); model.LIB.update(self.templates)

    def decorate(self, items):
        used=set()
        for (a,ap,_),(b,bp,_)in legacy.connection_groups(items):used.update(((a['id'],ap),(b['id'],bp)))
        notes=[]; blockers=[]
        for i in items:
            t=self.templates[i['module_id']];e=self.entries[t['source_module_id']]
            i['solver_port_ids']=list(i['ports'])
            full=model.placed_ports(dict(t,ports=t['all_ports']),*i['origin'],i['mirror_x'])
            for pid,p in i['ports'].items():full[pid].update(p)
            i['ports']=full
            i.update(source_module_id=e['id'],content_version=e['contentVersion'],scene=e['scene'],
                scene_origin_offset=e['sceneOriginOffsetPixels'],source_bounds=e['bounds'])
            i['content']=materialize(t,i['mirror_x'])
            i['connected_port_ids']=[pid for pid in i['ports']if(i['id'],pid)in used]
            i['sealed_ports']=[gear_seal(p,i['size_blocks'])for pid,p in i['ports'].items()if(i['id'],pid)not in used]
            closed={s['port_id']for s in i['sealed_ports']};effective=[]
            for r0 in t['all_routes']:
                r=copy.deepcopy(r0)
                if i['mirror_x']:
                    r['displacement'][0]*=-1
                    r['path_points']=[[i['size_blocks'][0]*128-x,y]for x,y in r['path_points']]
                if r['from_port']in closed or r['to_port']in closed or not set(r['required_abilities'])<=model.ABILITIES:continue
                effective.append(r)
                base=dict(instance=i['id'],module_id=e['id'],route_id=r['id'])
                if not model.permitted(i['ports'][r['from_port']],'in')or not model.permitted(i['ports'][r['to_port']],'out'):
                    blockers.append(dict(**base,reason='route_violates_initial_permission'))
                if set(r['required_abilities'])!=model.ABILITIES:
                    notes.append(dict(**base,reason='available_ability_superset_not_physically_witnessed',witnessed=r['required_abilities']))
                if r['validation'].get('testNeighborFixtures'):
                    blockers.append(dict(**base,reason='external_neighbor_fixture_not_bound',fixtures=r['validation']['testNeighborFixtures']))
                if len(r['path_points'])<2:
                    blockers.append(dict(**base,reason='missing_author_path_for_seal_clearance'))
                for s in i['sealed_ports']:
                    x,y,w,h=s['rect_pixels'];expanded=[x-12,y-18,w+24,h+36]
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


def audit(items):
    """Validate every layout, including those rejected inside legacy assemble."""
    from collections import defaultdict,deque
    occupied=set();graph=defaultdict(list);reward_nodes=[];blockers=[]
    used=set();ids={i['id']:i for i in items}
    for i in items:
        x,y=i['origin'];w,h=i['size_blocks']
        assert all(type(n)is int for n in(x,y,w,h))
        for bx in range(x,x+w):
            for by in range(y,y+h):
                assert(bx,by)not in occupied,('overlap',i['id'],bx,by)
                occupied.add((bx,by))
        for pid,p in i['ports'].items():
            u,v=p['local2'];f=p['face']
            assert p['world2']==[2*x+u,2*y+v]
            if f in('LEFT','RIGHT'):assert u==(0 if f=='LEFT'else 2*w)and v%2==1 and 0<v<2*h
            else:assert v==(0 if f=='TOP'else 2*h)and u%2==1 and 0<u<2*w
            assert p['surface']!='ROCK'or f in('LEFT','RIGHT')
            assert not(p['surface']=='AIR'and f=='BOTTOM'and model.permitted(p,'in'))
        closed={s['port_id']for s in i['sealed_ports']}
        assert set(i['ports'])==set(i['connected_port_ids'])|closed
        assert not set(i['connected_port_ids'])&closed
        for s in i['sealed_ports']:
            sx,sy,sw,sh=s['rect_pixels'];assert 0<=sx<sx+sw<=w*128 and 0<=sy<sy+sh<=h*128
        for r in i['effective_routes']:
            assert r['from_port']not in closed and r['to_port']not in closed
            a=i['ports'][r['from_port']]['world2'];b=i['ports'][r['to_port']]['world2']
            assert r['displacement']==[(b[k]-a[k])/2 for k in(0,1)]
            chain=[i['id']+'.'+r['from_port']+':arrive']
            if i['reward'] and r['reward_ids']:
                node=i['id']+':reward:'+r['id'];chain.append(node)
                reward_nodes.append(dict(node=node,instance=i['id'],module_id=i['source_module_id'],route_id=r['id'],reward_ids=r['reward_ids'],target=True))
            else:
                for rid in r['reward_ids']:
                    node=i['id']+':reward:'+r['id']+':'+rid;chain.append(node)
                    reward_nodes.append(dict(node=node,instance=i['id'],module_id=i['source_module_id'],route_id=r['id'],reward_ids=[rid],target=False))
            chain.append(i['id']+'.'+r['to_port']+':depart')
            for a,b in zip(chain,chain[1:]):graph[a].append(b)
    for(a,ap,p),(b,bp,q)in configured_connections(items):
        for item,pid in((a,ap),(b,bp)):
            assert(item['id'],pid)not in used;used.add((item['id'],pid))
        if model.permitted(p,'out')and model.permitted(q,'in'):graph[a['id']+'.'+ap+':depart'].append(b['id']+'.'+bp+':arrive')
        if model.permitted(q,'out')and model.permitted(p,'in'):graph[b['id']+'.'+bp+':depart'].append(a['id']+'.'+ap+':arrive')
    graph['START'].append('M01.R:depart')
    boss=next((i for i in items if i['module_id']=='BOSS'),None)
    if boss:graph[boss['id']+'.L:arrive'].append('BOSS')
    def reach(start):
        seen={start};queue=deque([start])
        while queue:
            for n in graph[queue.popleft()]:
                if n not in seen:seen.add(n);queue.append(n)
        return seen
    seen=reach('START')
    if not boss:blockers.append(dict(reason='boss_not_placed'))
    elif 'L'not in boss['connected_port_ids']:
        blockers.append(dict(reason='boss_declared_entry_not_connected',instance=boss['id'],module_id=boss['source_module_id'],connected_ports=boss['connected_port_ids']))
    if 'BOSS'not in seen:blockers.append(dict(reason='boss_unreachable'))
    for i in items:
        if not i['reward']:continue
        ns=[r for r in reward_nodes if r['instance']==i['id']and r['node']in seen]
        if not ns:blockers.append(dict(reason='target_reward_unreachable',instance=i['id'],module_id=i['source_module_id']))
        for r in ns:
            if 'BOSS'not in reach(r['node']):blockers.append(dict(reason='target_reward_cannot_continue_to_boss',**r))
    reward_count=sum(i['reward']for i in items)
    if reward_count!=6:blockers.append(dict(reason='reward_target_not_met',expected=6,actual=reward_count))
    reached={n.split('.')[0].split(':')[0]for n in seen}
    missing=[dict(instance=i['id'],module_id=i['source_module_id'])for i in items if i['id']not in reached]
    if missing:blockers.append(dict(reason='unreachable_instances',instances=missing))
    for r in reward_nodes:r['reachable']=r['node']in seen;r['can_continue_to_boss']='BOSS'in reach(r['node'])
    return dict(geometry='PASS',gear_seal_coverage='PASS',boss_reachable='BOSS'in seen,
        target_reward_instances=reward_count,all_reward_sites=sum(len(i['reward_sites'])for i in items),
        route_reward_nodes=reward_nodes,unreachable_instances=missing,
        blockers=blockers,edges=[[a,b]for a in sorted(graph)for b in graph[a]])


def configured_connections(items):
    """Exclude source Ports explicitly sealed by a terminal configuration."""
    views=[dict(i,ports={pid:p for pid,p in i['ports'].items()if pid in i.get('solver_port_ids',i['ports'])})for i in items]
    return legacy.connection_groups(views)


def placement_diagnosis(gen, role):
    """Explain current frontier exhaustion without retrying or consuming RNG."""
    rows=[]; mids={k for k in model.LIB if k.startswith('Q')} if role=='reward' else {'BOSS'}
    for source,pid,p in gen.frontier():
        eligible=source['module_id']!='START'
        if role=='reward':eligible=eligible and not source['reward'] and source['module_id']!='BOSS'
        candidates=[]
        for mid,mx,pin,local in gen.index[model.OPPOSITE[p['face']],p['surface']]:
            if mid not in mids:continue
            delta=[p['world2'][k]-local['local2'][k]for k in(0,1)]
            if any(n%2 for n in delta):continue
            item=legacy.make(mid,*[n//2 for n in delta],mx)
            if not legacy.matching(p,item['ports'][pin]):continue
            overlap=[dict(instance=i['id'],module_id=model.LIB[i['module_id']]['source_module_id'])for i in gen.items if model.overlap(item,i)]
            candidates.append(dict(module_id=model.LIB[mid]['source_module_id'],role_alias=mid,mirror_x=mx,
                port_id=pin,origin=item['origin'],overlaps=overlap))
        rows.append(dict(source_instance=source['id'],source_module=model.LIB[source['module_id']]['source_module_id'],
            port_id=pid,face=p['face'],surface=p['surface'],world2=p['world2'],eligible_source=eligible,
            fitting_count=sum(not c['overlaps']for c in candidates),candidates=candidates,
            reason='source_excluded_by_original_role_rule' if not eligible else 'no_matching_interface' if not candidates else 'all_matching_placements_overlap' if all(c['overlaps']for c in candidates) else 'fitting_candidates'))
    return dict(role=role,frontiers=rows,eligible_fitting_candidates=sum(r['fitting_count']for r in rows if r['eligible_source']))
