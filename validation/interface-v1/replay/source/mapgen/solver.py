"""Independent stable-v2 search. Every policy value arrives through per-call inputs.

Search order, RNG calls and arithmetic order match the frozen reference profile.
No imports of experiments, sys.path changes, network or file I/O are performed.
"""
import copy
import math
import random
from collections import Counter,defaultdict,deque
from . import geometry as model
from .geometry import matching,bounds,connection_groups,segment_hits_rect
from .assembly import assemble,AssemblyRejected
from .audit import audit
from .metrics import actual_paths,shape_metrics

class SearchFailure(RuntimeError):pass
class BudgetExhausted(SearchFailure):pass
class Cancelled(SearchFailure):pass

def reachable(graph,start):
    seen={start};queue=deque([start])
    while queue:
        for node in graph.get(queue.popleft(),[]):
            if node not in seen:seen.add(node);queue.append(node)
    return seen

class GeometrySearch:
    def __init__(self,seed,library):
        self.library=library;self.templates=library.templates;self.abilities=library.abilities;self.seed=seed;self.rng=random.Random(seed);self.items=[];self.expanded=0
        self.local={};self.index=defaultdict(list)
        for mid,t in library.templates.items():
            for mx in ((False,True) if t['allow_mirror_x'] else (False,)):
                ps=model.placed_ports(t,0,0,mx);self.local[mid,mx]=ps
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

    def add_air_loop(self):
        # Search an already available ROCK frontier, then require a real reconnection.
        basefront=self.frontier();self.rng.shuffle(basefront)
        for source in basefront:
            if source[2]['surface']!='ROCK' or not model.permitted(source[2],'out'):continue
            for a,pin in self.candidates(source,self.library.air_entries):
                a['id']='airtmpA'
                air=next((pid,p) for pid,p in a['ports'].items() if p['surface']=='AIR')
                for b,bpin in self.candidates((a,*air),self.library.air_returns,self.items+[a]):
                    b['id']='airtmpB'
                    out=next((pid,p) for pid,p in b['ports'].items() if p['surface']=='ROCK')
                    # Extend from B into a target old frontier with bounded search.
                    targets=[t for t in basefront if t[0]['id']!=source[0]['id']]
                    mids={m for m in self.templates if m.startswith('T')}
                    for c,cpin in self.candidates((b,*out),mids,self.items+[a,b]):
                        if any(matching(p,t[2]) for pid,p in c['ports'].items() if pid!=cpin for t in targets):
                            self.add(a);self.add(b);self.add(c);return True
        return False

    def make(self,mid,x,y,mirror=False,iid=None):
        t=self.templates[mid]
        return dict(id=iid,module_id=mid,name=t['name'],origin=[x,y],size_blocks=t['size_blocks'],mirror_x=mirror,ports=model.placed_ports(t,x,y,mirror),reward=t['reward'])


