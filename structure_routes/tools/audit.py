"""Independently check the planned skeleton and growth identities in export."""
from collections import Counter,deque

def inspect(result):
    assert result['status']=='PASS'
    d=result['diagnostics']['details'];m=result['map'];by={i['id']:i for i in m['instances']}
    growth=d['growth_instance_ids'];assert len(growth)==m['inputs']['config']['goals']['growth_target']
    assert len(set(growth))==len(growth) and all(i in by for i in growth)
    assert by[growth[0]]['role']=='start'
    assert all(by[i]['role']=='traversal' for i in growth[1:])
    branches={i for b in d['reward_branches'] for i in b['instance_ids']}
    assert not set(growth)&branches
    assert Counter(b['kind'] for b in d['reward_branches'])==Counter(d['structure_plan']['reward_modes'])
    nodes={n['id']:n for n in m['graph']['nodes']};named={};g={n:[] for n in nodes}
    for a,b in m['graph']['edges']:g[a].append(b)
    for nid,n in nodes.items():
        if n['kind'].startswith('port_'):name=n['instance_id']+'.'+n['port_id']+':'+n['kind'].removeprefix('port_')
        elif n['kind']=='start':name='START'
        elif n['kind']=='boss':name='BOSS'
        elif n['kind']=='reward':name=n['instance_id']+':reward:'+n['route_id']+('' if n['target'] else ':'+n['reward_ids'][0])
        else:continue
        named[name]=nid
        if n['kind'].startswith('port_'):
            for anchor,canonical in [('start_departure','R'),('boss_arrival','L')]:
                ref=m['anchors'][anchor]
                if n['instance_id']==ref['instance_id'] and n['port_id']==ref['port_id']:
                    named[n['instance_id']+'.'+canonical+':'+n['kind'].removeprefix('port_')]=nid
    path=d['structure_path'];assert path[0]=='START' and path[-1]=='BOSS'
    for a,b in zip(path,path[1:]):
        left,right=named[a],named[b]
        if right in g[left]:continue
        # Export may materialize ordinary rewards on the same declared edge.
        iid=nodes[left]['instance_id'];assert iid==nodes[right]['instance_id']
        queue=deque([left]);seen={left}
        while queue:
            cur=queue.popleft()
            for nxt in g[cur]:
                if nxt not in seen and (nxt==right or nodes[nxt]['kind']=='reward' and nodes[nxt]['instance_id']==iid):seen.add(nxt);queue.append(nxt)
        assert right in seen,(a,b)
    return dict(status='PASS',growth=len(growth),planned_modes=d['structure_plan']['reward_modes'],skeleton_edges=len(path)-1,scope='actual export graph and identities; no physics')
