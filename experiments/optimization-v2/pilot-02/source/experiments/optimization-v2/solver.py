"""Spatial objectives and goal-aware reservations over the frozen v1 solver."""
import copy
from collections import Counter,defaultdict,deque
import importlib.util
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('optimization_v1_solver',ROOT/'experiments/optimization-v1/solver.py')
v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)
Base=v1.Optimized;SearchFailure=v1.SearchFailure;BudgetExhausted=v1.BudgetExhausted
RealLibrary=v1.RealLibrary;audit=v1.audit;legacy=v1.legacy;model=v1.model;package=v1.package;read=v1.read
from metrics import actual_paths,shape_metrics


class Spatial(Base):
    def __init__(self,seed,library,profile,config):
        super().__init__(seed,library,'backtrack',config)
        self.profile=profile;self.variant=profile
        self.multi_axis=profile in ('spatial','stable');self.goal_aware=profile=='stable'
        self.return_rooms={k for k,t in model.LIB.items()if k.startswith('Q')and len(t['ports'])==1 and any(r['from_port']==r['to_port']and r['reward_ids']for r in t['routes'])}

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
        tids={k for k in model.LIB if k.startswith('T')};roles={k for k in model.LIB if k.startswith('Q')}|{'BOSS'}
        connected={pid for pid,p in item['ports'].items()if any(legacy.matching(p,q)for q in lookup.get(tuple(p['world2']),[]))}
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
        graph,_,connected=self.graph(items,potential=True);seen=v1.reachable(graph,'START')
        proposed=[];used=set();extra=defaultdict(set);counts=Counter()
        for source in self.frontier(items):
            i,pid,p=source
            if i['reward']or i['module_id']in ('START','BOSS'):continue
            if i['id']+'.'+pid+':depart'not in seen or not model.permitted(p,'in'):continue
            onward=v1.reachable(graph,i['id']+'.'+pid+':arrive')
            if require_boss:
                if 'BOSS'not in onward:continue
            elif not any(i['id']+'.'+q+':depart'in onward for q in connected[i['id']]):continue
            if not self.configuration_ok(i,connected[i['id']]|extra[i['id']]|{pid}):continue
            options=list(self.candidates(source,self.return_rooms,items+proposed))
            options.sort(key=lambda row:(5*counts[row[0]['module_id']]+.1*math.prod(row[0]['size_blocks']),row[0]['module_id'],row[0]['mirror_x'],row[0]['origin']))
            if not options:continue
            candidate,_=options[0];candidate=copy.deepcopy(candidate);candidate['id']=f'plan-{len(proposed)}'
            proposed.append(candidate);used.add((i['id'],pid));extra[i['id']].add(pid);counts[candidate['module_id']]+=1
            if len(proposed)>=limit:return proposed
        return proposed

    def growth_options(self):
        fronts=self.reachable_frontier(self.items);self.rng.shuffle(fronts);fronts=fronts[:self.config['growth_frontier_limit']]
        old=legacy.bounds(self.items);old_cost=self.shape_cost(old);cfg=self.config['shape']
        lookup=defaultdict(list)
        for _,_,p in self.frontier():lookup[tuple(p['world2'])].append(p)
        used=Counter(i['module_id']for i in self.items);mids={k for k in model.LIB if k.startswith('T')};options=[];seen=set()
        for source in fronts:
            for item,pin in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']),pin)
                if key in seen:continue
                seen.add(key)
                auto=sum(any(legacy.matching(p,q)for q in lookup.get(tuple(p['world2']),[]))for p in item['ports'].values())
                x,y=item['origin'];w,h=item['size_blocks'];b=[min(old[0],x),min(old[1],y),max(old[2],x+w),max(old[3],y+h)]
                perimeter=(b[2]-b[0]+b[3]-b[1])-(old[2]-old[0]+old[3]-old[1])
                base=24*(auto-1)-cfg['perimeter_weight']*perimeter-(self.shape_cost(b)-old_cost)-5*used[item['module_id']]-cfg['left_bias']*max(0,-x)-cfg['height_bias']*abs(y)+self.rng.uniform(-3,3)
                free={r['to_port']for r in self.transit[item['module_id'],item['mirror_x'],pin]if r['to_port']!=pin and not any(legacy.matching(item['ports'][r['to_port']],q)for q in lookup.get(tuple(item['ports'][r['to_port']]['world2']),[]))}
                score=base+self.config['expansion_weights']['usable_exit']*(len(free)-1)
                if self.multi_axis:score+=cfg['vertical_exit_weight']*sum(item['ports'][pid]['face']in('TOP','BOTTOM')for pid in free)
                options.append((score,base,item,pin))
        options.sort(key=lambda x:x[0],reverse=True);ranked=[]
        for _,base,item,pin in options[:self.config['closure_beam_width']]:
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
        mids={k for k in model.LIB if k.startswith('Q')};seen=set();options=[]
        for source in self.reachable_frontier(self.items):
            if source[0]['reward']or source[0]['module_id']in ('START','BOSS'):continue
            for item,_ in self.candidates(source,mids,self.items):
                key=(item['module_id'],item['mirror_x'],tuple(item['origin']))
                if key in seen:continue
                seen.add(key);item['id']=f'M{len(self.items)+1:02}';trial=self.items+[item]
                if not self.valid_reward_state(trial):continue
                if len(self.reservation(trial,remaining,True))<remaining:
                    self.rejections['insufficient_remaining_reward_reservation']+=1;continue
                near=sum(math.hypot(item['origin'][0]-i['origin'][0],item['origin'][1]-i['origin'][1])<8 for i in self.items if i['reward'])
                options.append((self.rng.random()*4-near*5,item))
        options.sort(key=lambda x:x[0],reverse=True)
        return [i for _,i in options[:self.config['growth_choice_count']]]

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
                if len(actual_paths([[a,b]for a in sorted(graph)for b in graph[a]]))<self.config['main_paths_required']:
                    self.rejections['boss_main_path_diversity']+=1;continue
                if len(self.reservation(trial,self.config['reward_target'],True))<self.config['reward_target']:
                    self.rejections['boss_reward_space_reservation']+=1;continue
                options.append((math.hypot(*item['origin']),item))
        options.sort(key=lambda x:x[0],reverse=True)
        if not options:self.record_failure('no_goal_and_reservation_compatible_boss');raise SearchFailure('no_goal_and_reservation_compatible_boss')
        before=copy.deepcopy(self.items);rng=self.rng.getstate()
        for _,boss in options[:self.config['growth_choice_count']]:
            self.items=copy.deepcopy(before);self.rng.setstate(rng);self.add(copy.deepcopy(boss))
            result=self.place_rewards(0)
            if result is not None:return result
        raise SearchFailure('goal_aware_reward_search_exhausted')

    def place_rewards(self,n):
        if not self.goal_aware or n!=self.config['reward_target']:return super().place_rewards(n)
        if shape_metrics(self.items)['aspect']>self.config['shape']['max_aspect']:
            self.record_failure('final_shape_envelope');return None
        try:result=legacy.assemble(self)
        except AssertionError:self.record_failure('original_assembly_rejected');return None
        items=copy.deepcopy(self.items);notes,blockers=self.library.decorate(items);checked=audit(items)
        if blockers or checked['blockers'] or len(actual_paths(checked['edges']))<self.config['main_paths_required']:
            self.record_failure('final_independent_goal_check');return None
        return result


def create_solver(seed,library,profile,config):
    return Base(seed,library,'backtrack',config)if profile=='baseline'else Spatial(seed,library,profile,config)
