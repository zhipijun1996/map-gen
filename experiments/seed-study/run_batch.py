#!/usr/bin/env python3
"""Freeze the v2 generator; evaluate seeds without retries, seed substitution or repairs."""
import sys,json,time,subprocess,traceback,hashlib,csv,statistics
from pathlib import Path
from collections import defaultdict,deque,Counter
ROOT=Path(__file__).parent;OUT=ROOT/'output';SOURCE=ROOT/'source'
sys.path.insert(0,str(SOURCE))
from generate import prepare_library,Generator
from model import LIB,OPPOSITE,permitted

def verify(m):
    ids={i['id']:i for i in m['instances']};occupied={};used=set();g=defaultdict(list)
    for i in ids.values():
        x,y=i['origin'];w,h=i['size_blocks'];assert all(type(n) is int for n in (x,y,w,h))
        for bx in range(x,x+w):
            for by in range(y,y+h):assert (bx,by) not in occupied;occupied[bx,by]=i['id']
        for p in i['ports'].values():
            u,v=p['local2'];f=p['face']
            if f in ('LEFT','RIGHT'):assert u==(0 if f=='LEFT' else 2*w) and v%2==1 and 0<v<2*h
            else:assert v==(0 if f=='TOP' else 2*h) and u%2==1 and 0<u<2*w
            assert p['world2']==[2*x+u,2*y+v]
            assert p['surface']!='ROCK' or f in ('LEFT','RIGHT')
            assert not(p['surface']=='AIR' and f=='BOTTOM' and permitted(p,'in'))
    for a,b in m['actual_graph']['edges']:g[a].append(b)
    for c in m['connections']:
        a,ap=c['a'].split('.');b,bp=c['b'].split('.');p=ids[a]['ports'][ap];q=ids[b]['ports'][bp]
        assert p['world2']==q['world2']==c['world2'] and p['surface']==q['surface']==c['surface']
        assert OPPOSITE[p['face']]==q['face']
        expected=[]
        if permitted(p,'out') and permitted(q,'in'):expected.append([c['a'],c['b']])
        if permitted(q,'out') and permitted(p,'in'):expected.append([c['b'],c['a']])
        assert expected==c['directions']
        for s,t in expected:assert t+':arrive' in g[s+':depart']
        for endpoint in (c['a'],c['b']):assert endpoint not in used;used.add(endpoint)
    for i in ids.values():
        for pid in i['ports']:assert (i['id']+'.'+pid in used) != (pid in i['closures'])
        expected={(r['from_port'],r['to_port']) for r in LIB[i['module_id']]['routes'] if r['from_port'] not in i['closures'] and r['to_port'] not in i['closures'] and set(r['required_abilities'])<=set(m['available_abilities'])}
        assert expected=={(r['from_port'],r['to_port']) for r in i['actual_routes']}
        for r in i['actual_routes']:
            a=i['ports'][r['from_port']]['world2'];b=i['ports'][r['to_port']]['world2']
            assert r['displacement']==[(b[k]-a[k])/2 for k in (0,1)]
            if not i['reward']:assert i['id']+'.'+r['to_port']+':depart' in g[i['id']+'.'+r['from_port']+':arrive']
    def reach(source):
        seen={source};q=deque([source])
        while q:
            for n in g[q.popleft()]:
                if n not in seen:seen.add(n);q.append(n)
        return seen
    seen=reach('START');assert 'BOSS' in seen
    for i in ids.values():
        if i['reward']:
            rewardnodes=[n for n in seen if n.startswith(i['id']+':reward:')]
            assert rewardnodes and all('BOSS' in reach(n) for n in rewardnodes)
    for path in m['main_paths']:assert path[0]=='START' and path[-1]=='BOSS' and all(b in g[a] for a,b in zip(path,path[1:]))
    rectarea=sum(i['size_blocks'][0]*i['size_blocks'][1] for i in ids.values())
    b=m['summary']['bounds_blocks'];boxarea=(b[2]-b[0])*(b[3]-b[1]);ports=sum(len(i['ports']) for i in ids.values())
    actual_reached={n.split('.')[0].split(':')[0] for n in seen}
    return dict(rect_area=rectarea,bounding_box=[b[2]-b[0],b[3]-b[1]],occupancy=rectarea/boxarea,
                closure_ratio=len(m['closures'])/ports,reachable_instances=sum(i in actual_reached for i in ids),
                horizontal_offset_ratio=m['summary']['offset_horizontal_seams']/m['summary']['horizontal_seams'],
                offcentre_ratio=m['summary']['offcentre_active_endpoints']/m['summary']['active_port_endpoints'])

class Instrumented(Generator):
    phase='init'
    def grow(self,*a,**kw):self.phase='growth';return super().grow(*a,**kw)
    def close_one(self,*a,**kw):self.phase='closure_search';return super().close_one(*a,**kw)
    def add_air_loop(self,*a,**kw):self.phase='air_loop';return super().add_air_loop(*a,**kw)
    def finish(self,*a,**kw):self.phase='boss_rewards_and_graph_validation';return super().finish(*a,**kw)

def worker(seed):
    prepare_library();gen=Instrumented(seed);started=time.perf_counter();folder=OUT/f'seed-{seed}';folder.mkdir(parents=True,exist_ok=True)
    try:
        m=gen.build();generation=time.perf_counter()-started;gen.phase='independent_validation';metrics=verify(m)
        (folder/'map.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
        return dict(seed=seed,status='PASS',seconds=round(generation,4),**m['summary'],**metrics)
    except Exception as err:
        (folder/'failed-candidate.json').write_text(json.dumps(dict(seed=seed,phase=gen.phase,instances=gen.items),ensure_ascii=False,indent=2))
        trace=traceback.format_exc();(folder/'failure.txt').write_text(trace)
        return dict(seed=seed,status='FAIL',seconds=round(time.perf_counter()-started,4),phase=gen.phase,error=type(err).__name__+': '+str(err),trace=trace)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':print(json.dumps(worker(int(sys.argv[2])),ensure_ascii=False));sys.exit()
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*.py')}
    results=[];seeds=list(range(271028,271048))
    for seed in seeds:
        try:
            r=subprocess.run([sys.executable,__file__,'--worker',str(seed)],capture_output=True,text=True,timeout=90)
            row=json.loads(r.stdout) if r.returncode==0 else dict(seed=seed,status='ERROR',error=r.stderr[-2000:])
        except subprocess.TimeoutExpired:row=dict(seed=seed,status='TIMEOUT',seconds=90)
        results.append(row)
        (OUT/'results.json').write_text(json.dumps(dict(seeds=seeds,source_sha256=hashes,per_seed_timeout_seconds=90,retry_count=0,results=results),ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in row.items() if k in ('seed','status','seconds','instances','connections','cycles','main_paths','surfaces','error')},ensure_ascii=False),flush=True)
    keys=['seed','status','seconds','instances','connections','cycles','used_templates','distinct_sizes','rewards','main_paths','closures','closure_ratio','horizontal_offset_ratio','offcentre_ratio','occupancy','reachable_instances','phase','error']
    with (OUT/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(results)
    print('COMPLETE',flush=True)
