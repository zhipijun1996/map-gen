extends "solver_basis.gd"
## Structure first: executable backbone/loops, hard reward motifs, then infill.
const MOTIFS=preload("motif_catalog.gd")
const STRUCTURE=preload("structure_planner.gd")
var motif_catalog
var growth_instance_ids: Array=[]
var blueprint: Dictionary={}
var structure_stats: Dictionary={"domain_sizes":[],"domain_prunes":0,"assignments":0,"infill_attempts":0}
var branch_locks: Dictionary={}
var skeleton_path: Array=[]
var growth_offset:=0
var branch_ids: Dictionary={}
var growth_target_reached:=false

func known_capacity(_occupied: Array) -> int:
	# This algorithm places full reward motifs; single-room reserve is unused.
	return 0

func reachable_frontier(occupied: Array) -> Array:
	var rows: Array=await super.reachable_frontier(occupied)
	return rows.filter(func(row):return not branch_ids.has(row[0].id) and row[0].module_id!="BOSS")

func safe_state(occupied: Array) -> bool:
	if not await super.safe_state(occupied):return false
	if not branch_locks.is_empty():
		var data: Array=await graph(occupied)
		for iid in branch_locks:
			if data[2].get(iid,{})!=branch_locks[iid]:
				reject("committed_branch_boundary_changed");return false
	return true

func growth_options() -> Array:
	# Ordinary infill has no reward-reserve lookahead: motifs already occupy space.
	var fronts: Array=await reachable_frontier(items)
	rng.shuffle(fronts)
	var counts: Dictionary={}
	for item in items:
		var mid: String=templates[item.module_id].source_module_id
		counts[mid]=counts.get(mid,0)+1
	var old: Array=GEO.bounds(items)
	var options: Array=[]
	var seen: Dictionary={}
	for source in fronts.slice(0,config.search.growth_frontier_limit):
		var cursor=candidates(source,tids,items)
		var row=await cursor.next()
		while row!=null:
			var item: Dictionary=row[0]
			var key: Array=[item.module_id,item.mirror_x,item.origin]
			if not seen.has(key):
				seen[key]=true
				var exits: Dictionary={}
				for route in transit[port_key(item.module_id,item.mirror_x,row[1])]:
					if route.to_port!=row[1]:exits[route.to_port]=true
				var mid: String=templates[item.module_id].source_module_id
				var b: Array=[mini(old[0],item.origin[0]),mini(old[1],item.origin[1]),maxi(old[2],item.origin[0]+item.size_blocks[0]),maxi(old[3],item.origin[1]+item.size_blocks[1])]
				var score: float=-config.scoring.repeat_module*counts.get(mid,0)-NUM.shape_cost(b,config)+config.scoring.usable_exit*exit_value(exits.size())
				score+=rng.uniform(-config.scoring.growth_noise,config.scoring.growth_noise)
				options.append([score,item])
			row=await cursor.next()
		if aborted():return []
	options=await sort_rows(options,func(a,b):return a[0]>b[0])
	var choices: Array=[]
	var used: Dictionary={}
	for option in options:
		var item: Dictionary=option[1]
		var mid: String=templates[item.module_id].source_module_id
		if used.has(mid):continue
		item.id="M%02d" % (items.size()+1)
		if not await safe_state(items+[item]):continue
		if aspect(items+[item])>config.shape.max_aspect:continue
		used[mid]=true;choices.append(item)
		if choices.size()>=config.search.growth_choice_count:break
	if not choices.is_empty():
		var pick: int=rng.randrange(choices.size())
		choices=[choices[pick]]+choices.slice(0,pick)+choices.slice(pick+1)
	return choices

func grow_to(count: int) -> bool:
	phase="growth"
	frames=[]
	while items.size()<count+growth_offset and not aborted():
		var choices: Array=await growth_options()
		if choices.is_empty():
			if rewind():continue
			return false
		var first: Dictionary=choices.pop_front()
		frames.append({"before":items.duplicate(true),"choices":choices,"rng":rng.getstate()})
		add(first.duplicate(true))
	return not aborted()

