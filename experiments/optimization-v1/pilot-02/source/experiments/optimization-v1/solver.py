"""Cumulative route/expansion/backtracking changes over the frozen generator.

No module content mutation, no seed replacement, no synthetic Route, no fallback.
The v2 adapter/auditor and the original final assembler remain acceptance gates.
"""
import copy
from collections import Counter, defaultdict, deque
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_import_path=sys.path[:]
sys.path.insert(0, str(ROOT/'experiments/legacy-real-v2'))
from adapter import RealLibrary, audit, gear_seal, legacy, model, package, read, segment_hits_rect
sys.path[:]=_import_path


class SearchFailure(RuntimeError): pass
class BudgetExhausted(SearchFailure): pass


def reachable(graph, start):
    seen={start};queue=deque([start])
    while queue:
        for node in graph.get(queue.popleft(),[]):
            if node not in seen:seen.add(node);queue.append(node)
    return seen


class Optimized(legacy.Generator):
    def __init__(self, seed, library, variant, config):
        super().__init__(seed)
        self.library=library;self.variant=variant;self.config=config
        self.expansion=variant in ('expansion','backtrack')
        self.backtracking=variant=='backtrack'
        self.phase='init';self.started=time.perf_counter()
        self.rejections=Counter();self.backtracks=0;self.repairs=0;self.terminal_states=0
        self.failures=[];self.decisions=[];self.frames=[];self.config_cache={}
        self.on_failure=None;self.on_checkpoint=None;self.closed_loops=0
        self.layout_terminal_start=0
        self.routes={};self.transit={}
        for mid,t in model.LIB.items():
            for mx in (False,True):
                rs=[]
                for r in t['routes']:
                    a,b=self.local[mid,mx][r['from_port']],self.local[mid,mx][r['to_port']]
                    if not set(r['required_abilities'])<=model.ABILITIES:continue
                    if not model.permitted(a,'in')or not model.permitted(b,'out'):continue
                    rs.append(r)
                self.routes[mid,mx]=rs
                for pid in self.local[mid,mx]:
                    self.transit[mid,mx,pid]=[r for r in rs if r['from_port']==pid and not r['validation'].get('testNeighborFixtures')]

    def tick(self):
        self.expanded+=1
        if self.expanded>self.config['candidate_expansion_budget']:
            raise BudgetExhausted('candidate_expansion_budget')
        if self.expanded%256==0 and time.perf_counter()-self.started>self.config['per_seed_timeout_seconds']:
            raise BudgetExhausted('wall_clock_budget')

    def raw_candidates(self, source, mids, items):
        _,_,p=source
        if not model.permitted(p,'out'):return
        for mid,mx,pid,local in self.index[model.OPPOSITE[p['face']],p['surface']]:
            if mid not in mids or not model.permitted(local,'in'):continue
            delta=[p['world2'][d]-local['local2'][d]for d in (0,1)]
            if any(n%2 for n in delta):continue
            self.tick();item=legacy.make(mid,*[n//2 for n in delta],mx)
            if any(model.overlap(item,i)for i in items):continue
            yield item,pid

    def candidates(self, source, mids=None, items=None):
        items=self.items if items is None else items
        mids=set(model.LIB)if mids is None else mids
        for item,pin in self.raw_candidates(source,mids,items):
            if item['module_id']=='BOSS':yield item,pin;continue
            rs=self.transit[item['module_id'],item['mirror_x'],pin]
            if not rs:self.rejections['no_route_from_actual_entry']+=1;continue
            if item['reward']:
                # Final connected-Port/reward reachability is checked after
                # actual seams are known, never inferred from room contents.
                if not any(r['reward_ids']for r in rs):
                    self.rejections['entry_has_no_reward_route']+=1;continue
            elif not any(r['to_port']!=pin for r in rs):
                self.rejections['no_onward_route_from_actual_entry']+=1;continue
            yield item,pin

    def configuration_ok(self, item, connected):
        mid,mx=item['module_id'],item['mirror_x'];key=(mid,mx,tuple(sorted(connected)))
        if key in self.config_cache:return self.config_cache[key]
        t=model.LIB[mid]
        full=model.placed_ports(dict(t,ports=t['all_ports']),0,0,mx)
        seals=[gear_seal(p,t['size_blocks'])for pid,p in full.items()if pid not in connected]
        for r in t['all_routes']:
            if r['from_port']not in connected or r['to_port']not in connected:continue
            if not set(r['required_abilities'])<=model.ABILITIES:continue
            if r['validation'].get('testNeighborFixtures'):
                self.config_cache[key]=False;return False
            if not model.permitted(full[r['from_port']],'in')or not model.permitted(full[r['to_port']],'out'):
                self.config_cache[key]=False;return False
            points=r['path_points']
            if len(points)<2:self.config_cache[key]=False;return False
            if mx:points=[[t['size_blocks'][0]*128-x,y]for x,y in points]
            for seal in seals:
                x,y,w,h=seal['rect_pixels'];rect=[x-12,y-18,w+24,h+36]
                if any(segment_hits_rect(a,b,rect)for a,b in zip(points,points[1:])):
                    self.config_cache[key]=False;return False
        self.config_cache[key]=True;return True

    def graph(self, items, potential=False):
        g=defaultdict(list);connected=defaultdict(set);rewards=[]
        groups=legacy.connection_groups(items)
        for(a,ap,p),(b,bp,q)in groups:
            connected[a['id']].add(ap);connected[b['id']].add(bp)
            if model.permitted(p,'out')and model.permitted(q,'in'):
                g[a['id']+'.'+ap+':depart'].append(b['id']+'.'+bp+':arrive')
            if model.permitted(q,'out')and model.permitted(p,'in'):
                g[b['id']+'.'+bp+':depart'].append(a['id']+'.'+ap+':arrive')
        for i in items:
            for r in self.routes[i['module_id'],i['mirror_x']]:
                a,b=r['from_port'],r['to_port'];selected=connected[i['id']]
                if not potential and (a not in selected or b not in selected):continue
                if potential and not self.configuration_ok(i,selected|{a,b}):continue
                chain=[i['id']+'.'+a+':arrive']
                if i['reward'] and r['reward_ids']:
                    node=i['id']+':reward:'+r['id'];chain.append(node);rewards.append((i['id'],node))
                chain.append(i['id']+'.'+b+':depart')
                for x,y in zip(chain,chain[1:]):g[x].append(y)
        g['START'].append('M01.R:depart')
        boss=next((i for i in items if i['module_id']=='BOSS'),None)
        if boss:g[boss['id']+'.L:arrive'].append('BOSS')
        return g,rewards,connected

    def reachable_frontier(self, items):
        graph,_,_=self.graph(items,potential=True);seen=reachable(graph,'START')
        return [s for s in self.frontier(items)if s[0]['id']+'.'+s[1]+':depart'in seen and model.permitted(s[2],'out')]

    def safe_state(self, items):
        _,_,connected=self.graph(items)
        return all(self.configuration_ok(i,connected[i['id']])for i in items)

    def record_failure(self, reason):
        row=dict(reason=reason,phase=self.phase,expanded=self.expanded,
            backtracks=self.backtracks,repairs=self.repairs,instances=copy.deepcopy(self.items))
        self.failures.append(row)
        if self.on_failure:self.on_failure(row)

    def add(self,item):
        result=super().add(item)
        if self.on_checkpoint:self.on_checkpoint(self)
        return result

    def successor_count(self, item, pin, items, lookup):
        counts=[0,0,0];tids={k for k in model.LIB if k.startswith('T')}
        role_ids={k for k in model.LIB if k.startswith('Q')}|{'BOSS'}
        routes=self.transit[item['module_id'],item['mirror_x'],pin]
        exits=sorted({r['to_port']for r in routes if r['to_port']!=pin})
        connected={pid for pid,p in item['ports'].items()if any(legacy.matching(p,q)for q in lookup.get(tuple(p['world2']),[]))}
        for pid in exits:
            if pid in connected:continue
            if not self.configuration_ok(item,connected|{pin,pid}):continue
            source=(item,pid,item['ports'][pid]);trial=items+[item]
            if next(self.candidates(source,tids,trial),None)is not None:counts[0]+=1
            if any(r['to_port']==pin for r in self.transit[item['module_id'],item['mirror_x'],pid]):counts[1]+=1
            if next(self.candidates(source,role_ids,trial),None)is not None:counts[2]+=1
        return counts

    def growth_options(self):
        fronts=self.reachable_frontier(self.items);self.rng.shuffle(fronts)
        fronts=fronts[:self.config['growth_frontier_limit']]
        old=legacy.bounds(self.items);area=(old[2]-old[0])*(old[3]-old[1])
        lookup=defaultdict(list)
        for _,_,p in self.frontier():lookup[tuple(p['world2'])].append(p)
        used=Counter(i['module_id']for i in self.items)
        mids={k for k in model.LIB if k.startswith('T')};options=[];seen=set()
        for source in fronts:
            for item,pin in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']),pin)
                if key in seen:continue
                seen.add(key)
                auto=sum(any(legacy.matching(p,q)for q in lookup.get(tuple(p['world2']),[]))for p in item['ports'].values())
                x,y=item['origin'];w,h=item['size_blocks']
                newarea=(max(old[2],x+w)-min(old[0],x))*(max(old[3],y+h)-min(old[1],y))
                base=24*(auto-1)-.055*(newarea-area)-5*used[item['module_id']]-.10*max(0,-x)-.025*abs(y)+self.rng.uniform(-3,3)
                score=base
                if self.expansion:
                    free={r['to_port']for r in self.transit[item['module_id'],item['mirror_x'],pin]if r['to_port']!=pin and not any(legacy.matching(item['ports'][r['to_port']],q)for q in lookup.get(tuple(item['ports'][r['to_port']]['world2']),[]))}
                    score+=self.config['expansion_weights']['usable_exit']*(len(free)-1)
                options.append((score,base,item,pin))
        options.sort(key=lambda x:x[0],reverse=True)
        ranked=[]
        # Bounded lookahead over the same beam-width-sized shortlist. Geometry
        # evaluations contribute to the common expansion budget.
        shortlist=options[:self.config['closure_beam_width']]if self.expansion else options
        for score,base,item,pin in shortlist:
            item=copy.deepcopy(item);item['id']=f'M{len(self.items)+1:02}'
            if not self.safe_state(self.items+[item]):self.rejections['seal_or_route_configuration']+=1;continue
            if self.expansion:
                exits,reverse,slots=self.successor_count(item,pin,self.items,lookup);weights=self.config['expansion_weights']
                score=base+weights['usable_exit']*(exits-1)+weights['bidirectional_exit']*reverse+weights['terminal_slot']*slots
                if not exits:score+=weights['dead_end']
            ranked.append((score,item))
        ranked.sort(key=lambda x:x[0],reverse=True)
        unique=[];physical=set()
        for _,item in ranked:
            key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
            if key not in physical:physical.add(key);unique.append(item)
        choices=unique[:self.config['growth_choice_count']]
        if choices:
            pick=self.rng.randrange(len(choices));choices=[choices[pick]]+choices[:pick]+choices[pick+1:]
        return choices

    def rewind(self):
        for depth in range(self.config['max_rewind_depth']):
            if not self.frames or self.backtracks>=self.config['max_growth_backtracks']:return False
            frame=self.frames[-1];self.items=copy.deepcopy(frame['before']);self.backtracks+=1
            if frame['choices']:
                choice=frame['choices'].pop(0);self.rng.setstate(frame['rng']);self.add(copy.deepcopy(choice))
                return True
            self.frames.pop()
        return False

    def grow(self, count=32):
        self.phase='growth'
        if not self.items:self.add(legacy.make('START',0,0))
        while len(self.items)<count:
            choices=self.growth_options()
            if not choices:
                self.record_failure('growth_exhausted')
                if self.backtracking and self.rewind():continue
                raise SearchFailure('growth_exhausted')
            first=choices.pop(0)
            self.frames.append(dict(before=copy.deepcopy(self.items),choices=choices,rng=self.rng.getstate()))
            self.decisions.append(dict(instance=f'M{len(self.items)+1:02}',module_id=first['module_id'],origin=first['origin'],mirror_x=first['mirror_x']))
            self.add(copy.deepcopy(first))

    def close_one(self,max_depth=3):
        self.phase='closure_search';fronts=self.reachable_frontier(self.items);self.rng.shuffle(fronts)
        viable=[s for s in fronts if not s[0]['reward']and s[0]['module_id']!='START']
        graph,_,_=self.graph(self.items,potential=True)
        mids={k for k in model.LIB if k.startswith('T')}
        for source in viable[:24]:
            targets=[t for t in self.frontier()if t[0]['id']!=source[0]['id'] and model.permitted(t[2],'in') and sum(abs(t[2]['world2'][k]-source[2]['world2'][k])for k in(0,1))<40 and source[0]['id']+'.'+source[1]+':depart'in reachable(graph,t[0]['id']+'.'+t[1]+':arrive')]
            if not targets:continue
            beam=[([],source)]
            for depth in range(max_depth):
                states=[]
                for chain,front in beam:
                    for item,pin in self.candidates(front,mids,self.items+chain):
                        item['id']=f'tmp{depth}'
                        for pid in sorted({r['to_port']for r in self.transit[item['module_id'],item['mirror_x'],pin]if r['to_port']!=pin}):
                            p=item['ports'][pid]
                            if not self.configuration_ok(item,{pin,pid}):continue
                            if any(legacy.matching(p,t[2])and model.permitted(t[2],'in')for t in targets):
                                trial=copy.deepcopy(self.items)
                                for c in chain+[item]:
                                    c=copy.deepcopy(c);c['id']=f'M{len(trial)+1:02}';trial.append(c)
                                if self.safe_state(trial):self.items=trial;return True
                            dist=min(sum(abs(p['world2'][k]-t[2]['world2'][k])for k in(0,1))for t in targets)
                            if dist<32:states.append((dist+self.rng.random()*2,chain+[item],(item,pid,p)))
                states.sort(key=lambda x:x[0]);beam=[(chain,f)for _,chain,f in states[:self.config['closure_beam_width']]]
                if not beam:break
        return False

    def valid_reward_state(self,items):
        if not self.safe_state(items):return False
        graph,rewards,_=self.graph(items);seen=reachable(graph,'START')
        if 'BOSS'not in seen:return False
        for i in items:
            if not i['reward']:continue
            nodes=[n for iid,n in rewards if iid==i['id']and n in seen]
            if not nodes or any('BOSS'not in reachable(graph,n)for n in nodes):return False
        return True

    def reward_options(self):
        mids={k for k in model.LIB if k.startswith('Q')};options=[];seen=set()
        for source in self.reachable_frontier(self.items):
            if source[0]['reward']or source[0]['module_id']in('START','BOSS'):continue
            for item,_ in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
                if key in seen:continue
                seen.add(key);item['id']=f'M{len(self.items)+1:02}'
                if not self.valid_reward_state(self.items+[item]):self.rejections['reward_claim_or_onward_invalid']+=1;continue
                import math
                near=sum(math.hypot(item['origin'][0]-i['origin'][0],item['origin'][1]-i['origin'][1])<8 for i in self.items if i['reward'])
                options.append((self.rng.random()*4-near*5,item))
        options.sort(key=lambda x:x[0],reverse=True)
        return [i for _,i in options[:self.config['growth_choice_count']]]

    def place_rewards(self,n):
        if n==self.config['reward_target']:
            try:return legacy.assemble(self)
            except AssertionError:
                self.record_failure('original_assembly_rejected');return None
        choices=self.reward_options()
        if not self.backtracking:choices=choices[:1]
        if not choices:self.record_failure('reward_exhausted');return None
        before=copy.deepcopy(self.items);rng=self.rng.getstate()
        for choice in choices:
            self.terminal_states+=1
            if self.terminal_states>self.config['max_terminal_states']:
                raise BudgetExhausted('terminal_state_budget')
            if self.backtracking:
                share=max(self.config['reward_target'],self.config['max_terminal_states']//(self.config['max_layout_repairs']+1))
                if self.terminal_states-self.layout_terminal_start>share:
                    self.record_failure('terminal_slice_exhausted')
                    raise SearchFailure('terminal_slice_exhausted')
            self.items=copy.deepcopy(before);self.rng.setstate(rng);self.add(copy.deepcopy(choice))
            result=self.place_rewards(n+1)
            if result is not None:return result
        self.items=before;return None

    def finish(self):
        self.phase='boss_rewards';import math
        self.layout_terminal_start=self.terminal_states
        adjacency=defaultdict(set)
        for (a,_,_),(b,_,_)in legacy.connection_groups(self.items):
            adjacency[a['id']].add(b['id']);adjacency[b['id']].add(a['id'])
        distances={'M01':0};queue=deque(['M01'])
        while queue:
            at=queue.popleft()
            for node in sorted(adjacency[at]):
                if node not in distances:distances[node]=distances[at]+1;queue.append(node)
        options=[]
        for source in self.reachable_frontier(self.items):
            if source[0]['module_id']=='START':continue
            for item,_ in self.candidates(source,{'BOSS'},self.items):
                item['id']=f'M{len(self.items)+1:02}'
                if self.valid_reward_state(self.items+[item]):
                    options.append((math.hypot(*item['origin'])+.4*distances.get(source[0]['id'],0),item))
        options.sort(key=lambda x:x[0],reverse=True)
        if not self.backtracking:options=options[:1]
        else:options=options[:self.config['growth_choice_count']]
        if not options:self.record_failure('boss_exhausted');raise SearchFailure('boss_exhausted')
        before=copy.deepcopy(self.items);rng=self.rng.getstate()
        for _,boss in options:
            self.items=copy.deepcopy(before);self.rng.setstate(rng);self.add(copy.deepcopy(boss))
            result=self.place_rewards(0)
            if result is not None:return result
        raise SearchFailure('reward_or_final_graph_exhausted')

    def build(self):
        while True:
            self.grow(self.config['growth_target']);growth=copy.deepcopy(self.items)
            for _ in range(self.config['close_attempts']):
                self.closed_loops+=bool(self.close_one(self.config['close_depth']))
            self.phase='air_loop';self.air_connected=super().add_air_loop()
            try:return self.finish()
            except BudgetExhausted:raise
            except SearchFailure:
                if not self.backtracking or self.repairs>=self.config['max_layout_repairs']:raise
                self.repairs+=1;self.items=growth
                if not self.rewind():raise
