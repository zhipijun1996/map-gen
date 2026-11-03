extends RefCounted
const GEO = preload("geometry.gd")
const NUM = preload("numeric.gd")
const RNG = preload("python_rng.gd")
const CURSOR = preload("candidate_cursor.gd")
const PIPELINE = preload("final_pipeline.gd")
var owner: WeakRef
var library
var request: Dictionary
var config: Dictionary
var templates: Dictionary
var rng = RNG.new()
var items: Array = []
var expanded := 0
var backtracks := 0
var repairs := 0
var terminal_states := 0
var closed_loops := 0
var phase := "init"
var error_status := ""
var error_message := ""
var rejections: Dictionary = {}
var failures: Array = []
var decisions: Array = []
var frames: Array = []
var local: Dictionary = {}
var index: Dictionary = {}
var routes: Dictionary = {}
var transit: Dictionary = {}
var config_cache: Dictionary = {}
var graph_cache: Dictionary = {}
var reach_cache: Dictionary = {}
var return_rooms: Dictionary = {}
var tids: Dictionary = {}
var qids: Dictionary = {}
var roles: Dictionary = {"BOSS": true}
var started_usec := 0
var layout_terminal_start := 0
var air_connected := false
var terminal_slice_failed := false
var last_search_failure := ""
var final_source: Dictionary = {}

func _init(job, req: Dictionary, prepared, cfg: Dictionary):
	owner = weakref(job)
	library = prepared
	request = req
	config = cfg
	templates = prepared.templates
	rng.seed_integer(req.seed)
	started_usec = Time.get_ticks_usec()

func initialize() -> bool:
	for mid in templates:
		if not await checkpoint():
			return false
		var template: Dictionary = templates[mid]
		if mid.begins_with("T"):
			tids[mid] = true
		if mid.begins_with("Q"):
			qids[mid] = true
			roles[mid] = true
			for route in template.routes:
				if template.ports.size() == 1 and route.from_port == route.to_port and not route.reward_ids.is_empty():
					return_rooms[mid] = true
		for mirror in [false, true]:
			var key := local_key(mid, mirror)
			var ports := GEO.placed_ports(template, 0, 0, mirror)
			local[key] = ports
			for pid in ports:
				var port: Dictionary = ports[pid]
				var ikey: String = port.face + "/" + port.surface
				if not index.has(ikey):
					index[ikey] = []
				index[ikey].append([mid, mirror, pid, port])
			var rs: Array = []
			for route in template.routes:
				if has_abilities(route.required_abilities) and GEO.permitted(ports[route.from_port], "in") and GEO.permitted(ports[route.to_port], "out"):
					rs.append(route)
			routes[key] = rs
			for pid in ports:
				transit[port_key(mid, mirror, pid)] = rs.filter(func(r): return r.from_port == pid and not r.validation.get("testNeighborFixtures", []))

	return not aborted()

static func local_key(mid: String, mirror: bool) -> String:
	return mid + ("|1" if mirror else "|0")

static func port_key(mid: String, mirror: bool, pid: String) -> String:
	return local_key(mid, mirror) + "|" + pid

func has_abilities(required: Array) -> bool:
	for ability in required:
		if not library.abilities.has(ability):
			return false
	return true

func aborted() -> bool:
	return not error_status.is_empty()

func reject(reason: String) -> void:
	rejections[reason] = rejections.get(reason, 0)+1

func checkpoint() -> bool:
	var job = owner.get_ref()
	if job == null or not await job.consume():
		error_status = "CANCELLED"
		error_message = "cancelled"
		return false
	return true

func sort_rows(rows: Array, less: Callable) -> Array:
	# Bottom-up stable merge, same equal-key order; no RNG calls.
	var result := rows.duplicate()
	var width := 1
	while width < result.size():
		var merged: Array = []
		for start in range(0,result.size(),width*2):
			var i := start
			var j := mini(start+width,result.size())
			var end := mini(start+2*width,result.size())
			var left_end := j
			while i < left_end or j < end:
				if not await checkpoint():
					return []
				if i >= left_end or j < end and less.call(result[j],result[i]):
					merged.append(result[j])
					j += 1
				else:
					merged.append(result[i])
					i += 1
		result = merged
		width *= 2
	return result

