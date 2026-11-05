"""Independent Python geometry/graph checks, not a gameplay or physical-route proof."""
import collections, math, json, gzip, argparse
from pathlib import Path
from map_additions.tools.setup import ROOT
from route_construction.tools.report import source,read

def overlap(a,b):return a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]
def expand(r,x,y):return [r[0]-x,r[1]-y,r[2]+2*x,r[3]+2*y]
def move(r,o):return [r[0]+o[0],r[1]+o[1],*r[2:]]
def swept(a,b,r=0):return [min(a[0],b[0])-r,min(a[1],b[1])-r,abs(a[0]-b[0])+2*r,abs(a[1]-b[1])+2*r]
def point(p,r):return [p[0]-r,p[1]-r,2*r,2*r]
def audit(base,out):
    m=base['map'];cfg=out['config'];unit=m['coordinates']['block_size_pixels'];half=m['inputs']['request']['player']['clearance_half_extents_pixels'];items={i['id']:i for i in m['instances']};contents=base['content_store'];nodes={n['id']:n for n in m['graph']['nodes']};g=collections.defaultdict(list)
    for a,b in m['graph']['edges']:g[a].append(b)
    def walk(begin,blocked=None):
        d={begin:0};q=collections.deque([begin])
        while q:
            at=q.popleft()
            for nxt in g[at]:
                if nodes[nxt]['instance_id']!=blocked and nxt not in d:d[nxt]=d[at]+1;q.append(nxt)
        return d
    reached=walk(next(n for n,v in nodes.items() if v['kind']=='start'));pn={(n['instance_id'],n.get('port_id'),n['kind']):nid for nid,n in nodes.items()};solids=[];danger=[];protect=[];floors=[]
    for iid,i in items.items():
        o=[v*unit for v in i['origin_blocks']];body=contents[i['content_ref']]
        def world(p):return [p[0]+o[0],p[1]+o[1]]
        for idx,r in enumerate(body.get('platforms',[])):
            r=move(r,o);solids.append(r)
            if idx not in body.get('wall_platform_indices',[]):floors.append(r)
        solids.extend(move(s['rect_pixels'],o) for s in i['seals'])
        for r in body.get('hazards',[]):
            if isinstance(r,list) and len(r)==4:danger.append(move(r,o))
        for s in body.get('saws',[]):
            a=world(s['origin']);t=s.get('travel',[0,0]);danger.append(swept(a,[a[0]+t[0],a[1]+t[1]],s.get('radius',24)))
        for gr in body.get('retractable_groups',[]):danger.extend(move(b['rect'],o) for b in gr.get('bands',[]) if 'rect' in b)
        for mp in body.get('moving_platforms',[]):danger.append(expand(swept(world(mp['start']),world(mp['finish'])),*mp.get('size',[128,32])))
        for l in body.get('latches',[]):
            danger.extend(move(l[k],o) for k in ['gate','paired_gate'] if k in l)
            if 'bell' in l:danger.append(point(world(l['bell']),40))
        for t in body.get('thorns',[]):
            if isinstance(t,dict) and 0<=t.get('platform_index',-1)<len(body.get('platforms',[])):danger.append(expand(move(body['platforms'][t['platform_index']],o),t.get('depth',16),t.get('depth',16)))
        if body.get('hooks') or any(not isinstance(r,list) or len(r)!=4 for r in body.get('hazards',[])):danger.append([*o,*[v*unit for v in i['size_blocks']]])
        protect.extend(expand(point(world(p['local_position_pixels']),32),*half) for p in i['ports'])
        for r in i['routes']:protect.extend(expand(swept(world(a),world(b)),*half) for a,b in zip(r['author_path_pixels'],r['author_path_pixels'][1:]))
        protect.extend(expand(move(s['region'],o),*half) for s in body.get('reward_sites',[]) if 'region' in s)
        if i['role'] in ['start','boss']:protect.append(expand([*o,*[v*unit for v in i['size_blocks']]],32,32))
    checks={}
    checks['bound_source']=out['source_map_id']==m['map_id'] and out['validation']['base_map_unchanged']
    checks['ids_unique']=len({s['id'] for s in out['signs']})==len(out['signs']) and len({s['id'] for s in out['moving_saws']})==len(out['moving_saws'])
    expected=set()
    for iid,i in items.items():
        groups=collections.defaultdict(set)
        for r in i['routes']:
            if r['from_port'] in i['connected_port_ids'] and r['to_port'] in i['connected_port_ids'] and pn.get((iid,r['from_port'],'port_arrive')) in reached:groups[r['from_port']].add(r['to_port'])
        expected.update((iid,pid) for pid,exits in groups.items() if len(exits)>=2)
    actual=[];routing_ok=True;placement_ok=True
    for board in out['signs']:
        i=items[board['instance_id']];o=[x*unit for x in i['origin_blocks']];pos=board['position_pixels'];ip=board['interaction_position_pixels'];size=cfg['signage']['board_size_pixels'];box=[pos[0]-size[0]/2,pos[1]-size[1],*size];actor=[ip[0]-half[0],ip[1]-half[1],2*half[0],2*half[1]]
        placement_ok &= not any(overlap(box,r) or overlap(actor,r) for r in solids+danger)
        if board['mount']=='floor':placement_ok &= any(abs(r[1]-(ip[1]+half[1]))<1e-7 and r[0]+half[0]<=ip[0]<=r[0]+r[2]-half[0] for r in floors)
        else:placement_ok &= board['mount']=='suspended' and board['actor_stand_position_pixels'] is None and math.dist(ip,pos)<=cfg['signage']['interact_radius_pixels']
        for v in board['views']:
            actual.append((i['id'],v['arrival_port_id']));allcost=[]
            for d in v['directions']:
                routes=[r for r in i['routes'] if r['from_port']==v['arrival_port_id'] and r['to_port']==d['exit_port_id']];routing_ok &= bool(routes) and set(d['route_ids'])=={r['id'] for r in routes}
                seen=walk(pn[(i['id'],d['exit_port_id'],'port_depart')],i['id']);local={'chest:'+i['id']+':'+rid for r in routes for rid in r['required_reward_ids']};cost={tid:min(seen[n] for n in t['node_ids'] if n in seen) for tid,t in out['targets'].items() if any(n in seen for n in t['node_ids'])};cost.update({tid:0 for tid in local});allcost.append(cost)
                routing_ok &= set(d['categories'])=={out['targets'][tid]['kind'] for tid in d['targets']} and set(d['categories'])<={'chest','shop','boss'} and all(tid in cost for tid in d['targets'])
            for d,cost in zip(v['directions'],allcost):
                for tid in d['targets']:
                    if out['targets'][tid]['kind']!='boss':routing_ok &= cost[tid]==min(c.get(tid,math.inf) for c in allcost)
            for tid in v['shared_targets']:routing_ok &= len({c.get(tid,math.inf) for c in allcost})==1 and tid in allcost[0]
    actual.extend((g['instance_id'],g['arrival_port_id']) for g in out['gaps']);checks['fork_accounting']=len(actual)==len(set(actual)) and set(actual)==expected and out['stats']['decisions']==len(expected);checks['routing_references']=bool(routing_ok);checks['static_board_clearance']=bool(placement_ok)
    saws=out['moving_saws'];cfg=cfg['moving_saws'];gear_ok=True;density=True;alignment=True
    for s in saws:
        a=s['origin'];b=[a[n]+s['travel'][n] for n in range(2)];env=swept(a,b,s['radius']);ex=expand(env,half[0]+cfg['margin_pixels'],half[1]+cfg['margin_pixels']);gear_ok &= env==s['swept_envelope_pixels'] and ex==s['protected_envelope_pixels'] and not any(overlap(ex,r) for r in solids+danger+protect) and cfg['min_travel_pixels']<=math.dist(a,b)<=cfg['max_travel_pixels'] and s['radius']==cfg['radius_pixels']
        for board in out['signs']:gear_ok &= not overlap(ex,point(board['interaction_position_pixels'],out['config']['signage']['interact_radius_pixels']))
        density &= sum(math.dist(s['center_pixels'],t['center_pixels'])<cfg['density_radius_pixels'] for t in saws)<=cfg['max_local_groups']
        for t in saws:
            if t['id']!=s['id']:gear_ok &= math.dist(s['center_pixels'],t['center_pixels'])>=cfg['min_spacing_pixels'] and not overlap(ex,t['protected_envelope_pixels'])
        for iid in s['boundary_instances']:
            i=items[iid];o=[x*unit for x in i['origin_blocks']];w,h=[x*unit for x in i['size_blocks']]
            alignment &= (a[0]==b[0] and a[0] in [o[0],o[0]+w] and o[1]<=min(a[1],b[1])<=max(a[1],b[1])<=o[1]+h) or (a[1]==b[1] and a[1] in [o[1],o[1]+h] and o[0]<=min(a[0],b[0])<=max(a[0],b[0])<=o[0]+w)
    checks['swept_saw_protection']=bool(gear_ok);checks['symmetric_density_cap']=bool(density);checks['boundary_alignment']=bool(alignment);checks['global_cap']=len(saws)<=cfg['max_groups'];checks['status_honest']=(out['status']=='PARTIAL')==bool(out['gaps']);return checks

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[]
    for algo in ['v5','v6returns','v6merge','v7']:
        folder=ROOT/'validation/map-additions-20261105'/('cohort-'+algo)
        for row in json.loads((folder/'summary.json').read_text())['rows']:
            if row['status']=='BASE_FAILED':rows.append(dict(algorithm=algo,seed=row['seed'],status='BASE_FAILED'));continue
            v=json.loads(gzip.decompress((folder/('seed-'+str(row['seed'])+'.json.gz')).read_bytes()))['result'];checks=audit(read(source(algo,row['seed'])),v);rows.append(dict(algorithm=algo,seed=row['seed'],status='PASS' if all(checks.values()) else 'FAIL',checks=checks))
    report=dict(status='PASS' if all(r['status']!='FAIL' for r in rows) else 'FAIL',scope='Independent static graph/geometry audit only; canonical identity replay checked separately in Godot; no whole-map physics, actor AI, or host interaction proof',rows=rows);a.out.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],[(r['algorithm'],r['seed'],[k for k,v in r.get('checks',{}).items() if not v]) for r in rows if r['status']=='FAIL'])
if __name__=='__main__':main()
