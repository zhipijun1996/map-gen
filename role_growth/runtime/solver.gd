extends "joint_basis.gd"
const ROLE_CURSOR=preload("role_cursor.gd")
var funnel: Dictionary={}
var responsibility_counts: Dictionary={}
var role_trials:=0
var growth_stage: String="scaffold"
func grow_base_to(count: int) -> bool:
	growth_stage="scaffold";return await super.grow_base_to(count)
func complete_infill(prefix: int) -> bool:
	growth_stage="infill";return await super.complete_infill(prefix)
func observe(mid: String,stage: String):
	var key: String=templates[mid].source_module_id
	if not funnel.has(key):funnel[key]={}
	funnel[key][stage]=funnel[key].get(stage,0)+1
func candidates(source: Array,mids: Dictionary,occupied: Array):return ROLE_CURSOR.new(self,source,mids,occupied)
func large(item: Dictionary) -> bool:return item.size_blocks[0]*item.size_blocks[1]>=config.growth_roles.large_min_area and templates[item.module_id].ports.size()<=2 and item.module_id not in ["START","BOSS"] and not item.reward
func add(item: Dictionary) -> void:
	super.add(item)
	if item.has("growth_role"):
		observe(item.module_id,"committed_growth_attempt")
		responsibility_counts[item.growth_role]=responsibility_counts.get(item.growth_role,0)+1
func fork_state(occupied: Array) -> Dictionary:
	var data: Array=await graph(occupied)
	var seen: Dictionary=await reachable(data[0],"START")
	var forks: Dictionary={}
	for item in occupied:
		var connected: Dictionary=data[2][item.id]
		var choices: Dictionary={}
		for route in routes[local_key(item.module_id,item.mirror_x)]:
			if route.from_port==route.to_port or not connected.has(route.from_port) or not connected.has(route.to_port):continue
			if not seen.has(item.id+"."+route.from_port+":arrive"):continue
			if not choices.has(route.from_port):choices[route.from_port]={}
			choices[route.from_port][route.to_port]=true
		for exits in choices.values():
			if exits.size()>=2:forks[item.id]=true;break
	var pairs: Dictionary={}
	for group in GEO.connection_groups(occupied):
		var a: String=group[0][0].id;var b: String=group[1][0].id
		if forks.has(a) and forks.has(b):
			var ids: Array=[a,b];ids.sort();pairs[ids]=true
	return {"forks":forks.size(),"adjacent_pairs":pairs.size()}
func growth_options() -> Array:
	var cfg: Dictionary=config.growth_roles
	if not cfg.enabled:return await super.growth_options()
	var fronts: Array=await reachable_frontier(items);rng.shuffle(fronts)
	var count_large:=0;var counts: Dictionary={}
	for item in items:
		if large(item):count_large+=1
		var mid: String=templates[item.module_id].source_module_id;counts[mid]=counts.get(mid,0)+1
	var role: String="extend"
	if cfg.role_enabled and (growth_stage=="scaffold" or fronts.size()<cfg.frontier_target):role="branch_supply"
	if cfg.large_enabled and ((items.size()<=cfg.early_large_limit and count_large<cfg.early_large_target) or (growth_stage=="infill" and count_large<cfg.early_large_target)):role="large_challenge"
	var old: Array=GEO.bounds(items);var options: Array=[];var seen: Dictionary={}
	for source in fronts.slice(0,config.search.growth_frontier_limit):
		var cursor=candidates(source,tids,items);var row=await cursor.next()
		while row!=null:
			var item: Dictionary=row[0];var key: Array=[item.module_id,item.mirror_x,item.origin,row[1]]
			if not seen.has(key):
				seen[key]=true;observe(item.module_id,"growth_ranked")
				var exits: Dictionary={}
				for route in transit[port_key(item.module_id,item.mirror_x,row[1])]:
					if route.to_port!=row[1]:exits[route.to_port]=true
				var mid: String=templates[item.module_id].source_module_id
				var b: Array=[mini(old[0],item.origin[0]),mini(old[1],item.origin[1]),maxi(old[2],item.origin[0]+item.size_blocks[0]),maxi(old[3],item.origin[1]+item.size_blocks[1])]
				var score: float=-config.scoring.repeat_module*counts.get(mid,0)-NUM.shape_cost(b,config)
				if role=="branch_supply" or not cfg.role_enabled:score+=config.scoring.usable_exit*exit_value(exits.size())
				else:score+=config.scoring.usable_exit*mini(1,exits.size())-cfg.continue_exit_penalty*maxi(0,exits.size()-1)
				if role=="large_challenge" and large(item):score+=cfg.large_bonus
				score+=rng.uniform(-config.scoring.growth_noise,config.scoring.growth_noise)
				item.growth_role=role;item.growth_parent=source[0].id;options.append([score,item])
			row=await cursor.next()
		if aborted():return []
	options=await sort_rows(options,func(a,b):return a[0]>b[0])
	var previous: Dictionary=await fork_state(items) if cfg.spacing_enabled else {}
	var ranked: Array=[];var used: Dictionary={};var tested:=0
	for option in options:
		var item: Dictionary=option[1];var mid: String=templates[item.module_id].source_module_id
		if used.has(mid):continue
		item.id="M%02d" % (items.size()+1);observe(item.module_id,"growth_checked")
		if not await safe_state(items+[item]):observe(item.module_id,"seal_or_route_rejected");continue
		if aspect(items+[item])>config.shape.max_aspect:observe(item.module_id,"aspect_rejected");continue
		used[mid]=true;observe(item.module_id,"growth_valid")
		if cfg.spacing_enabled and role!="branch_supply":
			var state: Dictionary=await fork_state(items+[item]);role_trials+=1
			option[0]-=cfg.adjacent_fork_penalty*maxi(0,state.adjacent_pairs-previous.adjacent_pairs)
			if role!="branch_supply":option[0]-=cfg.new_fork_penalty*maxi(0,state.forks-previous.forks)
		ranked.append(option);tested+=1
		if tested>=config.search.growth_shortlist:break
		if aborted():return []
	ranked=await sort_rows(ranked,func(a,b):return a[0]>b[0]);var choices: Array=[]
	for option in ranked:
		if choices.size()>=config.search.growth_choice_count:break
		if role!="branch_supply" and option[0]<ranked[0][0]-cfg.selection_slack and not choices.is_empty():break
		observe(option[1].module_id,"growth_shortlisted");choices.append(option[1])
	if not choices.is_empty():
		var pick: int=rng.randrange(choices.size());choices=[choices[pick]]+choices.slice(0,pick)+choices.slice(pick+1)
	return choices
func diagnostics() -> Dictionary:
	var value: Dictionary=super.diagnostics();var assigned: Array=[]
	for item in items:
		if item.has("growth_role"):assigned.append({"instance_id":item.id,"module_id":templates[item.module_id].source_module_id,"role":item.growth_role,"parent_instance":item.growth_parent,"large":large(item)})
	value.growth_roles={"funnel":funnel.duplicate(true),"attempt_counts":responsibility_counts.duplicate(),"final_assignments":assigned,"spacing_trials":role_trials,"scope":"observation counters include retries; role/large/spacing are preferences, actual final graph audited separately"};return value