func tick() -> bool:
	if not await checkpoint():
		return false
	expanded += 1
	if expanded > config.search.candidate_expansion_budget:
		error_status = "BUDGET_EXHAUSTED"
		error_message = "candidate_expansion_budget"
		return false
	if expanded%config.search.budget_check_interval == 0 and config.search.per_seed_timeout_seconds != null and float(Time.get_ticks_usec()-started_usec)/1000000.0 > config.search.per_seed_timeout_seconds:
		error_status = "BUDGET_EXHAUSTED"
		error_message = "wall_clock_budget"
		return false
	return true

func make(mid: String, x: int, y: int, mirror := false, iid = null) -> Dictionary:
	var template: Dictionary = templates[mid]
	return {"id": iid, "module_id": mid, "name": template.name, "origin": [x, y], "size_blocks": template.size_blocks, "mirror_x": mirror, "ports": GEO.placed_ports(template, x, y, mirror), "reward": template.reward}

func add(item: Dictionary) -> void:
	item.id = "M%02d" % (items.size()+1)
	items.append(item)

func candidates(source: Array, mids: Dictionary, occupied: Array):
	return CURSOR.new(self, source, mids, occupied)

func configuration_ok(item: Dictionary, connected: Dictionary) -> bool:
	var ids: Array = connected.keys()
	ids.sort()
	var key := local_key(item.module_id, item.mirror_x) + JSON.stringify(ids)
	if config_cache.has(key):
		return config_cache[key]
	if not await checkpoint():
		return false
	var template: Dictionary = templates[item.module_id]
	var full := GEO.placed_ports(template, 0, 0, item.mirror_x, true)
	var seals: Array = []
	for pid in full:
		if not connected.has(pid):
			seals.append(library.gear_seal(full[pid], template.size_blocks))
	for route in template.all_routes:
		if not connected.has(route.from_port) or not connected.has(route.to_port) or not has_abilities(route.required_abilities):
			continue
		if route.validation.get("testNeighborFixtures", []) or not GEO.permitted(full[route.from_port], "in") or not GEO.permitted(full[route.to_port], "out") or route.path_points.size() < 2:
			config_cache[key] = false
			return false
		var points: Array = route.path_points
		if item.mirror_x:
			points = []
			for p in route.path_points:
				points.append([template.size_blocks[0]*library.block_pixels-p[0], p[1]])
		for seal in seals:
			var rect: Array = library.clearance_rect(seal.rect_pixels)
			for i in range(points.size()-1):
				if GEO.segment_hits_rect(points[i], points[i+1], rect):
					config_cache[key] = false
					return false
	config_cache[key] = true
	return true

static func edge(graph: Dictionary, a: String, b: String) -> void:
	if not graph.has(a):
		graph[a] = []
	graph[a].append(b)

func graph(occupied: Array, potential := false) -> Array:
	var state: Array = ["potential" if potential else "actual"]
	for item in occupied:
		state.append([item.id,item.module_id,item.mirror_x,item.origin])
	var cache_key := JSON.stringify(state)
	if graph_cache.has(cache_key):
		await checkpoint()
		return graph_cache[cache_key]
	var g: Dictionary = {}
	var connected: Dictionary = {}
	var rewards: Array = []
	for item in occupied:
		connected[item.id] = {}
	for group in GEO.connection_groups(occupied):
		if not await checkpoint():
			return [{},[],connected]
		var a: Array = group[0]
		var b: Array = group[1]
		connected[a[0].id][a[1]] = true
		connected[b[0].id][b[1]] = true
		if GEO.permitted(a[2], "out") and GEO.permitted(b[2], "in"):
			edge(g, a[0].id+"."+a[1]+":depart", b[0].id+"."+b[1]+":arrive")
		if GEO.permitted(b[2], "out") and GEO.permitted(a[2], "in"):
			edge(g, b[0].id+"."+b[1]+":depart", a[0].id+"."+a[1]+":arrive")
	for item in occupied:
		if not await checkpoint():
			return [{},[],connected]
		for route in routes[local_key(item.module_id, item.mirror_x)]:
			var a: String = route.from_port
			var b: String = route.to_port
			var selected: Dictionary = connected[item.id]
			if not potential and (not selected.has(a) or not selected.has(b)):
				continue
			var trial := selected.duplicate()
			trial[a] = true
			trial[b] = true
			if potential and not (await configuration_ok(item, trial)):
				continue
			var chain: Array = [item.id+"."+a+":arrive"]
			if item.reward and not route.reward_ids.is_empty():
				var node: String = item.id+":reward:"+route.id
				chain.append(node)
				rewards.append([item.id, node])
			chain.append(item.id+"."+b+":depart")
			for i in range(chain.size()-1):
				edge(g, chain[i], chain[i+1])
	# StableSolver expands incidental treasure edges in a second pass.
	for item in occupied:
		if item.reward:
			continue
		for route in routes[local_key(item.module_id, item.mirror_x)]:
			if route.reward_ids.is_empty():
				continue
			var a: String = item.id+"."+route.from_port+":arrive"
			var b: String = item.id+"."+route.to_port+":depart"
			if not b in g.get(a, []):
				continue
			g[a].erase(b)
			var chain: Array = [a]
			for rid in route.reward_ids:
				chain.append(item.id+":reward:"+route.id+":"+rid)
			chain.append(b)
			for i in range(chain.size()-1):
				edge(g, chain[i], chain[i+1])
	edge(g, "START", "M01.R:depart")
	for item in occupied:
		if item.module_id == "BOSS":
			edge(g, item.id+".L:arrive", "BOSS")
			break
	var value: Array = [g,rewards,connected]
	if graph_cache.size() >= 64:
		graph_cache.erase(graph_cache.keys()[0])
	graph_cache[cache_key] = value
	return value

