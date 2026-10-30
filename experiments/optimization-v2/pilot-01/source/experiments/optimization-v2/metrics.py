"""Deterministic actual-graph paths and explicit spatial acceptance gates."""
from collections import defaultdict,deque


def actual_paths(edges):
    graph=defaultdict(list)
    for a,b in edges:graph[a].append(b)
    paths=[];sequences=set();skips=[set()]
    while skips and len(paths)<3:
        skip=skips.pop(0);previous={'START':None};queue=deque(['START'])
        while queue:
            at=queue.popleft()
            for node in graph[at]:
                if (at,node)not in skip and node not in previous:previous[node]=at;queue.append(node)
        if 'BOSS'not in previous:continue
        path=[];at='BOSS'
        while at is not None:path.append(at);at=previous[at]
        path.reverse();seq=tuple(dict.fromkeys(n.split('.')[0].split(':')[0]for n in path))
        if seq in sequences:continue
        sequences.add(seq);paths.append(path)
        for a,b in zip(path,path[1:]):
            if a.endswith(':depart')and b.endswith(':arrive')and not a.startswith('M01.'):
                skips.append(skip|{(a,b)})
    return paths


def shape_metrics(items):
    x0=min(i['origin'][0]for i in items);y0=min(i['origin'][1]for i in items)
    x1=max(i['origin'][0]+i['size_blocks'][0]for i in items);y1=max(i['origin'][1]+i['size_blocks'][1]for i in items)
    w,h=x1-x0,y1-y0
    area=sum(i['size_blocks'][0]*i['size_blocks'][1]for i in items)
    return dict(bounds_blocks=[x0,y0,x1,y1],width=w,height=h,aspect=max(w/h,h/w),occupancy=area/(w*h))


def quality(items,paths,static_pass,cfg):
    m=shape_metrics(items);reward_count=sum(i['reward']for i in items)
    targets=static_pass and reward_count==cfg['reward_target'] and len(paths)>=cfg['main_paths_required']
    shape=m['aspect']<=cfg['shape']['max_aspect']
    return dict(**m,static_pass=static_pass,targets_pass=targets,shape_pass=shape,effect_pass=targets and shape,
        main_paths=len(paths),target_rewards=reward_count)
