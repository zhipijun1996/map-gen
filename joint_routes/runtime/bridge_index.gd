extends RefCounted
## Reverse terminal-leg placements from real, capability-filtered directed Routes.
const GEO=preload("geometry.gd")
var rows: Dictionary={}
var s

func _init(solver):s=solver

func build(targets: Array) -> bool:
	var steps: Array=[]
	for mid in s.templates:
		if not s.tids.has(mid) and not s.qids.has(mid):continue
		for mirror in [false,true]:
			var ports: Dictionary=s.local[s.local_key(mid,mirror)]
			var seen: Dictionary={}
			for pin in ports:
				for route in s.transit[s.port_key(mid,mirror,pin)]:
					if route.to_port==pin or s.qids.has(mid) and route.reward_ids.is_empty():continue
					var key: Array=[pin,route.to_port]
					if seen.has(key):continue
					seen[key]=true
					steps.append({"mid":mid,"mirror":mirror,"pin":pin,"exit":route.to_port,"entry":ports[pin],"out":ports[route.to_port],"reward":s.qids.has(mid)})
		if not await s.checkpoint():return false
	var ordered: Array=await s.sort_rows(targets,func(a,b):return s.reward_core_rank.get(a[0].id,-1)>s.reward_core_rank.get(b[0].id,-1))
	for target in ordered.slice(0,s.config.planning.merge_target_limit):
		for step in steps:
			if step.out.surface!=target[2].surface or step.out.face!=GEO.OPPOSITE[target[2].face]:continue
			var origin2: Array=[target[2].world2[0]-step.out.local2[0],target[2].world2[1]-step.out.local2[1]]
			if origin2[0]%2 or origin2[1]%2:continue
			if not await s.tick():return false
			var key: Array=[GEO.OPPOSITE[step.entry.face],step.entry.surface,origin2[0]+step.entry.local2[0],origin2[1]+step.entry.local2[1],step.reward]
			if not rows.has(key):rows[key]=[]
			rows[key].append({"mid":step.mid,"mirror":step.mirror,"pin":step.pin,"exit":step.exit,"x":int(origin2[0]/2),"y":int(origin2[1]/2),"target":target[0].id})
	return true

func matches(front: Dictionary,needs_reward: bool,root_id: String) -> Array:
	var key: Array=[front.face,front.surface,front.world2[0],front.world2[1],needs_reward]
	var result: Array=[]
	for row in rows.get(key,[]):
		if row.target==root_id:continue
		result.append(row)
		if result.size()>=s.config.planning.bridge_matches_per_front:break
	return result