func reachable(g: Dictionary, start: String) -> Dictionary:
	var key := hash(g)
	if reach_cache.has(key) and reach_cache[key].graph == g and reach_cache[key].starts.has(start):
		await checkpoint()
		return reach_cache[key].starts[start]
	var seen: Dictionary = {start: true}
	var queue: Array = [start]
	var head := 0
	while head < queue.size():
		if not await checkpoint():
			return {}
		var at: String = queue[head]
		head += 1
		for node in g.get(at, []):
			if not seen.has(node):
				seen[node] = true
				queue.append(node)
	if not reach_cache.has(key) or reach_cache[key].graph != g:
		if reach_cache.size() >= 64:
			reach_cache.erase(reach_cache.keys()[0])
		reach_cache[key] = {"graph":g,"starts":{}}
	reach_cache[key].starts[start] = seen
	return seen

func reachable_frontier(occupied: Array) -> Array:
	var seen := (await reachable((await graph(occupied, true))[0], "START"))
	return GEO.frontier(occupied).filter(func(s): return seen.has(s[0].id+"."+s[1]+":depart") and GEO.permitted(s[2], "out"))

func safe_state(occupied: Array) -> bool:
	var connected: Dictionary = (await graph(occupied))[2]
	for item in occupied:
		if not (await configuration_ok(item, connected[item.id])):
			return false
	return true

func record_failure(reason: String) -> void:
	failures.append({"reason": reason, "phase": phase, "expanded": expanded, "backtracks": backtracks, "repairs": repairs, "instances": items.duplicate(true)})

func rewind() -> bool:
	for _depth in range(config.search.max_rewind_depth):
		if frames.is_empty() or backtracks >= config.search.max_growth_backtracks:
			return false
		var frame: Dictionary = frames[-1]
		items = frame.before.duplicate(true)
		backtracks += 1
		if not frame.choices.is_empty():
			var choice: Dictionary = frame.choices.pop_front()
			rng.setstate(frame.rng)
			add(choice.duplicate(true))
			return true
		frames.pop_back()
	return false

func grow() -> bool:
	phase = "growth"
	if items.is_empty():
		add(make("START", request.start_origin_blocks[0], request.start_origin_blocks[1]))
	while items.size() < config.goals.growth_target and not aborted():
		var choices: Array = await growth_options()
		if aborted():
			return false
		if choices.is_empty():
			record_failure("growth_exhausted")
			if rewind():
				continue
			error_status = "SEARCH_EXHAUSTED"
			error_message = "growth_exhausted"
			return false
		var first: Dictionary = choices.pop_front()
		frames.append({"before": items.duplicate(true), "choices": choices, "rng": rng.getstate()})
		decisions.append({"instance": "M%02d" % (items.size()+1), "module_id": first.module_id, "origin": first.origin.duplicate(), "mirror_x": first.mirror_x})
		add(first.duplicate(true))
	return not aborted()

func matched(port: Dictionary, lookup: Dictionary) -> bool:
	for other in lookup.get(GEO.coordinate_key(port.world2), []):
		if GEO.matching(port, other):
			return true
	return false

