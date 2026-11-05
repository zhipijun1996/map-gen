"""Verify the joint macro and three core paths independently in exported data."""
from structure_routes.tools.audit import inspect as base_audit
from branch_routes.tools.audit_branches import inspect as branch_audit
from collections import deque

def inspect(result):
    checked=base_audit(result);branch_audit(result)
    m=result['map'];d=result['diagnostics']['details'];macro=d['joint_macro']
    assert macro['reward_instance']==next(b['reward_instance_id'] for b in d['reward_branches'] if b['kind']=='forward_merge')
    assert macro['entry_instance']!=macro['merge_instance']
    rank=d['reward_core_rank'];assert rank[macro['merge_instance']]>rank[macro['entry_instance']]
    branches={i for b in d['reward_branches'] for i in b['instance_ids']}
    assert not branches&set(macro['bypass_instances'])
    nodes={n['id']:n for n in m['graph']['nodes'] if n['instance_id'] not in branches};g={n:[] for n in nodes}
    for a,b in m['graph']['edges']:
        if a in g and b in g:g[a].append(b)
    start=next(n for n,v in nodes.items() if v['kind']=='start');boss=next(n for n,v in nodes.items() if v['kind']=='boss')
    # Preserve the legacy distinct instance-sequence path semantics, excluding
    # every reward branch so the new macro cannot supply a free third core path.
    todo=[set()];paths=[];seen_sequences=set()
    while todo and len(paths)<m['inputs']['config']['goals']['main_paths_required']:
        skipped=todo.pop(0);q=deque([start]);parent={start:None}
        while q and boss not in parent:
            a=q.popleft()
            for b in g[a]:
                if (a,b) not in skipped and b not in parent:parent[b]=a;q.append(b)
        if boss not in parent:continue
        path=[];cur=boss
        while cur is not None:path.append(cur);cur=parent[cur]
        path.reverse();seq=tuple(dict.fromkeys(nodes[n]['instance_id'] for n in path))
        if seq in seen_sequences:continue
        seen_sequences.add(seq);paths.append(path)
        for a,b in zip(path,path[1:]):
            if nodes[a]['kind']=='port_depart' and nodes[b]['kind']=='port_arrive' and nodes[a]['instance_id']!=m['anchors']['start_departure']['instance_id']:todo.append(skipped|{(a,b)})
    assert len(paths)>=m['inputs']['config']['goals']['main_paths_required']
    return checked|dict(core_paths=len(paths),joint_macro=True,scope='independent exported graph, strict style, true core routes; no physics/irreversibility proof')
