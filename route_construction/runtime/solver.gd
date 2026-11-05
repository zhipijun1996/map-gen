extends "structure_basis.gd"
## Joint scarce-route construction, demand-driven core loops, then independent returns.
const TRANSITS=preload("transit_index.gd")
const CONSTRUCT=preload("merge_constructor.gd")
var transit_index
var merge_rewards: Dictionary={}
var merge_rooms: Dictionary={}
var base_growth_ids: Array=[]
var macro_record: Dictionary={}
var construction_stats: Dictionary={"macro_candidates":0,"bypass_queries":0,"bypass_trials":0,"core_loop_trials":0,"core_path_gains":[]}

static func unique_nodes(path: Array) -> int:
	var seen: Dictionary={}
	for node in path:seen[node]=true
	return seen.size()

func core_paths(occupied: Array,count: int) -> Array:
	var g: Dictionary=(await graph(occupied))[0]
	var edges: Array=[]
	for a in g:
		if branch_ids.has(a.split(".")[0].split(":")[0]):continue
		for b in g[a]:
			if not branch_ids.has(b.split(".")[0].split(":")[0]):edges.append([a,b])
	return await actual_paths(edges,count)

func topology_ready() -> bool:
	if (await core_paths(items,config.goals.main_paths_required)).size()<config.goals.main_paths_required:return false
	# Keep the constructed core witness; shortest paths may prefer the reward arm.
	reward_core={};reward_core_rank={}
	for item in items:
		if not branch_ids.has(item.id):reward_core[item.id]=true
	for index in range(skeleton_path.size()):
		var iid: String=skeleton_path[index].split(".")[0].split(":")[0]
		if reward_core.has(iid) and not reward_core_rank.has(iid):reward_core_rank[iid]=index
	return true

func grow_base_to(count: int) -> bool:
	var before: Dictionary={}
	for item in items:before[item.id]=true
	growth_offset=items.size()-base_growth_ids.size()
	if not await grow_to(count):return false
	for item in items:
		if not before.has(item.id):base_growth_ids.append(item.id)
	return true

func close_one(_max_depth: int) -> bool:
	if config.construction.core_loop_policy=="legacy":return await super.close_one(_max_depth)
	phase="demand_core_routes"
	var required: int=config.goals.main_paths_required
	var old_count: int=(await core_paths(items,required)).size()
	if old_count>=required:return true
	var fronts: Array=await reachable_frontier(items)
	rng.shuffle(fronts)
	var potential: Dictionary=(await graph(items,true))[0]
	var back: Dictionary=await reverse_reachable(potential,"BOSS")
	var pairs: Array=[]
	for source in fronts.slice(0,config.search.closure_source_limit):
		if source[0].module_id=="START":continue
		for target in GEO.frontier(items):
			if target[0].id==source[0].id or branch_ids.has(target[0].id) or not GEO.permitted(target[2],"in"):continue
			if not back.has(target[0].id+"."+target[1]+":arrive"):continue
			var dist: int=distance2(source[2],target[2])
			if dist<config.search.closure_target_distance2:pairs.append([dist,source,target])
	pairs=await sort_rows(pairs,func(a,b):return a[0]<b[0])
	for pair in pairs:
		for chain in await transit_index.chains(pair[1],pair[2],items,mini(2,_max_depth),config.search.closure_beam_width):
			if chain.is_empty():continue
			construction_stats.core_loop_trials+=1
			var trial: Array=items.duplicate(true)
			for original in chain:
				var item: Dictionary=original.duplicate(true);item.id="M%02d" % (trial.size()+1);trial.append(item)
			if aspect(trial)>config.shape.max_aspect or not await valid_reward_state(trial):continue
			var new_count: int=(await core_paths(trial,required)).size()
			if new_count<=old_count:continue
			items=trial;construction_stats.core_path_gains.append([old_count,new_count]);return true
		if aborted():return false
	return false