func exit_features(item: Dictionary, pin: String, occupied: Array, lookup: Dictionary) -> Array:
	var useful := 0
	var reverse := 0
	var slots := 0
	var vertical := 0
	var directions: Dictionary = {}
	var connected: Dictionary = {}
	for pid in item.ports:
		if matched(item.ports[pid], lookup):
			connected[pid] = true
	var exits: Dictionary = {}
	for route in transit[port_key(item.module_id, item.mirror_x, pin)]:
		if route.to_port != pin:
			exits[route.to_port] = true
	var ids: Array = exits.keys()
	ids.sort()
	for pid in ids:
		var selected := connected.duplicate()
		selected[pin] = true
		selected[pid] = true
		if connected.has(pid) or not (await configuration_ok(item, selected)):
			continue
		var source: Array = [item, pid, item.ports[pid]]
		var trial: Array = occupied+[item]
		if await candidates(source, tids, trial).next() != null:
			useful += 1
			directions[source[2].face] = true
			if source[2].face in ["TOP", "BOTTOM"]:
				vertical += 1
		if aborted():
			return []
		for route in transit[port_key(item.module_id, item.mirror_x, pid)]:
			if route.to_port == pin:
				reverse += 1
				break
		if await candidates(source, roles, trial).next() != null:
			slots += 1
		if aborted():
			return []
	return [useful, reverse, slots, vertical, directions.size()]

func reservation(occupied: Array, limit: int, require_boss := false) -> Array:
	if limit <= 0:
		return []
	var data := (await graph(occupied, true))
	var g: Dictionary = data[0]
	var connected: Dictionary = data[2]
	var seen := (await reachable(g, "START"))
	var proposed: Array = []
	var extra: Dictionary = {}
	var counts: Dictionary = {}
	for source in GEO.frontier(occupied):
		var item: Dictionary = source[0]
		var pid: String = source[1]
		if item.reward or item.module_id in ["START", "BOSS"] or not seen.has(item.id+"."+pid+":depart") or not GEO.permitted(source[2], "in"):
			continue
		var onward := (await reachable(g, item.id+"."+pid+":arrive"))
		if require_boss and not onward.has("BOSS"):
			continue
		if not require_boss:
			var can_return := false
			for other in connected[item.id]:
				if onward.has(item.id+"."+other+":depart"):
					can_return = true
			if not can_return:
				continue
		var selected: Dictionary = connected[item.id].duplicate()
		selected.merge(extra.get(item.id, {}))
		selected[pid] = true
		if not (await configuration_ok(item, selected)):
			continue
		var options: Array = []
		var cursor = candidates(source, return_rooms, occupied+proposed)
		var row = await cursor.next()
		while row != null:
			options.append(row)
			row = await cursor.next()
		if aborted():
			return []
		options = (await sort_rows(options, func(a, b):
			var aa = config.scoring.reservation_repeat*counts.get(a[0].module_id, 0)+config.scoring.reservation_area*(a[0].size_blocks[0]*a[0].size_blocks[1])
			var bb = config.scoring.reservation_repeat*counts.get(b[0].module_id, 0)+config.scoring.reservation_area*(b[0].size_blocks[0]*b[0].size_blocks[1])
			if aa != bb: return aa < bb
			if a[0].module_id != b[0].module_id: return a[0].module_id < b[0].module_id
			if a[0].mirror_x != b[0].mirror_x: return not a[0].mirror_x
			return a[0].origin[0] < b[0].origin[0] if a[0].origin[0] != b[0].origin[0] else a[0].origin[1] < b[0].origin[1]))
		if options.is_empty():
			continue
		var candidate: Dictionary = options[0][0].duplicate(true)
		candidate.id = "plan-%d" % proposed.size()
		proposed.append(candidate)
		if not extra.has(item.id):
			extra[item.id] = {}
		extra[item.id][pid] = true
		counts[candidate.module_id] = counts.get(candidate.module_id, 0)+1
		if proposed.size() >= limit:
			return proposed
	return proposed

