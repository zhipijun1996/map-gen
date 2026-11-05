extends RefCounted
## One joint structure: reward arm, future merge, bypass and Boss.
const GEO=preload("geometry.gd")
const BRANCH=preload("reward_branch_planner.gd")
var s
var used:=0
func _init(solver):s=solver
func solve() -> bool:
	s.phase="joint_merge"
	var fronts: Array=await s.reachable_frontier(s.items)
	s.rng.shuffle(fronts)
	var prefix: Array=s.items.duplicate(true)
	for root in fronts.slice(0,s.config.search.growth_frontier_limit):
		if root[0].module_id=="START":continue
		var main_fronts: Array=fronts.filter(func(row):return row[0].id==root[0].id and row[1]!=root[1])
		if main_fronts.is_empty():continue
		var cursor=s.candidates(root,s.merge_rewards,prefix)
		cursor.options=cursor.options.duplicate();s.rng.shuffle(cursor.options)
		var row=await cursor.next()
		var seen: Dictionary={}
		while row!=null:
			var reward: Dictionary=row[0]
			var pin: String=row[1]
			var exits: Dictionary={}
			for route in s.transit[s.port_key(reward.module_id,reward.mirror_x,pin)]:
				if route.to_port!=pin and not route.reward_ids.is_empty():exits[route.to_port]=true
			if not exits.is_empty() and not seen.has(reward.module_id):
				seen[reward.module_id]=true
				for pout in exits:
					if await try_reward(prefix,root,main_fronts,reward,pout):return true
					if s.aborted() or used>=s.config.construction.macro_candidate_limit:return false
				if seen.size()>=s.config.search.reward_choice_count:break
			# Always progress, including repeated source modules/mirror poses.
			row=await cursor.next()
			if s.aborted():return false
	return false

func try_reward(prefix: Array,root: Array,main_fronts: Array,reward: Dictionary,pout: String) -> bool:
	var cursor=s.candidates([reward,pout,reward.ports[pout]],s.merge_rooms,prefix+[reward])
	cursor.options=cursor.options.duplicate();s.rng.shuffle(cursor.options)
	var row=await cursor.next()
	var seen: Dictionary={}
	while row!=null:
		var merge: Dictionary=row[0]
		var arrival: String=row[1]
		if not seen.has(merge.module_id):
			seen[merge.module_id]=true
			for onward in merge.ports:
				if onward==arrival or not GEO.permitted(merge.ports[onward],"out"):continue
				var from_reward:=false
				for route in s.transit[s.port_key(merge.module_id,merge.mirror_x,arrival)]:
					if route.to_port==onward:from_reward=true
				if not from_reward:continue
				# Propagate Boss fit BEFORE enumerating a bypass around it.
				var boss_cursor=s.candidates([merge,onward,merge.ports[onward]],{"BOSS":true},prefix+[reward,merge])
				var boss_row=await boss_cursor.next()
				if boss_row==null:continue
				for alternate in merge.ports:
					if alternate in [arrival,onward]:continue
					var from_main:=false
					for route in s.transit[s.port_key(merge.module_id,merge.mirror_x,alternate)]:
						if route.to_port==onward:from_main=true
					if not from_main:continue
					used+=1;s.construction_stats.macro_candidates+=1
					if used>s.config.construction.macro_candidate_limit:return false
					for main_front in main_fronts:
						for chain in await s.transit_index.chains(main_front,[merge,alternate,merge.ports[alternate]],prefix+[reward,merge,boss_row[0]],s.config.construction.bypass_depth,s.config.search.closure_beam_width):
							if await accept(prefix,root,main_front,reward,merge,arrival,alternate,boss_row[0],chain):return true
							if s.aborted():return false
			if seen.size()>=s.config.search.boss_choice_count:break
		row=await cursor.next()
		if s.aborted():return false
	return false

func accept(prefix: Array,root: Array,main_front: Array,reward0: Dictionary,merge0: Dictionary,arrival: String,alternate: String,boss0: Dictionary,bypass: Array) -> bool:
	s.construction_stats.bypass_trials+=1
	if s.aborted() or not await s.tick():return false
	var before: Array=s.items.duplicate(true)
	s.items=prefix.duplicate(true)
	var before_ids: Dictionary={}
	for item in prefix:before_ids[item.id]=true
	var new_core: Array=[]
	for original in bypass+[merge0]:
		var item: Dictionary=original.duplicate(true);s.add(item);new_core.append(item)
	var merge: Dictionary=new_core[-1]
	var reward: Dictionary=reward0.duplicate(true);s.add(reward)
	s.add(boss0.duplicate(true))
	var valid: bool=await s.valid_reward_state(s.items)
	if valid and s.aspect(s.items)<=s.config.shape.max_aspect:
		var g: Dictionary=(await s.graph(s.items))[0]
		var helper=BRANCH.new(s)
		var core: Dictionary=before_ids.duplicate()
		for item in new_core:core[item.id]=true
		core[s.items[-1].id]=true
		var p1: Array=await helper.path(g,"START",before_ids,{main_front[0].id+"."+main_front[1]+":depart":true})
		var allowed: Dictionary={root[0].id:true}
		for item in new_core:allowed[item.id]=true
		var p2: Array=await helper.path(g,main_front[0].id+"."+main_front[1]+":depart",allowed,{merge.id+"."+alternate+":arrive":true})
		var p3: Array=await helper.path(g,merge.id+"."+alternate+":arrive",{merge.id:true,s.items[-1].id:true},{"BOSS":true})
		if not p1.is_empty() and not p2.is_empty() and not p3.is_empty():
			var path: Array=p1+p2.slice(1)+p3.slice(1)
			if path.size()==s.unique_nodes(path):
				s.reward_core=core;s.reward_core_rank={}
				for index in range(path.size()):
					var iid: String=path[index].split(".")[0].split(":")[0]
					if core.has(iid) and not s.reward_core_rank.has(iid):s.reward_core_rank[iid]=index
				var proof: Dictionary=await BRANCH.new(s).prove([reward],root,s.items)
				if not proof.is_empty() and proof.kind=="forward_merge":
					s.terminal_states+=1
					if s.terminal_states>s.config.search.max_terminal_states:
						s.error_status="BUDGET_EXHAUSTED";s.error_message="terminal_state_budget";s.items=before;return false
					s.skeleton_path=path;s.reward_branches=[proof];s.branch_ids={reward.id:true}
					var data: Array=await s.graph(s.items);s.branch_locks={reward.id:data[2][reward.id].duplicate()}
					for item in new_core:s.base_growth_ids.append(item.id)
					s.macro_record={"entry_instance":root[0].id,"reward_instance":reward.id,"merge_instance":merge.id,"bypass_instances":new_core.map(func(item):return item.id),"main_witness":path.duplicate()}
					return true
	s.items=before;s.reward_core={};s.reward_core_rank={}
	return false
