extends RefCounted
## Bounded data search. Only declared directed Routes; no inferred reverse edges.
const GEO = preload("geometry.gd")
const NUM = preload("numeric.gd")
var s
var policy: Dictionary
var core: Dictionary
var rank: Dictionary
var counts: Dictionary = {}
var reward_counts: Dictionary = {}
var targets: Array = []

func _init(solver):
	s = solver
	policy = s.config.diversity
	core = s.reward_core
	rank = s.reward_core_rank
	for item in s.items:
		var mid: String = s.templates[item.module_id].source_module_id
		counts[mid] = counts.get(mid,0)+1
		if item.reward: reward_counts[mid] = reward_counts.get(mid,0)+1
	for port in GEO.frontier(s.items):
		if core.has(port[0].id) and GEO.permitted(port[2],"in"):
			targets.append(port)

func signature(chain: Array) -> String:
	var rows: Array = []
	for item in chain: rows.append([item.module_id,item.mirror_x,item.origin])
	return JSON.stringify(rows)

func chain_score(chain: Array) -> float:
	var total := 0.0
	var local: Dictionary = {}
	for item in chain:
		var mid: String = s.templates[item.module_id].source_module_id
		if item.reward:
			total -= policy.reward_repeat_penalty*reward_counts.get(mid,0)
		else:
			total -= policy.connector_repeat_penalty*(counts.get(mid,0)+local.get(mid,0))
		total -= s.config.scoring.reservation_area*item.size_blocks[0]*item.size_blocks[1]
		local[mid] = local.get(mid,0)+1
	return total+policy.branch_length_bonus*chain.size()

func actual_connected(item: Dictionary, occupied: Array) -> Dictionary:
	var selected: Dictionary = {}
	for other in occupied:
		for pid in item.ports:
			for port in other.ports.values():
				if GEO.matching(item.ports[pid],port): selected[pid] = true
	return selected

func core_join(item: Dictionary, source_id: String) -> bool:
	for port in item.ports.values():
		if not GEO.permitted(port,"out"): continue
		for target in targets:
			if target[0].id != source_id and GEO.matching(port,target[2]): return true
	return false

func distance_to_core(port: Dictionary, source_id: String) -> int:
	var nearest := 1000000
	for target in targets:
		if target[0].id != source_id and port.surface == target[2].surface:
			nearest = mini(nearest,s.distance2(port,target[2]))
	return nearest