func complete_infill(_prefix: int) -> bool:
	structure_stats.infill_attempts+=1
	var before: Array=items.duplicate(true)
	var before_ids: Dictionary={}
	for item in before:before_ids[item.id]=true
	var previous_locks: Dictionary=branch_locks.duplicate(true)
	var previous_branches: Dictionary=branch_ids.duplicate()
	var previous_offset: int=growth_offset
	for branch in reward_branches:
		for iid in branch.instance_ids:branch_ids[iid]=true
	var data: Array=await graph(items)
	for iid in branch_ids:branch_locks[iid]=data[2][iid].duplicate()
	growth_offset=items.size()-base_growth_ids.size()
	if await grow_to(config.goals.growth_target):
		growth_instance_ids=base_growth_ids.duplicate()
		for item in items:
			if not before_ids.has(item.id):growth_instance_ids.append(item.id)
		growth_target_reached=growth_instance_ids.size()==config.goals.growth_target
		for item in items:
			if not branch_ids.has(item.id):reward_core[item.id]=true
		air_connected=await add_air_loop() if request.air_loop.enabled else false
		if growth_target_reached and await final_accept():return true
	items=before;branch_locks=previous_locks;branch_ids=previous_branches;growth_offset=previous_offset;growth_target_reached=false
	return false

func build() -> bool:
	blueprint={"reward_modes":config.topology.reward_modes.duplicate(),"backbone_growth_count":config.topology.backbone_min+rng.randrange(config.topology.backbone_max-config.topology.backbone_min+1),"main_paths_required":config.goals.main_paths_required}
	phase="transit_catalog";transit_index=TRANSITS.new(self)
	if not await transit_index.build():return false
	construction_stats.transit_legs=transit_index.count
	for mid in qids:
		for route in templates[mid].routes:
			if route.from_port!=route.to_port and not route.reward_ids.is_empty() and has_abilities(route.required_abilities):merge_rewards[mid]=true
	for mid in tids:
		if templates[mid].ports.size()>=3:merge_rooms[mid]=true
	phase="motif_catalog";motif_catalog=MOTIFS.new(self)
	if not await motif_catalog.build():return false
	structure_stats.motif_count=motif_catalog.count
	for attempt in range(config.search.max_layout_repairs+1):
		if aborted():return false
		repairs=attempt;items=[];reward_branches=[];reward_core={};reward_core_rank={};branch_ids={};branch_locks={};growth_offset=0;base_growth_ids=[];macro_record={};skeleton_path=[]
		add(make("START",request.start_origin_blocks[0],request.start_origin_blocks[1]));base_growth_ids.append(items[0].id)
		if not await grow_base_to(config.construction.anchor_growth_count):record_failure("joint_anchor_growth_exhausted");continue
		var constructed:=false
		for count in range(config.construction.anchor_growth_count,config.construction.max_anchor_growth_count+1):
			if count>base_growth_ids.size() and not await grow_base_to(count):break
			if await CONSTRUCT.new(self).solve():constructed=true;break
			if aborted():return false
		if not constructed:record_failure("joint_forward_macro_domain_empty");continue
		if not await grow_base_to(blueprint.backbone_growth_count):record_failure("joint_scaffold_growth_exhausted");continue
		var ready: bool=await topology_ready()
		for _step in range(config.search.close_attempts):
			if ready:break
			if await close_one(config.search.close_depth):closed_loops+=1
			ready=await topology_ready()
		if not ready:record_failure("joint_core_paths_domain_empty");continue
		if await STRUCTURE.new(self).solve(blueprint.backbone_growth_count):return true
		record_failure("joint_remaining_returns_or_infill_exhausted")
	if aborted():return false
	error_status="SEARCH_EXHAUSTED";error_message="joint_construction_exhausted";return false

func diagnostics() -> Dictionary:
	var value: Dictionary=super.diagnostics()
	value.joint_construction=construction_stats.duplicate(true)
	value.joint_macro=macro_record.duplicate(true)
	value.algorithm_scope="jointly construct reward/future merge/core bypass/Boss before scaffold; only accept loops increasing core path count; original static full audit, not physics"
	return value