func growth_options() -> Array:
	var fronts := (await reachable_frontier(items))
	rng.shuffle(fronts)
	fronts = fronts.slice(0, config.search.growth_frontier_limit)
	var old := GEO.bounds(items)
	var old_cost := NUM.shape_cost(old, config)
	var score: Dictionary = config.scoring
	var lookup: Dictionary = {}
	for row in GEO.frontier(items):
		var key := GEO.coordinate_key(row[2].world2)
		if not lookup.has(key):
			lookup[key] = []
		lookup[key].append(row[2])
	var used: Dictionary = {}
	for item in items:
		used[item.module_id] = used.get(item.module_id, 0)+1
	var options: Array = []
	var seen: Dictionary = {}
	for source in fronts:
		var cursor = candidates(source, tids, items)
		var row = await cursor.next()
		while row != null:
			var item: Dictionary = row[0]
			var pin: String = row[1]
			var key := local_key(item.module_id, item.mirror_x)+GEO.coordinate_key(item.origin)+"/"+pin
			if not seen.has(key):
				seen[key] = true
				var auto := 0
				for port in item.ports.values():
					if matched(port, lookup):
						auto += 1
				var x: int = item.origin[0]
				var y: int = item.origin[1]
				var b: Array = [mini(old[0], x), mini(old[1], y), maxi(old[2], x+item.size_blocks[0]), maxi(old[3], y+item.size_blocks[1])]
				var perimeter: int = (b[2]-b[0]+b[3]-b[1])-(old[2]-old[0]+old[3]-old[1])
				var base = score.auto_connection*(auto-1)-score.perimeter*perimeter-(NUM.shape_cost(b, config)-old_cost)-score.repeat_module*used.get(item.module_id, 0)-score.left_bias*maxi(0, -x)-score.height_bias*absi(y)+rng.uniform(-score.growth_noise, score.growth_noise)
				var free: Dictionary = {}
				for route in transit[port_key(item.module_id, item.mirror_x, pin)]:
					if route.to_port != pin and not matched(item.ports[route.to_port], lookup):
						free[route.to_port] = true
				var ranking = base+score.usable_exit*(free.size()-1)
				var vertical := 0
				for pid in free:
					if item.ports[pid].face in ["TOP", "BOTTOM"]:
						vertical += 1
				ranking += score.vertical_exit*vertical
				options.append([ranking, base, item, pin])
			row = await cursor.next()
		if aborted():
			return []
	options = (await sort_rows(options, func(a, b): return a[0] > b[0]))
	var ranked: Array = []
	for row in options.slice(0, config.search.growth_shortlist):
		var item: Dictionary = row[2].duplicate(true)
		item.id = "M%02d" % (items.size()+1)
		if not (await safe_state(items+[item])):
			reject("seal_or_route_configuration")
			continue
		var features: Array = await exit_features(item, row[3], items, lookup)
		if aborted():
			return []
		var ranking = row[1]+score.usable_exit*(features[0]-1)+score.bidirectional_exit*features[1]+score.terminal_slot*features[2]
		if not features[0]:
			ranking += score.dead_end
		ranking += score.vertical_exit*features[3]+score.distinct_direction*features[4]
		ranked.append([ranking, item])
	ranked = (await sort_rows(ranked, func(a, b): return a[0] > b[0]))
	var unique: Array = []
	var physical: Dictionary = {}
	for row in ranked:
		var key := local_key(row[1].module_id, row[1].mirror_x)+GEO.coordinate_key(row[1].origin)
		if not physical.has(key):
			physical[key] = true
			unique.append(row)
	unique = unique.slice(0, config.search.growth_choice_count)
	if items.size() >= config.search.reserve_from_growth_count:
		var old_capacity: int = (await reservation(items, config.goals.reward_target)).size()
		var scored: Array = []
		for row in unique:
			var capacity: int = (await reservation(items+[row[1]], config.goals.reward_target)).size()
			scored.append([row[0]+score.reward_reserve*(capacity-old_capacity), row[1]])
			if aborted():
				return []
		unique = (await sort_rows(scored, func(a, b): return a[0] > b[0]))
	var choices: Array = []
	for row in unique:
		choices.append(row[1])
	if not choices.is_empty():
		var pick: int = rng.randrange(choices.size())
		choices = [choices[pick]]+choices.slice(0, pick)+choices.slice(pick+1)
	return choices