func options() -> Array:
	s.phase = "reward_branches"
	var fronts: Array = await s.reachable_frontier(s.items)
	s.rng.shuffle(fronts)
	fronts = fronts.filter(func(row):return core.has(row[0].id) and row[0].module_id not in ["START","BOSS"])
	# Prefer actual validated main-path instances, but retain reachable core arms.
	fronts = await s.sort_rows(fronts,func(a,b):return int(rank.has(a[0].id)) > int(rank.has(b[0].id)))
	var beam: Array = []
	for source in fronts.slice(0,policy.branch_source_limit):
		beam.append({"chain":[],"front":source,"root":source,"collected":false,"returnable":true})
	var completed: Array = []
	var completed_keys: Dictionary = {}
	# Single-room returns are explicit base cases of this planner, not an old
	# generator fallback. Keep simultaneously placeable witnesses represented
	# even when speculative multi-room beams have many attractive dead ends.
	var placed: int = reward_counts.values().reduce(func(a,b):return a+b,0)
	var reserve: Array = await s.reservation(s.items,s.config.goals.reward_target-placed,true)
	var base_cases: Array = []
	for original in reserve:
		var item: Dictionary = original.duplicate(true)
		item.id = "M%02d" % (s.items.size()+1)
		for source in await s.reachable_frontier(s.items):
			if not core.has(source[0].id): continue
			var matches := false
			for port in item.ports.values():
				if GEO.matching(port,source[2]): matches=true
			if matches:
				base_cases.append({"chain":[item],"root":source,"score":chain_score([item])})
				break
	for depth in range(policy.branch_depth):
		var pending: Array = []
		for state in beam:
			var mids: Dictionary = s.tids.duplicate()
			if not state.collected: mids.merge(s.qids)
			var occupied: Array = s.items+state.chain
			var cursor = s.candidates(state.front,mids,occupied)
			var row = await cursor.next()
			while row != null:
				var item: Dictionary = row[0]
				var pin: String = row[1]
				item.id = "M%02d" % (s.items.size()+state.chain.size()+1)
				var chain: Array = state.chain+[item]
				var collected: bool = state.collected or item.reward
				var value: float = chain_score(chain)
				var physical := signature(chain)
				var connections := actual_connected(item,occupied)
				var joins := collected and core_join(item,state.root[0].id)
				var routes: Array = s.transit[s.port_key(item.module_id,item.mirror_x,pin)]
				var self_reward := false
				for route in routes:
					if item.reward and route.to_port == pin and not route.reward_ids.is_empty(): self_reward = true
				if collected and (joins or (item.reward and self_reward and state.returnable)) and not completed_keys.has(physical):
					completed_keys[physical] = true
					var bonus: float = policy.merge_bonus if joins else policy.multi_return_bonus if chain.size()>1 else 0.0
					completed.append({"chain":chain,"root":state.root,"hint":"merge" if joins else "multi_return" if chain.size()>1 else "single_return","score":value+bonus+s.rng.random()*s.config.scoring.reward_noise})
				var exits: Dictionary = {}
				for route in routes:
					if route.to_port == pin or (item.reward and route.reward_ids.is_empty()): continue
					exits[route.to_port] = true
				var ids: Array = exits.keys(); ids.sort()
				for pid in ids:
					if connections.has(pid): continue
					var selected := connections.duplicate(); selected[pin]=true; selected[pid]=true
					# Cache-backed original local clearance, including all reward sites.
					if not await s.configuration_ok(item,selected): continue
					var reverse := false
					for route in s.transit[s.port_key(item.module_id,item.mirror_x,pid)]:
						if route.to_port == pin: reverse = true
					var heuristic: float = value-0.25*distance_to_core(item.ports[pid],state.root[0].id)+(policy.multi_return_bonus if state.returnable and reverse else 0.0)
					pending.append({"chain":chain,"front":[item,pid,item.ports[pid]],"root":state.root,"collected":collected,"returnable":state.returnable and reverse,"score":heuristic})
				row = await cursor.next()
			if s.aborted(): return []
		pending = await s.sort_rows(pending,func(a,b):return a.score>b.score)
		beam=[]
		var groups: Dictionary = {}
		var phases: Dictionary = {}
		for state in pending:
			var group: String = str(state.collected)+s.templates[state.front[0].module_id].source_module_id
			if groups.get(group,0)>=2 or phases.get(state.collected,0)>=maxi(1,int(policy.branch_beam_width)/2): continue
			groups[group]=groups.get(group,0)+1
			phases[state.collected]=phases.get(state.collected,0)+1
			beam.append(state)
			if beam.size()>=policy.branch_beam_width: break
		if beam.is_empty(): break
	completed = await s.sort_rows(completed,func(a,b):return a.score>b.score)
	var choices: Array = []
	var signatures: Dictionary = {}
	var considered: Array = []
	var remaining_slots: int = maxi(0,policy.branch_completion_limit-base_cases.size())
	var hints: Dictionary = {}
	for option in completed:
		if hints.get(option.hint,0)>=maxi(1,remaining_slots/2): continue
		hints[option.hint]=hints.get(option.hint,0)+1
		considered.append(option)
		if considered.size()>=remaining_slots: break
	considered+=base_cases
	var checked: Dictionary = {}
	for option in considered:
		var key := signature(option.chain)
		if checked.has(key): continue
		checked[key]=true
		var trial: Array = s.items+option.chain
		if s.aspect(trial)>s.config.shape.max_aspect: continue
		if not await s.valid_reward_state(trial):
			s.reject("branch_candidate_invalid_state"); continue
		var proof: Dictionary = await prove(option.chain,option.root,trial)
		if proof.is_empty():
			s.reject("reward_branch_no_independent_core_path"); continue
		var remaining: int = s.config.goals.reward_target-placed-1
		# Conservative feasible reserve, not a claim every remaining branch must fold.
		if (await s.reservation(trial,remaining,true)).size()<remaining:
			s.reject("insufficient_remaining_reward_reservation"); continue
		var reward_mid := ""
		for item in option.chain:
			if item.reward: reward_mid=s.templates[item.module_id].source_module_id
		var diversity_key: String=reward_mid+"/"+proof.kind
		if signatures.has(diversity_key): continue
		signatures[diversity_key]=true
		option.proof=proof
		# Re-sort by proved kind; physical auto-contact alone is not a merge proof.
		option.score=chain_score(option.chain)+(policy.merge_bonus if proof.kind=="forward_merge" else policy.merge_bonus*0.75 if proof.kind=="core_merge" else policy.multi_return_bonus if proof.kind=="multi_return" else 0.0)
		choices.append(option)
		if choices.size()>=s.config.search.reward_choice_count: break
	return await s.sort_rows(choices,func(a,b):return a.score>b.score)

