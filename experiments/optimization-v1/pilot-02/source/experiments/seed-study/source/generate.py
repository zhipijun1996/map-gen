#!/usr/bin/env python3
"""Free 2D growth from exact boundary-Block ports. No rows, slots or lane anchors."""
import argparse, copy, json, math, random
from pathlib import Path
from collections import defaultdict, Counter, deque
from model import LIB, template, port, bidir, placed_ports, overlap, permitted, OPPOSITE, ABILITIES

def P(pid,face,block,w,h,surface=None,permission='INOUT'):
    surface=surface or ('ROCK' if face in ('LEFT','RIGHT') else 'ONE_WAY_PLATFORM')
    loc={'LEFT':[0,2*block+1],'RIGHT':[2*w,2*block+1],
         'TOP':[2*block+1,0],'BOTTOM':[2*block+1,2*h]}[face]
    return port(pid,face,loc,surface,permission)

def prepare_library():
    LIB.clear()
    shapes=[(2,3),(3,2),(4,3),(3,4),(5,3),(6,3),(3,6),(3,8),(7,2),
            (2,7),(4,5),(5,4),(6,5),(7,4),(4,7),(6,6),(8,3),(8,5)]
    for k,(w,h) in enumerate(shapes):
        for style in (0,1):
            mid=f'T{k+1:02}{"ab"[style]}'
            # Opposite faces intentionally have DIFFERENT offsets. No module midpoint rule.
            idx=[0,h-1,max(0,w-2),0] if style==0 else [h-1,0,0,w-1]
            pp=[P('L','LEFT',idx[0],w,h),P('R','RIGHT',idx[1],w,h),
                P('U','TOP',idx[2],w,h),P('D','BOTTOM',idx[3],w,h)]
            pairs=[('L','R'),('L','U'),('R','U'),('L','D'),('R','D')]
            if h>=5:
                # Two ports on one side at different boundary Blocks.
                pp.append(P('L2','LEFT',h//2,w,h))
                pairs += [('L2','R'),('L2','U'),('L2','D')]
            if w>=6:
                pp.append(P('U2','TOP',w//2,w,h))
                pairs += [('U2','L'),('U2','R'),('U2','D')]
            ability=['jump','recoil','grapple','double_jump'][k%4]
            name=('窄竖井' if h/w>=2 else '横向动作链' if w/h>=2 else '大空间' if w*h>=30 else '错层枢纽')
            template(mid,name,w,h,pp,bidir(pairs),ability,2+k%3)
    template('START','起点',5,4,[P('R','RIGHT',0,5,4)],[],mirror=False)
    template('BOSS','Boss',9,7,[P('L','LEFT',5,9,7)],[],mirror=True)
    # Reward single-port self-loop fixtures: all four faces and variable shapes.
    for face in ('LEFT','RIGHT','TOP','BOTTOM'):
        for k,(w,h) in enumerate([(3,2),(2,4),(4,3)]):
            n=(h if face in ('LEFT','RIGHT') else w)-1
            template(f'Q{face[0]}{k}','奖励折返',w,h,[P('P',face,n,w,h)],
                     [('P','P')],reward=True)
    # AIR loop leg; A enters ROCK and exits AIR, B enters AIR and exits ROCK.
    template('AIR_A','反冲跃出',4,5,[P('L','LEFT',4,4,5,permission='INPUT'),
             P('A','RIGHT',1,4,5,'AIR','OUTPUT')],[('L','A')],'recoil',4)
    template('AIR_B','空中接入',3,4,[P('A','LEFT',2,3,4,'AIR','INPUT'),
             P('R','RIGHT',0,3,4,permission='OUTPUT')],[('A','R')],'grapple',4)

def make(mid,x,y,mirror=False,iid=None):
    t=LIB[mid]
    return dict(id=iid,module_id=mid,name=t['name'],origin=[x,y],size_blocks=t['size_blocks'],
                mirror_x=mirror,ports=placed_ports(t,x,y,mirror),reward=t['reward'])

def matching(a,b):
    return a['world2']==b['world2'] and OPPOSITE[a['face']]==b['face'] and a['surface']==b['surface'] and (
        permitted(a,'out') and permitted(b,'in') or permitted(b,'out') and permitted(a,'in'))

def bounds(items):
    return [min(i['origin'][0] for i in items),min(i['origin'][1] for i in items),
            max(i['origin'][0]+i['size_blocks'][0] for i in items),max(i['origin'][1]+i['size_blocks'][1] for i in items)]

class Generator:
    def __init__(self,seed):
        self.seed=seed;self.rng=random.Random(seed);self.items=[];self.expanded=0
        self.local={};self.index=defaultdict(list)
        for mid,t in LIB.items():
            for mx in ((False,True) if t['allow_mirror_x'] else (False,)):
                ps=placed_ports(t,0,0,mx);self.local[mid,mx]=ps
                for pid,p in ps.items():self.index[p['face'],p['surface']].append((mid,mx,pid,p))
    def add(self,item):
        item['id']=f'M{len(self.items)+1:02}';self.items.append(item);return item
    def frontier(self,items=None):
        its=items if items is not None else self.items
        groups=defaultdict(list)
        for i in its:
            for pid,p in i['ports'].items():groups[tuple(p['world2'])].append((i,pid,p))
        return [(i,pid,p) for group in groups.values() for i,pid,p in group
                if not any(ii['id']!=i['id'] and matching(p,q) for ii,_,q in group)]
    def candidates(self,source,mids=None,items=None):
        items=self.items if items is None else items;_,_,p=source
        pool=self.index[OPPOSITE[p['face']],p['surface']]
        for mid,mx,pid,local in pool:
            if mids is not None and mid not in mids:continue
            delta=[p['world2'][d]-local['local2'][d] for d in (0,1)]
            if any(n%2 for n in delta):continue
            x,y=[n//2 for n in delta];self.expanded+=1
            item=make(mid,x,y,mx)
            if any(overlap(item,i) for i in items):continue
            if not matching(p,item['ports'][pid]):continue
            yield item,pid
    def grow(self,count=32):
        self.add(make('START',0,0))
        mids={m for m in LIB if m.startswith('T')};used=Counter()
        while len(self.items)<count:
            front=self.frontier();self.rng.shuffle(front);front=front[:22]
            old=bounds(self.items);area=(old[2]-old[0])*(old[3]-old[1]);lookup=defaultdict(list)
            for _,_,p in self.frontier():lookup[tuple(p['world2'])].append(p)
            options=[];seen=set()
            for src in front:
                for item,_ in self.candidates(src,mids):
                    key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
                    if key in seen:continue
                    seen.add(key)
                    auto=sum(any(matching(p,q) for q in lookup[tuple(p['world2'])]) for p in item['ports'].values())
                    x,y=item['origin'];w,h=item['size_blocks']
                    newarea=(max(old[2],x+w)-min(old[0],x))*(max(old[3],y+h)-min(old[1],y))
                    # Pack a varied connected region, without preassigned origins or rows.
                    score=24*(auto-1)-.055*(newarea-area)-5*used[item['module_id']]
                    score-=.10*max(0,-x)+.025*abs(y)
                    score+=self.rng.uniform(-3,3)
                    options.append((score,item))
            if not options:raise RuntimeError('growth exhausted')
            options.sort(key=lambda x:x[0],reverse=True)
            chosen=options[self.rng.randrange(min(5,len(options)))][1]
            self.add(chosen);used[chosen['module_id']]+=1
    def close_one(self,max_depth=3):
        """Bounded beam search between existing frontiers. No invented connector geometry."""
        fronts=self.frontier();self.rng.shuffle(fronts)
        viable=[f for f in fronts if not f[0]['reward'] and f[0]['module_id']!='START']
        mids={m for m in LIB if m.startswith('T')}
        for source in viable[:24]:
            targets=[t for t in viable if t[0]['id']!=source[0]['id'] and
                     sum(abs(t[2]['world2'][k]-source[2]['world2'][k]) for k in (0,1))<40]
            if not targets:continue
            beam=[([],source)]
            for depth in range(max_depth):
                states=[]
                for chain,front in beam:
                    for item,pin in self.candidates(front,mids,self.items+chain):
                        item['id']=f'tmp{depth}'
                        for opid,p in item['ports'].items():
                            if opid==pin:continue
                            for target in targets:
                                if matching(p,target[2]):
                                    for c in chain+[item]:self.add(c)
                                    return True
                            dist=min(sum(abs(p['world2'][k]-t[2]['world2'][k]) for k in (0,1)) for t in targets)
                            if dist<32:states.append((dist+self.rng.random()*2,chain+[item],(item,opid,p)))
                states.sort(key=lambda x:x[0]);beam=[(chain,f) for _,chain,f in states[:18]]
                if not beam:break
        return False
    def add_air_loop(self):
        # Search an already available ROCK frontier, then require a real reconnection.
        basefront=self.frontier();self.rng.shuffle(basefront)
        for source in basefront:
            if source[2]['surface']!='ROCK' or not permitted(source[2],'out'):continue
            for a,pin in self.candidates(source,{'AIR_A'}):
                a['id']='airtmpA'
                air=next((pid,p) for pid,p in a['ports'].items() if p['surface']=='AIR')
                for b,bpin in self.candidates((a,*air),{'AIR_B'},self.items+[a]):
                    b['id']='airtmpB'
                    out=next((pid,p) for pid,p in b['ports'].items() if p['surface']=='ROCK')
                    # Extend from B into a target old frontier with bounded search.
                    targets=[t for t in basefront if t[0]['id']!=source[0]['id']]
                    mids={m for m in LIB if m.startswith('T')}
                    for c,cpin in self.candidates((b,*out),mids,self.items+[a,b]):
                        if any(matching(p,t[2]) for pid,p in c['ports'].items() if pid!=cpin for t in targets):
                            self.add(a);self.add(b);self.add(c);return True
        return False
    def finish(self):
        # Place boss on a distant outward frontier, rather than fixing a coordinate.
        graph=defaultdict(set)
        for group in connection_groups(self.items):
            (a,_,_),(b,_,_)=group;graph[a['id']].add(b['id']);graph[b['id']].add(a['id'])
        dist={'M01':0};q=deque(['M01'])
        while q:
            current=q.popleft()
            for n in sorted(graph[current]):
                if n not in dist:dist[n]=dist[current]+1;q.append(n)
        opts=[]
        for src in self.frontier():
            if src[0]['module_id']=='START':continue
            for item,_ in self.candidates(src,{'BOSS'}):
                score=math.hypot(*item['origin'])+dist.get(src[0]['id'],0)*.4
                opts.append((score,item))
        if not opts:raise RuntimeError('boss cannot fit')
        self.add(max(opts,key=lambda p:p[0])[1])
        for n in range(6):
            opts=[]
            for src in self.frontier():
                if src[0]['reward'] or src[0]['module_id'] in ('START','BOSS'):continue
                for item,_ in self.candidates(src,{m for m in LIB if m.startswith('Q')}):
                    # Keep exactly one external interface and spread rewards across branches.
                    near=sum(math.hypot(item['origin'][0]-i['origin'][0],item['origin'][1]-i['origin'][1])<8 for i in self.items if i['reward'])
                    opts.append((self.rng.random()*4-near*5,item))
            if not opts:raise RuntimeError('reward cannot fit')
            self.add(max(opts,key=lambda p:p[0])[1])
        return assemble(self)
    def build(self):
        self.grow(32)
        for _ in range(3):self.close_one(3)
        self.air_connected=self.add_air_loop()
        return self.finish()

def connection_groups(items):
    groups=defaultdict(list)
    for i in items:
        for pid,p in i['ports'].items():groups[tuple(p['world2'])].append((i,pid,p))
    return [group for group in groups.values() if len(group)==2 and matching(group[0][2],group[1][2])]

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
        for r0 in LIB[i['module_id']]['routes']:
            r=copy.deepcopy(r0)
            if i['mirror_x']:r['displacement'][0]*=-1
            if r['from_port'] in i['closures'] or r['to_port'] in i['closures'] or not set(r['required_abilities'])<=ABILITIES:
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
    seen=search('START');assert 'BOSS' in seen
    for i in items:
        if i['reward']:
            nodes=[n for n in seen if n.startswith(i['id']+':reward:')]
            assert nodes and all('BOSS' in search(n) for n in nodes)
    paths=[];seenpaths=set();skips=[set()]
    while skips and len(paths)<3:
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
        i['lane']='reward' if i['reward'] else 'shared' if i['module_id'] in ('START','BOSS') else 'air' if i['module_id'].startswith('AIR') else LIB[i['module_id']]['routes'][0]['required_abilities'][0]
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
    return dict(schema='map-port-prototype/2',seed=gen.seed,block_pixels=128,available_abilities=sorted(ABILITIES),
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

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=271028);p.add_argument('--out',default=str(Path(__file__).parent/'output'))
    args=p.parse_args();prepare_library();g=Generator(args.seed);m=g.build();out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
    (out/'map.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
    (out/'module_library.json').write_text(json.dumps(LIB,ensure_ascii=False,indent=2))
    print(json.dumps(m['summary'],ensure_ascii=False,indent=2))