func close_one(max_depth: int) -> bool:
	phase = "closure_search"
	var fronts := (await reachable_frontier(items))
	rng.shuffle(fronts)
	var viable: Array = fronts.filter(func(s): return not s[0].reward and s[0].module_id != "START")
	var g: Dictionary = (await graph(items, true))[0]
	for source in viable.slice(0, config.search.closure_source_limit):
		var targets: Array = []
		for target in GEO.frontier(items):
			if target[0].id == source[0].id or not GEO.permitted(target[2], "in"):
				continue
			if distance2(target[2], source[2]) >= config.search.closure_target_distance2:
				continue
			if (await reachable(g, target[0].id+"."+target[1]+":arrive")).has(source[0].id+"."+source[1]+":depart"):
				targets.append(target)
		if targets.is_empty():
			continue
		var beam: Array = [[[], source]]
		for depth in range(max_depth):
			var states: Array = []
			for state in beam:
				var chain: Array = state[0]
				var cursor = candidates(state[1], tids, items+chain)
				var row = await cursor.next()
				while row != null:
					var item: Dictionary = row[0]
					var pin: String = row[1]
					item.id = "tmp%d" % depth
					var exits: Dictionary = {}
					for route in transit[port_key(item.module_id, item.mirror_x, pin)]:
						if route.to_port != pin:
							exits[route.to_port] = true
					var ids: Array = exits.keys()
					ids.sort()
					for pid in ids:
						var port: Dictionary = item.ports[pid]
						if not (await configuration_ok(item, {pin: true, pid: true})):
							continue
						var closes := false
						for target in targets:
							if GEO.matching(port, target[2]) and GEO.permitted(target[2], "in"):
								closes = true
								break
						if closes:
							var trial := items.duplicate(true)
							for original in chain+[item]:
								var copy: Dictionary = original.duplicate(true)
								copy.id = "M%02d" % (trial.size()+1)
								trial.append(copy)
							if (await safe_state(trial)):
								items = trial
								return true
						var dist := 9223372036854775807
						for target in targets:
							dist = mini(dist, distance2(port, target[2]))
						if dist < config.search.closure_distance_limit2:
							states.append([dist+rng.random()*config.scoring.closure_noise, chain+[item], [item, pid, port]])
					row = await cursor.next()
				if aborted():
					return false
			states = (await sort_rows(states, func(a, b): return a[0] < b[0]))
			beam = []
			for state in states.slice(0, config.search.closure_beam_width):
				beam.append([state[1], state[2]])
			if beam.is_empty():
				break
	return false

static func distance2(a: Dictionary, b: Dictionary) -> int:
	return absi(a.world2[0]-b.world2[0])+absi(a.world2[1]-b.world2[1])

func add_air_loop() -> bool:
	var basefront := GEO.frontier(items)
	rng.shuffle(basefront) # Also consumed for the default empty AIR leg sets.
	for source in basefront:
		if source[2].surface != "ROCK" or not GEO.permitted(source[2], "out"):
			continue
		var acursor = candidates(source, library.air_entries, items)
		var arow = await acursor.next()
		while arow != null:
			var a: Dictionary = arow[0]
			a.id = "airtmpA"
			var air: Array = []
			for pid in a.ports:
				if a.ports[pid].surface == "AIR":
					air = [a, pid, a.ports[pid]]
					break
			var bcursor = candidates(air, library.air_returns, items+[a])
			var brow = await bcursor.next()
			while brow != null:
				var b: Dictionary = brow[0]
				b.id = "airtmpB"
				var out: Array = []
				for pid in b.ports:
					if b.ports[pid].surface == "ROCK":
						out = [b, pid, b.ports[pid]]
						break
				var targets := basefront.filter(func(t): return t[0].id != source[0].id)
				var ccursor = candidates(out, tids, items+[a,b])
				var crow = await ccursor.next()
				while crow != null:
					var c: Dictionary = crow[0]
					for pid in c.ports:
						if pid == crow[1]:
							continue
						for target in targets:
							if GEO.matching(c.ports[pid], target[2]):
								add(a)
								add(b)
								add(c)
								return true
					crow = await ccursor.next()
				brow = await bcursor.next()
			arow = await acursor.next()
	return false

func valid_reward_state(occupied: Array) -> bool:
	if not (await safe_state(occupied)):
		return false
	var data := (await graph(occupied))
	var seen := (await reachable(data[0], "START"))
	if not seen.has("BOSS"):
		return false
	for item in occupied:
		if not item.reward:
			continue
		var nodes: Array = data[1].filter(func(r): return r[0] == item.id and seen.has(r[1]))
		if nodes.is_empty():
			return false
		for node in nodes:
			if not (await reachable(data[0], node[1])).has("BOSS"):
				return false
	return true

static func graph_edges(g: Dictionary) -> Array:
	var result: Array = []
	var keys: Array = g.keys()
	keys.sort()
	for key in keys:
		for node in g[key]:
			result.append([key, node])
	return result

