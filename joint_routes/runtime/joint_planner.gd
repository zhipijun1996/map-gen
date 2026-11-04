extends RefCounted
## Joint selection of actual route witnesses, not counts of single-room slots.
const GEO=preload("geometry.gd")
const BRANCH=preload("reward_branch_planner.gd")
var s
var pool: Array=[]
var conflicts: Array=[]

func _init(solver):s=solver

func incompatible(a: Dictionary,b: Dictionary) -> bool:
	for key in a.core_ports:
		if b.core_ports.has(key):return true
	for x in a.chain:
		for y in b.chain:
			if GEO.overlap(x,y):return true
			for p in x.ports.values():
				for q in y.ports.values():
					if GEO.matching(p,q):return true
	return false

func solve() -> bool:
	s.phase="reward_branches"
	pool=await BRANCH.new(s).options(true)
	s.joint_stats.pools+=1
	s.joint_stats.pool_candidates+=pool.size()
	for option in pool:
		option.core_ports={}
		for group in GEO.connection_groups(s.items+option.chain):
			for row in group:
				if s.reward_core.has(row[0].id):option.core_ports[row[0].id+"."+row[1]]=true
		# Only core-to-branch endpoints belong to the reservation. Existing
		# core-to-core connections are common and must not conflict every plan.
		option.core_ports={}
		for group in GEO.connection_groups(s.items+option.chain):
			var a: Array=group[0];var b: Array=group[1]
			if s.reward_core.has(a[0].id) and not s.reward_core.has(b[0].id):option.core_ports[a[0].id+"."+a[1]]=true
			if s.reward_core.has(b[0].id) and not s.reward_core.has(a[0].id):option.core_ports[b[0].id+"."+b[1]]=true
	for i in range(pool.size()):
		if not await s.checkpoint():return false
		var row: Dictionary={i:true}
		for j in range(i):
			if incompatible(pool[i],pool[j]):
				row[j]=true;conflicts[j][i]=true;s.joint_stats.pair_conflicts+=1
		conflicts.append(row)
	var available: Array=range(pool.size())
	var success: bool=await search(available,0)
	if not success and not s.aborted():s.record_failure("joint_reward_plan_exhausted")
	return success

func score(option: Dictionary) -> float:
	var value: float=option.score
	for item in option.chain:
		var mid: String=s.templates[item.module_id].source_module_id
		for placed in s.items:
			if not s.reward_core.has(placed.id) and s.templates[placed.module_id].source_module_id==mid:
				value-=s.config.diversity.reward_repeat_penalty if item.reward else s.config.diversity.connector_repeat_penalty
	return value

func search(available: Array,count: int) -> bool:
	if s.aborted():return false
	if count==s.config.goals.reward_target:return await s.final_accept()
	if available.size()<s.config.goals.reward_target-count:
		s.joint_stats.capacity_prunes+=1;return false
	var ordered: Array=await s.sort_rows(available,func(a,b):return score(pool[a])>score(pool[b]))
	var before: Array=s.items.duplicate(true)
	var branches: Array=s.reward_branches.duplicate(true)
	for index in ordered:
		var next: Array=[]
		for other in available:
			if other>index and not conflicts[index].has(other):next.append(other)
		if next.size()<s.config.goals.reward_target-count-1:continue
		s.terminal_states+=1;s.joint_stats.search_nodes+=1
		if s.terminal_states>s.config.search.max_terminal_states:
			s.error_status="BUDGET_EXHAUSTED";s.error_message="terminal_state_budget";return false
		var share: int=maxi(s.config.goals.reward_target,s.config.search.max_terminal_states/(s.config.search.max_layout_repairs+1))
		if s.terminal_states-s.layout_terminal_start>share:
			s.record_failure("terminal_slice_exhausted");s.terminal_slice_failed=true;s.last_search_failure="terminal_slice_exhausted";return false
		s.items=before.duplicate(true);s.reward_branches=branches.duplicate(true)
		var chain: Array=[]
		for original in pool[index].chain:
			var item: Dictionary=original.duplicate(true)
			s.add(item);chain.append(item)
		if not await s.valid_reward_state(s.items):continue
		var proof: Dictionary=await BRANCH.new(s).prove(chain,pool[index].root,s.items)
		if proof.is_empty():continue
		s.reward_branches.append(proof)
		if await search(next,count+1):return true
		if s.aborted() or s.terminal_slice_failed:return false
	s.items=before;s.reward_branches=branches
	return false