func skeleton_boss() -> bool:
	phase="structure_backbone"
	var options: Array=[]
	for source in await reachable_frontier(items):
		var cursor=candidates(source,{"BOSS":true},items)
		var row=await cursor.next()
		while row!=null:
			var item: Dictionary=row[0];item.id="M%02d" % (items.size()+1)
			if aspect(items+[item])<=config.shape.max_aspect and await valid_reward_state(items+[item]):
				options.append([origin_distance(item.origin),item])
			row=await cursor.next()
	options=await sort_rows(options,func(a,b):return a[0]>b[0])
	if options.is_empty():return false
	add(options[rng.randrange(mini(options.size(),config.search.boss_choice_count))][1])
	return true

func topology_ready() -> bool:
	var paths: Array=await actual_paths(graph_edges((await graph(items))[0]),config.goals.main_paths_required)
	if paths.size()<config.goals.main_paths_required:return false
	skeleton_path=paths[0]
	reward_core={};reward_core_rank={}
	for item in items:reward_core[item.id]=true
	for index in range(skeleton_path.size()):
		var iid: String=skeleton_path[index].split(".")[0].split(":")[0]
		if reward_core.has(iid) and not reward_core_rank.has(iid):reward_core_rank[iid]=index
	return true

func complete_infill(prefix_count: int) -> bool:
	structure_stats.infill_attempts+=1
	var before: Array=items.duplicate(true)
	var original_ids: Dictionary={}
	for item in before:original_ids[item.id]=true
	var locks_before: Dictionary=branch_locks.duplicate(true)
	branch_ids={}
	for branch in reward_branches:
		for iid in branch.instance_ids:branch_ids[iid]=true
	var data: Array=await graph(items)
	for iid in branch_ids:branch_locks[iid]=data[2][iid].duplicate()
	growth_offset=items.size()-prefix_count
	if await grow_to(config.goals.growth_target):
		growth_target_reached=true
		growth_instance_ids=[]
		for item in items.slice(0,prefix_count):growth_instance_ids.append(item.id)
		for item in items:
			if not original_ids.has(item.id):growth_instance_ids.append(item.id)
		for item in items:
			if not branch_ids.has(item.id):reward_core[item.id]=true
		if await final_accept():return true
	items=before;branch_locks=locks_before;branch_ids={};growth_target_reached=false
	return false

func build() -> bool:
	# Modes and backbone size are chosen before any geometric placement.
	blueprint={"reward_modes":config.topology.reward_modes.duplicate(),"backbone_growth_count":config.topology.backbone_min+rng.randrange(config.topology.backbone_max-config.topology.backbone_min+1),"main_paths_required":config.goals.main_paths_required}
	var prefix: int=blueprint.backbone_growth_count
	phase="motif_catalog"
	motif_catalog=MOTIFS.new(self)
	if not await motif_catalog.build():return false
	structure_stats.motif_count=motif_catalog.count
	for attempt in range(config.search.max_layout_repairs+1):
		if aborted():return false
		repairs=attempt;items=[];reward_branches=[];reward_core={};reward_core_rank={};branch_ids={};branch_locks={};growth_offset=0
		add(make("START",request.start_origin_blocks[0],request.start_origin_blocks[1]))
		if not await grow_to(prefix):record_failure("structure_backbone_growth_exhausted");continue
		if not await skeleton_boss():record_failure("structure_no_boss_attachment");continue
		var has_paths: bool=await topology_ready()
		for _step in range(config.search.close_attempts):
			if has_paths:break
			if await close_one(config.search.close_depth):closed_loops+=1
			has_paths=await topology_ready()
		if not has_paths:record_failure("structure_main_path_domain_empty");continue
		if await STRUCTURE.new(self).solve(prefix):return true
		record_failure("structure_reward_or_infill_exhausted")
	error_status="SEARCH_EXHAUSTED";error_message="structure_plan_exhausted"
	return false

func diagnostics() -> Dictionary:
	var value: Dictionary=super.diagnostics()
	value.structure_plan=blueprint.duplicate(true)
	value.structure_search=structure_stats.duplicate(true)
	value.structure_path=skeleton_path.duplicate()
	value.growth_target_reached=growth_target_reached
	value.growth_instance_ids=growth_instance_ids.duplicate()
	value.algorithm_scope="backbone/loops then hard motif CSP then ordinary infill; full author-Route/static checks, not physics"
	return value