func actual_paths(edges: Array, count: int) -> Array:
	var g: Dictionary = {}
	for pair in edges:
		edge(g, pair[0], pair[1])
	var paths: Array = []
	var sequences: Dictionary = {}
	var skips: Array = [{}]
	while not skips.is_empty() and paths.size() < count:
		if not await checkpoint():
			return []
		var skip: Dictionary = skips.pop_front()
		var previous: Dictionary = {"START": null}
		var queue: Array = ["START"]
		var head := 0
		while head < queue.size():
			if not await checkpoint():
				return []
			var at: String = queue[head]
			head += 1
			for node in g.get(at, []):
				if not skip.has(at+"\n"+node) and not previous.has(node):
					previous[node] = at
					queue.append(node)
		if not previous.has("BOSS"):
			continue
		var path: Array = []
		var at = "BOSS"
		while at != null:
			path.append(at)
			at = previous[at]
		path.reverse()
		var sequence: Dictionary = {}
		for node in path:
			sequence[node.split(".")[0].split(":")[0]] = true
		var key := JSON.stringify(sequence.keys())
		if sequences.has(key):
			continue
		sequences[key] = true
		paths.append(path)
		for i in range(path.size()-1):
			if path[i].ends_with(":depart") and path[i+1].ends_with(":arrive") and not path[i].begins_with("M01."):
				var next_skip := skip.duplicate()
				next_skip[path[i]+"\n"+path[i+1]] = true
				skips.append(next_skip)
	return paths

static func aspect(occupied: Array) -> float:
	var bounds := GEO.bounds(occupied)
	var width: int = bounds[2]-bounds[0]
	var height: int = bounds[3]-bounds[1]
	return maxf(float(width)/height, float(height)/width)

func reward_options() -> Array:
	var placed := 0
	for item in items:
		if item.reward:
			placed += 1
	var remaining: int = config.goals.reward_target-placed-1
	var seen: Dictionary = {}
	var options: Array = []
	for source in (await reachable_frontier(items)):
		if source[0].reward or source[0].module_id in ["START", "BOSS"]:
			continue
		var cursor = candidates(source, qids, items)
		var row = await cursor.next()
		while row != null:
			var item: Dictionary = row[0]
			var key := local_key(item.module_id, item.mirror_x)+GEO.coordinate_key(item.origin)
			if not seen.has(key):
				seen[key] = true
				item.id = "M%02d" % (items.size()+1)
				var trial: Array = items+[item]
				if (await valid_reward_state(trial)):
					if (await reservation(trial, remaining, true)).size() < remaining:
						reject("insufficient_remaining_reward_reservation")
					else:
						var near := 0
						for other in items:
							if other.reward and origin_distance(item.origin, other.origin) < config.scoring.reward_near_radius:
								near += 1
						options.append([rng.random()*config.scoring.reward_noise-near*config.scoring.reward_near_penalty, item])
			row = await cursor.next()
		if aborted():
			return []
	options = (await sort_rows(options, func(a, b): return a[0] > b[0]))
	var result: Array = []
	for row in options.slice(0, config.search.reward_choice_count):
		result.append(row[1])
	return result

func origin_distance(a: Array, b: Array = [0, 0]) -> float:
	var result := NUM.integer_hypot(a[0]-b[0],a[1]-b[1])
	if not is_finite(result):
		error_status = "INVALID_INPUT"
		error_message = "coordinate distance exceeds candidate +/-2000000000 integer domain"
		return 0.0
	return result

func place_rewards(n: int) -> bool:
	if n == config.goals.reward_target:
		if aspect(items) > config.shape.max_aspect:
			record_failure("final_shape_envelope")
			return false
		# The final independent assembly/audit/export gate is supplied separately.
		return await final_accept()
	var choices: Array = await reward_options()
	if aborted():
		return false
	if choices.is_empty():
		record_failure("reward_exhausted")
		return false
	var before := items.duplicate(true)
	var state: Array = rng.getstate()
	for choice in choices:
		terminal_states += 1
		if terminal_states > config.search.max_terminal_states:
			error_status = "BUDGET_EXHAUSTED"
			error_message = "terminal_state_budget"
			return false
		var share: int = maxi(config.goals.reward_target, config.search.max_terminal_states/(config.search.max_layout_repairs+1))
		if terminal_states-layout_terminal_start > share:
			record_failure("terminal_slice_exhausted")
			terminal_slice_failed = true
			last_search_failure = "terminal_slice_exhausted"
			return false
		items = before.duplicate(true)
		rng.setstate(state)
		add(choice.duplicate(true))
		if await place_rewards(n+1):
			return true
		if aborted() or terminal_slice_failed:
			return false
	items = before
	return false

