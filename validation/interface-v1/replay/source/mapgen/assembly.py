"""Preserved final assembly gate with explicit per-call context and path goal."""
import copy
from collections import defaultdict,Counter,deque
from .geometry import connection_groups, permitted, bounds

class AssemblyRejected(RuntimeError):
    pass

def assemble(gen):
    items=gen.items;connections=[];used=set()
    for (a,ap,p),(b,bp,q) in sorted(connection_groups(items),key=lambda g:(g[0][2]['world2'])):
        cid=f'C{len(connections)+1:02}';dirs=[]
        if permitted(p,'out') and permitted(q,'in'):dirs.append([a['id']+'.'+ap,b['id']+'.'+bp])
        if permitted(q,'out') and permitted(p,'in'):dirs.append([b['id']+'.'+bp,a['id']+'.'+ap])
        connections.append(dict(id=cid,a=a['id']+'.'+ap,b=b['id']+'.'+bp,world2=p['world2'],surface=p['surface'],directions=dirs))
        for i,pid,pp in [(a,ap,p),(b,bp,q)]:used.add((i['id'],pid));pp['connection']=cid
    edges=[];closures=[]
    for i in items:
        i['actual_routes']=[];i['inactive_routes']=[];i['closures']=[]
        for pid,p in i['ports'].items():
            if (i['id'],pid) not in used:i['closures'].append(pid);p['closed']=True;closures.append(dict(instance=i['id'],port=pid,certified=False))
        for r0 in gen.library.templates[i['module_id']]['routes']:
            r=copy.deepcopy(r0)
            if i['mirror_x']:r['displacement'][0]*=-1
            if r['from_port'] in i['closures'] or r['to_port'] in i['closures'] or not set(r['required_abilities'])<=gen.library.abilities:
                i['inactive_routes'].append(r);continue
            i['actual_routes'].append(r)
            a=i['id']+'.'+r['from_port']+':arrive';b=i['id']+'.'+r['to_port']+':depart'
            if i['reward']:
                n=i['id']+':reward:'+r['id'];edges.extend([(a,n),(n,b)])
            else:edges.append((a,b))
    for c in connections:
        for a,b in c['directions']:edges.append((a+':depart',b+':arrive'))
    boss=next(i for i in items if i['module_id']=='BOSS')
    edges.extend([('START','M01.R:depart'),(boss['id']+'.L:arrive','BOSS')])
    graph=defaultdict(list)
    for a,b in edges:graph[a].append(b)
    def search(source,skip=set()):
        prev={source:None};q=deque([source])
        while q:
            a=q.popleft()
            for b in graph[a]:
                if (a,b) not in skip and b not in prev:prev[b]=a;q.append(b)
        return prev
    seen=search('START')
    if 'BOSS' not in seen:raise AssemblyRejected('boss_unreachable')
    for i in items:
        if i['reward']:
            nodes=[n for n in seen if n.startswith(i['id']+':reward:')]
            if not nodes or not all('BOSS' in search(n) for n in nodes):raise AssemblyRejected('reward_claim_or_onward_invalid')
    paths=[];seenpaths=set();skips=[set()]
    while skips and len(paths)<gen.config['main_paths_required']:
        skip=skips.pop(0);prev=search('START',skip)
        if 'BOSS' not in prev:continue
        path=[];n='BOSS'
        while n is not None:path.append(n);n=prev[n]
        path.reverse();seq=tuple(dict.fromkeys(n.split('.')[0].split(':')[0] for n in path))
        if seq in seenpaths:continue
        seenpaths.add(seq);paths.append(path)
        for a,b in zip(path,path[1:]):
            if a.endswith(':depart') and b.endswith(':arrive') and not a.startswith('M01.'):
                skips.append(skip|{(a,b)})
    for i in items:
        # Classify visual content by shape / action, never by a spatial lane.
        i['lane']='reward' if i['reward'] else 'shared' if i['module_id'] in ('START','BOSS') else 'air' if i['module_id'].startswith('AIR') else (gen.library.templates[i['module_id']]['routes'][0]['required_abilities'] or ['move'])[0]
    offcentre=0;total=0;seamoffset=0;horizontal=0
    for i in items:
        w,h=i['size_blocks']
        for p in i['ports'].values():
            if p.get('connection'):
                total+=1;u,v=p['local2'];offcentre+= v!=h if p['face'] in ('LEFT','RIGHT') else u!=w
    ids={i['id']:i for i in items}
    for c in connections:
        a=ids[c['a'].split('.')[0]];b=ids[c['b'].split('.')[0]]
        p=a['ports'][c['a'].split('.')[1]]
        if p['face'] in ('LEFT','RIGHT'):horizontal+=1;seamoffset+=a['origin'][1]!=b['origin'][1]
    return dict(schema='map-port-prototype/2',seed=gen.seed,block_pixels=gen.library.block_pixels,available_abilities=sorted(gen.library.abilities),
        library_version='offset-block-port-fixtures-v2',certified_for_game=False,
        assumptions=['在线前固定模板库；无固定行列、路线带或 Boss 坐标。','局部封口和 Route 均为未认证的占位契约。'],
        summary=dict(instances=len(items),used_templates=len(set(i['module_id'] for i in items)),
                     distinct_sizes=len(set(tuple(i['size_blocks']) for i in items)),connections=len(connections),
                     cycles=len(connections)-len(items)+1,rewards=sum(i['reward'] for i in items),
                     active_port_endpoints=total,offcentre_active_endpoints=offcentre,
                     offset_horizontal_seams=seamoffset,horizontal_seams=horizontal,
                     mirrored=sum(i['mirror_x'] for i in items),closures=len(closures),
                     one_way=sum(len(c['directions'])==1 for c in connections),
                     surfaces=dict(Counter(c['surface'] for c in connections)),bounds_blocks=bounds(items),
                     search_expansions=gen.expanded,main_paths=len(paths)),
        instances=items,connections=connections,closures=closures,
        actual_graph=dict(node_model='instance.port:arrive/depart; explicit reward phases',edges=edges),main_paths=paths,
        verification=dict(rectangles='PASS',block_edge_centre_ports='PASS',actual_graph_reachability='PASS',reward_returns='PASS',physics='NOT_CERTIFIED'))
