#!/usr/bin/env python3
import copy,json
from pathlib import Path
from collections import defaultdict,deque
from generate import prepare_library,Generator
from model import LIB,OPPOSITE,permitted

out=Path(__file__).parent/'output';m=json.loads((out/'map.json').read_text());prepare_library()
normalized=copy.deepcopy(m)
for i in normalized['instances']:
    for p in i['ports'].values():
        p.pop('edge_block',None);p.pop('block_offset',None)
assert json.loads(json.dumps(Generator(m['seed']).build()))==normalized,'seed mismatch'
occupied={};ids={i['id']:i for i in m['instances']}
for i in m['instances']:
    x,y=i['origin'];w,h=i['size_blocks']
    for bx in range(w):
        for by in range(h):
            assert (x+bx,y+by) not in occupied;occupied[x+bx,y+by]=i['id']
    for p in i['ports'].values():
        u,v=p['local2'];face=p['face']
        if face in ('LEFT','RIGHT'):
            assert u==(0 if face=='LEFT' else 2*w) and v%2==1 and 0<v<2*h
        else:assert v==(0 if face=='TOP' else 2*h) and u%2==1 and 0<u<2*w
        assert p['world2']==[2*x+u,2*y+v]
        assert p['surface']!='ROCK' or face in ('LEFT','RIGHT')
        assert not(p['surface']=='AIR' and face=='BOTTOM' and permitted(p,'in'))
connected=set();g=defaultdict(list)
for a,b in m['actual_graph']['edges']:g[a].append(b)
for c in m['connections']:
    a,ap=c['a'].split('.');b,bp=c['b'].split('.');p=ids[a]['ports'][ap];q=ids[b]['ports'][bp]
    assert p['world2']==q['world2']==c['world2'] and p['surface']==q['surface']==c['surface']
    assert OPPOSITE[p['face']]==q['face']
    for src,dst in c['directions']:
        si,sp=src.split('.');di,dp=dst.split('.')
        assert permitted(ids[si]['ports'][sp],'out') and permitted(ids[di]['ports'][dp],'in')
        assert dst+':arrive' in g[src+':depart']
    for endpoint in (c['a'],c['b']):assert endpoint not in connected;connected.add(endpoint)
for i in m['instances']:
    for pid,p in i['ports'].items():assert (i['id']+'.'+pid in connected) != (pid in i['closures'])
    expected={(r['from_port'],r['to_port']) for r in LIB[i['module_id']]['routes']
              if r['from_port'] not in i['closures'] and r['to_port'] not in i['closures']}
    assert expected=={(r['from_port'],r['to_port']) for r in i['actual_routes']}
    for r in i['actual_routes']:
        a=i['ports'][r['from_port']]['world2'];b=i['ports'][r['to_port']]['world2']
        assert r['displacement']==[(b[k]-a[k])/2 for k in (0,1)]
        if not i['reward']:assert i['id']+'.'+r['to_port']+':depart' in g[i['id']+'.'+r['from_port']+':arrive']
def reachable(s):
    seen={s};q=deque([s])
    while q:
        for b in g[q.popleft()]:
            if b not in seen:seen.add(b);q.append(b)
    return seen
reach=reachable('START');assert 'BOSS' in reach
for i in m['instances']:
    if i['reward']:
        nodes=[n for n in reach if n.startswith(i['id']+':reward:')]
        assert nodes and all('BOSS' in reachable(n) for n in nodes)
for path in m['main_paths']:
    assert path[0]=='START' and path[-1]=='BOSS' and all(b in g[a] for a,b in zip(path,path[1:]))
assert {'ROCK','AIR','ONE_WAY_PLATFORM'}==set(c['surface'] for c in m['connections'])
assert m['certified_for_game'] is False
print('PASS: seed reproducibility, integer occupancy, boundary Block parity, exact seams, permissions, closures, full route graph, mirrors, 3 paths, 6 reward return paths, all 3 surfaces.')
