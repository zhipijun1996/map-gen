extends RefCounted
## Finite real motif domains, MRV and forward checking under original budgets.
const BRANCH=preload("reward_branch_planner.gd")
const JOINT=preload("joint_planner.gd")
var s
var pool: Array=[]
var conflicts: Array=[]
var prefix:=0
func _init(solver):s=solver

func solve(growth_prefix: int) -> bool:
	prefix=growth_prefix
	s.phase="structure_domains"
	var grouped: Array=[]
	var witness=BRANCH.new(s)
	for source in await s.reachable_frontier(s.items):
		if source[0].module_id in ["START","BOSS"]:continue
		var realized: Array=[]
		var seen: Dictionary={}
		for option in await s.motif_catalog.instantiate(source):
			var signature: String=witness.signature(option.chain)
			if seen.has(signature):continue
			seen[signature]=true
			var trial: Array=s.items+option.chain
			if not await s.valid_reward_state(trial):continue
			var proof: Dictionary=await witness.prove(option.chain,source,trial)
			if proof.is_empty() or proof.kind!="multi_return":continue
			option.proof=proof;option.score=witness.chain_score(option.chain)
			realized.append(option)
			if realized.size()>=s.config.search.reward_choice_count:break
		if not realized.is_empty():grouped.append(realized)
		if s.aborted():return false
	# Round robin by actual root, so one crowded interface cannot fill the pool.
	for rank in range(s.config.search.reward_choice_count):
		for group in grouped:
			if rank<group.size() and pool.size()<s.config.topology.domain_limit:pool.append(group[rank])
	if "forward_merge" in s.blueprint.reward_modes:
		var merges: Array=await BRANCH.new(s).options(true)
		merges=merges.filter(func(option):return option.proof.kind=="forward_merge")
		pool=merges+pool
	pool=pool.slice(0,s.config.topology.domain_limit)
	var helper=JOINT.new(s)
	for option in pool:
		option.core_ports={}
		for group in s.GEO.connection_groups(s.items+option.chain):
			for index in [0,1]:
				var a: Array=group[index];var b: Array=group[1-index]
				if s.reward_core.has(a[0].id) and not s.reward_core.has(b[0].id):option.core_ports[a[0].id+"."+a[1]]=true
	for i in range(pool.size()):
		if not await s.checkpoint():return false
		var row: Dictionary={i:true}
		for j in range(i):
			if helper.incompatible(pool[i],pool[j]):row[j]=true;conflicts[j][i]=true
		conflicts.append(row)
	var domains: Array=[]
	for kind in s.blueprint.reward_modes:
		var domain: Array=[]
		for i in range(pool.size()):
			if pool[i].proof.kind==kind:domain.append(i)
		domains.append(domain)
	s.structure_stats.domain_sizes.append(domains.map(func(d):return d.size()))
	return await assign(domains,{})

func assign(domains: Array,chosen: Dictionary) -> bool:
	if s.aborted():return false
	s.phase="reward_branches"
	if chosen.size()==domains.size():return await s.complete_infill(prefix)
	var slot: int=-1
	for i in range(domains.size()):
		if not chosen.has(i) and (slot<0 or domains[i].size()<domains[slot].size()):slot=i
	if domains[slot].is_empty():s.structure_stats.domain_prunes+=1;return false
	var before: Array=s.items.duplicate(true)
	var branches: Array=s.reward_branches.duplicate(true)
	var core: Dictionary=s.reward_core.duplicate(true)
	for index in domains[slot]:
		s.terminal_states+=1;s.structure_stats.assignments+=1
		if s.terminal_states>s.config.search.max_terminal_states:
			s.error_status="BUDGET_EXHAUSTED";s.error_message="terminal_state_budget";return false
		var next: Array=domains.duplicate(true)
		var possible:=true
		for other in range(domains.size()):
			if chosen.has(other) or other==slot:continue
			next[other]=domains[other].filter(func(value):return not conflicts[index].has(value))
			# Identical slots are unordered: visit each assignment set once.
			if s.blueprint.reward_modes[other]==s.blueprint.reward_modes[slot] and other>slot:next[other]=next[other].filter(func(value):return value>index)
			if next[other].is_empty():possible=false;break
		if not possible:s.structure_stats.domain_prunes+=1;continue
		s.items=before.duplicate(true);s.reward_branches=branches.duplicate(true);s.reward_core=core.duplicate(true)
		var chain: Array=[]
		for original in pool[index].chain:
			var item: Dictionary=original.duplicate(true);s.add(item);chain.append(item)
		if not await s.valid_reward_state(s.items):continue
		var proof: Dictionary=await BRANCH.new(s).prove(chain,pool[index].root,s.items)
		if proof.is_empty() or proof.kind!=s.blueprint.reward_modes[slot]:continue
		s.reward_branches.append(proof);chosen[slot]=index
		if await assign(next,chosen):return true
		chosen.erase(slot)
		if s.aborted():return false
	s.items=before;s.reward_branches=branches;s.reward_core=core
	return false