func finish() -> bool:
	phase = "goal_aware_terminals"
	layout_terminal_start = terminal_states
	terminal_slice_failed = false
	var options: Array = []
	for source in (await reachable_frontier(items)):
		if source[0].module_id == "START":
			continue
		var cursor = candidates(source, {"BOSS": true}, items)
		var row = await cursor.next()
		while row != null:
			var item: Dictionary = row[0]
			item.id = "M%02d" % (items.size()+1)
			var trial: Array = items+[item]
			if (await valid_reward_state(trial)) and aspect(trial) <= config.shape.max_aspect:
				if (await actual_paths(graph_edges((await graph(trial))[0]), config.goals.main_paths_required)).size() < config.goals.main_paths_required:
					reject("boss_main_path_diversity")
				elif (await reservation(trial, config.goals.reward_target, true)).size() < config.goals.reward_target:
					reject("boss_reward_space_reservation")
				else:
					options.append([config.scoring.boss_distance*origin_distance(item.origin), item])
			row = await cursor.next()
		if aborted():
			return false
	options = (await sort_rows(options, func(a, b): return a[0] > b[0]))
	if options.is_empty():
		record_failure("no_goal_and_reservation_compatible_boss")
		last_search_failure = "no_goal_and_reservation_compatible_boss"
		return false
	var before := items.duplicate(true)
	var state: Array = rng.getstate()
	for row in options.slice(0, config.search.boss_choice_count):
		items = before.duplicate(true)
		rng.setstate(state)
		add(row[1].duplicate(true))
		if await place_rewards(0):
			return true
		if aborted() or terminal_slice_failed:
			return false
	last_search_failure = "goal_aware_reward_search_exhausted"
	return false

func final_accept() -> bool:
	if not await checkpoint():
		return false
	owner.get_ref().work_phase = "final_gate"
	if not await PIPELINE.assembly_gate(self):
		record_failure("original_assembly_rejected")
		return false
	var decorated := items.duplicate(true)
	owner.get_ref().work_phase = "final_decorate"
	var feedback: Array = await PIPELINE.decorate(decorated, self)
	if aborted():
		return false
	owner.get_ref().work_phase = "final_audit"
	var checked: Dictionary = await PIPELINE.audit(decorated, self)
	if aborted():
		return false
	var paths := (await actual_paths(checked.edges, config.goals.main_paths_required))
	if not feedback[1].is_empty() or not checked.blockers.is_empty() or paths.size() < config.goals.main_paths_required:
		record_failure("final_independent_goal_check")
		return false
	var quality_value: Dictionary = PIPELINE.quality(decorated, paths, true, self)
	if not quality_value.effect_pass:
		return false
	owner.get_ref().work_phase = ""
	final_source = {"instances": decorated, "independent_audit": checked, "main_paths": paths, "quality": quality_value, "physical_notes": feedback[0], "blockers": feedback[1]}
	return true

func build() -> bool:
	while not aborted():
		if not await grow():
			return false
		var growth := items.duplicate(true)
		for _i in range(config.search.close_attempts):
			if await close_one(config.search.close_depth):
				closed_loops += 1
			if aborted():
				return false
		phase = "air_loop"
		air_connected = await add_air_loop() if request.air_loop.enabled else false
		if aborted():
			return false
		if await finish():
			return true
		if aborted():
			return false
		if repairs >= config.search.max_layout_repairs:
			break
		repairs += 1
		items = growth
		if not rewind():
			break
	error_status = "SEARCH_EXHAUSTED"
	error_message = last_search_failure
	return false

func metrics() -> Dictionary:
	return {"expansions": expanded, "backtracks": backtracks, "layout_repairs": repairs, "terminal_states": terminal_states, "recorded_failures": failures.size(), "closed_loops_across_search": closed_loops, "pruning": rejections.duplicate(true), "generation_seconds": float(Time.get_ticks_usec()-started_usec)/1000000.0}

func diagnostics() -> Dictionary:
	return {"solver_state": {"seed": request.seed, "phase": phase, "instances": items}, "decisions": decisions, "failures": failures, "rng_state": rng.getstate()}