func path(g: Dictionary, start: String, allowed: Dictionary, goals: Dictionary) -> Array:
	var queue: Array = [start]
	var parent: Dictionary = {start:""}
	var position := 0
	while position<queue.size():
		if not await s.checkpoint(): return []
		var node: String=queue[position]; position+=1
		if goals.has(node):
			var result: Array=[]
			while not node.is_empty(): result.push_front(node); node=parent[node]
			return result
		for neighbor in g.get(node,[]):
			if not parent.has(neighbor) and (allowed.has(neighbor.split(".")[0].split(":")[0]) or goals.has(neighbor)):
				parent[neighbor]=node; queue.append(neighbor)
	return []

func prove(chain: Array, root: Array, trial: Array) -> Dictionary:
	var data: Array = await s.graph(trial)
	var g: Dictionary = data[0]
	var allowed: Dictionary = {}
	var reward_id := ""
	for item in chain:
		allowed[item.id]=true
		if item.reward: reward_id=item.id
	var reward_nodes: Dictionary = {}
	for pair in data[1]:
		if pair[0]==reward_id: reward_nodes[pair[1]]=true
	var outbound: Array=await path(g,root[0].id+"."+root[1]+":depart",allowed,reward_nodes)
	if outbound.is_empty(): return {}
	var can_finish: Dictionary=await s.reverse_reachable(g,"BOSS")
	var forward: Dictionary={}
	var merged: Dictionary={}
	var returned: Dictionary={}
	for node in g:
		var iid: String=node.split(".")[0].split(":")[0]
		if not core.has(iid) or not node.ends_with(":arrive") or not can_finish.has(node): continue
		if iid==root[0].id: returned[node]=true
		else:
			merged[node]=true
			if rank.has(iid) and rank.has(root[0].id) and rank[iid]>rank[root[0].id]: forward[node]=true
	for category in [["forward_merge",forward],["core_merge",merged],["multi_return" if chain.size()>1 else "single_return",returned]]:
		var onward: Array=await path(g,outbound[-1],allowed,category[1])
		if not onward.is_empty():
			var used: Dictionary={}
			for node in outbound+onward:
				var iid: String=node.split(".")[0].split(":")[0]
				if allowed.has(iid): used[iid]=true
			# Extra placed rooms must actually participate in the witness. Do not
			# relabel a single-room return as multi-room by adding unused padding.
			if used.size()!=allowed.size(): continue
			return {"kind":category[0],"instance_ids":allowed.keys(),"reward_instance_id":reward_id,"entry_instance_id":root[0].id,"entry_port_id":root[1],"outbound_path":outbound,"onward_path":onward,"scope":"declared directed graph witness; not physics or proof return is forbidden"}
	return {}