class Search(GeometrySearch):
    def __init__(self, seed, library, config, hooks):
        super().__init__(seed,library)
        self.library=library;self.variant="stable";self.config=config
        self.expansion=True
        self.backtracking=True
        self.hooks=hooks;self.phase='init';self.started=self.hooks.clock()
        self.rejections=Counter();self.backtracks=0;self.repairs=0;self.terminal_states=0
        self.failures=[];self.decisions=[];self.frames=[];self.config_cache={}
        self.on_failure=None;self.on_checkpoint=None;self.closed_loops=0
        self.layout_terminal_start=0
        self.routes={};self.transit={}
        for mid,t in self.templates.items():
            for mx in (False,True):
                rs=[]
                for r in t['routes']:
                    a,b=self.local[mid,mx][r['from_port']],self.local[mid,mx][r['to_port']]
                    if not set(r['required_abilities'])<=self.abilities:continue
                    if not model.permitted(a,'in')or not model.permitted(b,'out'):continue
                    rs.append(r)
                self.routes[mid,mx]=rs
                for pid in self.local[mid,mx]:
                    self.transit[mid,mx,pid]=[r for r in rs if r['from_port']==pid and not r['validation'].get('testNeighborFixtures')]

    def tick(self):
        if self.hooks.cancelled():raise Cancelled('cancelled')
        self.expanded+=1
        if self.expanded>self.config['candidate_expansion_budget']:
            raise BudgetExhausted('candidate_expansion_budget')
        if self.expanded%self.config['budget_check_interval']==0 and self.config['per_seed_timeout_seconds'] is not None and self.hooks.clock()-self.started>self.config['per_seed_timeout_seconds']:
            raise BudgetExhausted('wall_clock_budget')

    def raw_candidates(self, source, mids, items):
        _,_,p=source
        if not model.permitted(p,'out'):return
        for mid,mx,pid,local in self.index[model.OPPOSITE[p['face']],p['surface']]:
            if mid not in mids or not model.permitted(local,'in'):continue
            delta=[p['world2'][d]-local['local2'][d]for d in (0,1)]
            if any(n%2 for n in delta):continue
            self.tick();item=self.make(mid,*[n//2 for n in delta],mx)
            if any(model.overlap(item,i)for i in items):continue
            yield item,pid

    def candidates(self, source, mids=None, items=None):
        items=self.items if items is None else items
        mids=set(self.templates)if mids is None else mids
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
        t=self.templates[mid]
        full=model.placed_ports(dict(t,ports=t['all_ports']),0,0,mx)
        seals=[self.library.gear_seal(p,t['size_blocks'])for pid,p in full.items()if pid not in connected]
        for r in t['all_routes']:
            if r['from_port']not in connected or r['to_port']not in connected:continue
            if not set(r['required_abilities'])<=self.abilities:continue
            if r['validation'].get('testNeighborFixtures'):
                self.config_cache[key]=False;return False
            if not model.permitted(full[r['from_port']],'in')or not model.permitted(full[r['to_port']],'out'):
                self.config_cache[key]=False;return False
            points=r['path_points']
            if len(points)<2:self.config_cache[key]=False;return False
            if mx:points=[[t['size_blocks'][0]*self.library.block_pixels-x,y]for x,y in points]
            for seal in seals:
                rect=self.library.clearance_rect(seal['rect_pixels'])
                if any(segment_hits_rect(a,b,rect)for a,b in zip(points,points[1:])):
                    self.config_cache[key]=False;return False
        self.config_cache[key]=True;return True

    def graph(self, items, potential=False):
        g=defaultdict(list);connected=defaultdict(set);rewards=[]
        groups=connection_groups(items)
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
        if self.on_failure:self.on_failure(copy.deepcopy(row))

    def add(self,item):
        if self.hooks.cancelled():raise Cancelled('cancelled')
        result=super().add(item)
        if self.on_checkpoint:self.on_checkpoint(dict(phase=self.phase,expanded=self.expanded,instances=copy.deepcopy(self.items)))
        return result

    def rewind(self):
        for depth in range(self.config['max_rewind_depth']):
            if not self.frames or self.backtracks>=self.config['max_growth_backtracks']:return False
            frame=self.frames[-1];self.items=copy.deepcopy(frame['before']);self.backtracks+=1
            if frame['choices']:
                choice=frame['choices'].pop(0);self.rng.setstate(frame['rng']);self.add(copy.deepcopy(choice))
                return True
            self.frames.pop()
        return False

    def grow(self, count):
        self.phase='growth'
        if not self.items:self.add(self.make('START',*self.library.request['start_origin_blocks']))
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

    def close_one(self,max_depth):
        self.phase='closure_search';fronts=self.reachable_frontier(self.items);self.rng.shuffle(fronts)
        viable=[s for s in fronts if not s[0]['reward']and s[0]['module_id']!='START']
        graph,_,_=self.graph(self.items,potential=True)
        mids={k for k in self.templates if k.startswith('T')}
        for source in viable[:self.config['closure_source_limit']]:
            targets=[t for t in self.frontier()if t[0]['id']!=source[0]['id'] and model.permitted(t[2],'in') and sum(abs(t[2]['world2'][k]-source[2]['world2'][k])for k in(0,1))<self.config['closure_target_distance2'] and source[0]['id']+'.'+source[1]+':depart'in reachable(graph,t[0]['id']+'.'+t[1]+':arrive')]
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
                            if any(matching(p,t[2])and model.permitted(t[2],'in')for t in targets):
                                trial=copy.deepcopy(self.items)
                                for c in chain+[item]:
                                    c=copy.deepcopy(c);c['id']=f'M{len(trial)+1:02}';trial.append(c)
                                if self.safe_state(trial):self.items=trial;return True
                            dist=min(sum(abs(p['world2'][k]-t[2]['world2'][k])for k in(0,1))for t in targets)
                            if dist<self.config['closure_distance_limit2']:states.append((dist+self.rng.random()*self.config['scoring']['closure_noise'],chain+[item],(item,pid,p)))
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

    def place_rewards(self,n):
        if n==self.config['reward_target']:
            try:return assemble(self)
            except AssemblyRejected:
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

    def build(self):
        while True:
            self.grow(self.config['growth_target']);growth=copy.deepcopy(self.items)
            for _ in range(self.config['close_attempts']):
                self.closed_loops+=bool(self.close_one(self.config['close_depth']))
            self.phase='air_loop';self.air_connected=super().add_air_loop() if self.library.request['air_loop']['enabled'] else False
            try:return self.finish()
            except BudgetExhausted:raise
            except SearchFailure:
                if not self.backtracking or self.repairs>=self.config['max_layout_repairs']:raise
                self.repairs+=1;self.items=growth
                if not self.rewind():raise


class StableSolver(Search):
    def __init__(self,seed,library,config,hooks):
        super().__init__(seed,library,config,hooks)
        self.profile="stable";self.variant="stable"
        self.multi_axis=True;self.goal_aware=True
        self.return_rooms={k for k,t in self.templates.items()if k.startswith('Q')and len(t['ports'])==1 and any(r['from_port']==r['to_port']and r['reward_ids']for r in t['routes'])}

    def graph(self,items,potential=False):
        graph,rewards,connected=super().graph(items,potential)
        # Expand ordinary-room treasure edges too, preserving declared route
        # endpoints. This matches the independent auditor's actual reward graph.
        for i in items:
            if i['reward']:continue
            for r in self.routes[i['module_id'],i['mirror_x']]:
                if not r['reward_ids']:continue
                a=i['id']+'.'+r['from_port']+':arrive';b=i['id']+'.'+r['to_port']+':depart'
                if b not in graph.get(a,[]):continue
                graph[a].remove(b);chain=[a]+[i['id']+':reward:'+r['id']+':'+rid for rid in r['reward_ids']]+[b]
                for x,y in zip(chain,chain[1:]):graph[x].append(y)
        return graph,rewards,connected

    def shape_cost(self,bounds):
        w,h=bounds[2]-bounds[0],bounds[3]-bounds[1];cfg=self.config['shape']
        excess=max(0,abs(math.log(w/h/cfg['target_ratio']))-math.log(cfg['soft_tolerance']))
        return cfg['aspect_weight']*excess

    def exit_features(self,item,pin,items,lookup):
        useful=reverse=slots=vertical=0;directions=set()
        tids={k for k in self.templates if k.startswith('T')};roles={k for k in self.templates if k.startswith('Q')}|{'BOSS'}
        connected={pid for pid,p in item['ports'].items()if any(matching(p,q)for q in lookup.get(tuple(p['world2']),[]))}
        for pid in sorted({r['to_port']for r in self.transit[item['module_id'],item['mirror_x'],pin]if r['to_port']!=pin}):
            if pid in connected or not self.configuration_ok(item,connected|{pin,pid}):continue
            source=(item,pid,item['ports'][pid]);trial=items+[item]
            if next(self.candidates(source,tids,trial),None)is not None:
                useful+=1;face=source[2]['face'];directions.add(face)
                vertical+=face in ('TOP','BOTTOM')
            if any(r['to_port']==pin for r in self.transit[item['module_id'],item['mirror_x'],pid]):reverse+=1
            if next(self.candidates(source,roles,trial),None)is not None:slots+=1
        return useful,reverse,slots,vertical,len(directions)

    def reservation(self,items,limit,require_boss=False):
        """Constructive, nonoverlapping single-Port return-room capacity witness.

        Uses real source rectangles/routes; it is not a promise based on Port
        count. Only planning uses this conservative witness; every final room
        still undergoes the unchanged independent audit.
        """
        if limit<=0:return []
        graph,_,connected=self.graph(items,potential=True);seen=reachable(graph,'START')
        proposed=[];used=set();extra=defaultdict(set);counts=Counter()
        for source in self.frontier(items):
            i,pid,p=source
            if i['reward']or i['module_id']in ('START','BOSS'):continue
            if i['id']+'.'+pid+':depart'not in seen or not model.permitted(p,'in'):continue
            onward=reachable(graph,i['id']+'.'+pid+':arrive')
            if require_boss:
                if 'BOSS'not in onward:continue
            elif not any(i['id']+'.'+q+':depart'in onward for q in connected[i['id']]):continue
            if not self.configuration_ok(i,connected[i['id']]|extra[i['id']]|{pid}):continue
            options=list(self.candidates(source,self.return_rooms,items+proposed))
            options.sort(key=lambda row:(self.config['scoring']['reservation_repeat']*counts[row[0]['module_id']]+self.config['scoring']['reservation_area']*math.prod(row[0]['size_blocks']),row[0]['module_id'],row[0]['mirror_x'],row[0]['origin']))
            if not options:continue
            candidate,_=options[0];candidate=copy.deepcopy(candidate);candidate['id']=f'plan-{len(proposed)}'
            proposed.append(candidate);used.add((i['id'],pid));extra[i['id']].add(pid);counts[candidate['module_id']]+=1
            if len(proposed)>=limit:return proposed
        return proposed

    def growth_options(self):
        fronts=self.reachable_frontier(self.items);self.rng.shuffle(fronts);fronts=fronts[:self.config['growth_frontier_limit']]
        old=bounds(self.items);old_cost=self.shape_cost(old);cfg=self.config['shape']
        lookup=defaultdict(list)
        for _,_,p in self.frontier():lookup[tuple(p['world2'])].append(p)
        used=Counter(i['module_id']for i in self.items);mids={k for k in self.templates if k.startswith('T')};options=[];seen=set()
        for source in fronts:
            for item,pin in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']),pin)
                if key in seen:continue
                seen.add(key)
                auto=sum(any(matching(p,q)for q in lookup.get(tuple(p['world2']),[]))for p in item['ports'].values())
                x,y=item['origin'];w,h=item['size_blocks'];b=[min(old[0],x),min(old[1],y),max(old[2],x+w),max(old[3],y+h)]
                perimeter=(b[2]-b[0]+b[3]-b[1])-(old[2]-old[0]+old[3]-old[1])
                base=self.config['scoring']['auto_connection']*(auto-1)-cfg['perimeter_weight']*perimeter-(self.shape_cost(b)-old_cost)-self.config['scoring']['repeat_module']*used[item['module_id']]-cfg['left_bias']*max(0,-x)-cfg['height_bias']*abs(y)+self.rng.uniform(-self.config['scoring']['growth_noise'],self.config['scoring']['growth_noise'])
                free={r['to_port']for r in self.transit[item['module_id'],item['mirror_x'],pin]if r['to_port']!=pin and not any(matching(item['ports'][r['to_port']],q)for q in lookup.get(tuple(item['ports'][r['to_port']]['world2']),[]))}
                score=base+self.config['expansion_weights']['usable_exit']*(len(free)-1)
                if self.multi_axis:score+=cfg['vertical_exit_weight']*sum(item['ports'][pid]['face']in('TOP','BOTTOM')for pid in free)
                options.append((score,base,item,pin))
        options.sort(key=lambda x:x[0],reverse=True);ranked=[]
        for _,base,item,pin in options[:self.config['growth_shortlist']]:
            item=copy.deepcopy(item);item['id']=f'M{len(self.items)+1:02}'
            if not self.safe_state(self.items+[item]):self.rejections['seal_or_route_configuration']+=1;continue
            exits,reverse,slots,vertical,directions=self.exit_features(item,pin,self.items,lookup);weights=self.config['expansion_weights']
            score=base+weights['usable_exit']*(exits-1)+weights['bidirectional_exit']*reverse+weights['terminal_slot']*slots
            if not exits:score+=weights['dead_end']
            if self.multi_axis:score+=cfg['vertical_exit_weight']*vertical+cfg['distinct_direction_weight']*directions
            ranked.append((score,item))
        ranked.sort(key=lambda x:x[0],reverse=True);unique=[];physical=set()
        for score,item in ranked:
            key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
            if key not in physical:physical.add(key);unique.append((score,item))
        unique=unique[:self.config['growth_choice_count']]
        if self.goal_aware and len(self.items)>=cfg['reserve_from_growth_count']:
            old_capacity=len(self.reservation(self.items,self.config['reward_target']))
            scored=[]
            for score,item in unique:
                capacity=len(self.reservation(self.items+[item],self.config['reward_target']))
                scored.append((score+cfg['reserve_weight']*(capacity-old_capacity),item))
            scored.sort(key=lambda x:x[0],reverse=True);unique=scored
        choices=[i for _,i in unique]
        if choices:
            pick=self.rng.randrange(len(choices));choices=[choices[pick]]+choices[:pick]+choices[pick+1:]
        return choices

    def reward_options(self):
        if not self.goal_aware:return super().reward_options()
        remaining=self.config['reward_target']-sum(i['reward']for i in self.items)-1
        mids={k for k in self.templates if k.startswith('Q')};seen=set();options=[]
        for source in self.reachable_frontier(self.items):
            if source[0]['reward']or source[0]['module_id']in ('START','BOSS'):continue
            for item,_ in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
                if key in seen:continue
                seen.add(key);item['id']=f'M{len(self.items)+1:02}';trial=self.items+[item]
                if not self.valid_reward_state(trial):continue
                if len(self.reservation(trial,remaining,True))<remaining:
                    self.rejections['insufficient_remaining_reward_reservation']+=1;continue
                near=sum(math.hypot(item['origin'][0]-i['origin'][0],item['origin'][1]-i['origin'][1])<self.config['scoring']['reward_near_radius'] for i in self.items if i['reward'])
                options.append((self.rng.random()*self.config['scoring']['reward_noise']-near*self.config['scoring']['reward_near_penalty'],item))
        options.sort(key=lambda x:x[0],reverse=True)
        return [i for _,i in options[:self.config['reward_choice_count']]]

    def finish(self):
        if not self.goal_aware:return super().finish()
        self.phase='goal_aware_terminals';self.layout_terminal_start=self.terminal_states
        options=[]
        for source in self.reachable_frontier(self.items):
            if source[0]['module_id']=='START':continue
            for item,_ in self.candidates(source,{'BOSS'},self.items):
                item['id']=f'M{len(self.items)+1:02}';trial=self.items+[item]
                if not self.valid_reward_state(trial):continue
                if shape_metrics(trial)['aspect']>self.config['shape']['max_aspect']:continue
                graph,_,_=self.graph(trial)
                if len(actual_paths([[a,b]for a in sorted(graph)for b in graph[a]],self.config['main_paths_required']))<self.config['main_paths_required']:
                    self.rejections['boss_main_path_diversity']+=1;continue
                if len(self.reservation(trial,self.config['reward_target'],True))<self.config['reward_target']:
                    self.rejections['boss_reward_space_reservation']+=1;continue
                options.append((self.config['scoring']['boss_distance']*math.hypot(*item['origin']),item))
        options.sort(key=lambda x:x[0],reverse=True)
        if not options:self.record_failure('no_goal_and_reservation_compatible_boss');raise SearchFailure('no_goal_and_reservation_compatible_boss')
        before=copy.deepcopy(self.items);rng=self.rng.getstate()
        for _,boss in options[:self.config['boss_choice_count']]:
            self.items=copy.deepcopy(before);self.rng.setstate(rng);self.add(copy.deepcopy(boss))
            result=self.place_rewards(0)
            if result is not None:return result
        raise SearchFailure('goal_aware_reward_search_exhausted')

    def place_rewards(self,n):
        if not self.goal_aware or n!=self.config['reward_target']:return super().place_rewards(n)
        if shape_metrics(self.items)['aspect']>self.config['shape']['max_aspect']:
            self.record_failure('final_shape_envelope');return None
        try:result=assemble(self)
        except AssemblyRejected:self.record_failure('original_assembly_rejected');return None
        items=copy.deepcopy(self.items);notes,blockers=self.library.decorate(items);checked=audit(items,self.library,self.config['reward_target'])
        if blockers or checked['blockers'] or len(actual_paths(checked['edges'],self.config['main_paths_required']))<self.config['main_paths_required']:
            self.record_failure('final_independent_goal_check');return None
        return result
