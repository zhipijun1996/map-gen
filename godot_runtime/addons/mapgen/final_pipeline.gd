extends RefCounted
const GEO = preload("geometry.gd")
const TRANSFORM = preload("content_transform.gd")
const NUM = preload("numeric.gd")

static func assembly_gate(solver) -> bool:
	# Preserve the original assembly mutations and its separate reward graph gate.
	var used: Dictionary = {}
	var edges: Array = []
	var groups: Array = (await solver.sort_rows(GEO.connection_groups(solver.items), func(a,b):
		return a[0][2].world2[0] < b[0][2].world2[0] if a[0][2].world2[0] != b[0][2].world2[0] else a[0][2].world2[1] < b[0][2].world2[1]))
	var n := 0
	for group in groups:
		n += 1
		for row in group:
			used[row[0].id+"."+row[1]] = true
			row[2].connection = "C%02d" % n
	for item in solver.items:
		if not await solver.checkpoint():
			return false
		item.actual_routes = []
		item.inactive_routes = []
		item.closures = []
		for pid in item.ports:
			if not used.has(item.id+"."+pid):
				item.closures.append(pid)
				item.ports[pid].closed = true
		for original in solver.templates[item.module_id].routes:
			var route: Dictionary = original.duplicate(true)
			if item.mirror_x:
				route.displacement[0] *= -1
			if route.from_port in item.closures or route.to_port in item.closures or not solver.has_abilities(route.required_abilities):
				item.inactive_routes.append(route)
				continue
			item.actual_routes.append(route)
			var a: String = item.id+"."+route.from_port+":arrive"
			var b: String = item.id+"."+route.to_port+":depart"
			if item.reward:
				var node: String = item.id+":reward:"+route.id
				edges.append([a, node])
				edges.append([node, b])
			else:
				edges.append([a,b])
	for group in groups:
		var a: Array = group[0]
		var b: Array = group[1]
		if GEO.permitted(a[2], "out") and GEO.permitted(b[2], "in"):
			edges.append([a[0].id+"."+a[1]+":depart", b[0].id+"."+b[1]+":arrive"])
		if GEO.permitted(b[2], "out") and GEO.permitted(a[2], "in"):
			edges.append([b[0].id+"."+b[1]+":depart", a[0].id+"."+a[1]+":arrive"])
	edges.append(["START", "M01.R:depart"])
	for item in solver.items:
		if not await solver.checkpoint():
			return false
		if item.module_id == "BOSS":
			edges.append([item.id+".L:arrive", "BOSS"])
	var g: Dictionary = {}
	for pair in edges:
		solver.edge(g, pair[0], pair[1])
	var seen: Dictionary = (await solver.reachable(g, "START"))
	if not seen.has("BOSS"):
		return false
	for item in solver.items:
		if not await solver.checkpoint():
			return false
		if item.reward:
			var found := false
			for node in seen:
				if node.begins_with(item.id+":reward:"):
					found = true
					if not (await solver.reachable(g, node)).has("BOSS"):
						return false
			if not found:
				return false
		var routes: Array = solver.templates[item.module_id].routes
		item.lane = "reward" if item.reward else "shared" if item.module_id in ["START", "BOSS"] else "air" if item.module_id.begins_with("AIR") else (routes[0].required_abilities[0] if not routes[0].required_abilities.is_empty() else "move")
	return true

static func decorate(items: Array, solver) -> Array:
	var library = solver.library
	var used: Dictionary = {}
	for group in GEO.connection_groups(items):
		for row in group:
			used[row[0].id+"."+row[1]] = true
	var notes: Array = []
	var blockers: Array = []
	for item in items:
		if not await solver.checkpoint():
			return []
		var template: Dictionary = solver.templates[item.module_id]
		var entry: Dictionary = library.entries[template.source_module_id]
		item.solver_port_ids = item.ports.keys()
		var full := GEO.placed_ports(template, item.origin[0], item.origin[1], item.mirror_x, true)
		for pid in item.ports:
			full[pid].merge(item.ports[pid], true)
		item.ports = full
		item.source_module_id = entry.id
		item.content_version = entry.contentVersion
		item.scene = entry.scene
		item.scene_origin_offset = entry.sceneOriginOffsetPixels
		item.source_bounds = entry.bounds
		item.content = TRANSFORM.materialize(template, item.mirror_x, library.block_pixels)
		item.connected_port_ids = []
		item.sealed_ports = []
		var closed: Dictionary = {}
		for pid in item.ports:
			if used.has(item.id+"."+pid):
				item.connected_port_ids.append(pid)
			else:
				item.sealed_ports.append(library.gear_seal(item.ports[pid], item.size_blocks))
				closed[pid] = true
		var effective: Array = []
		for original in template.all_routes:
			if not await solver.checkpoint():
				return []
			var route: Dictionary = original.duplicate(true)
			if item.mirror_x:
				route.displacement[0] *= -1
				for point in route.path_points:
					point[0] = item.size_blocks[0]*library.block_pixels-point[0]
			if closed.has(route.from_port) or closed.has(route.to_port) or not solver.has_abilities(route.required_abilities):
				continue
			effective.append(route)
			var base := {"instance": item.id, "module_id": entry.id, "route_id": route.id}
			if not GEO.permitted(item.ports[route.from_port], "in") or not GEO.permitted(item.ports[route.to_port], "out"):
				var row := base.duplicate()
				row.reason = "route_violates_initial_permission"
				blockers.append(row)
			var available: Dictionary = {}
			for ability in route.required_abilities:
				available[ability] = true
			if available.size() != library.abilities.size():
				var row := base.duplicate()
				row.merge({"reason": "available_ability_superset_not_physically_witnessed", "witnessed": route.required_abilities})
				notes.append(row)
			if route.validation.get("testNeighborFixtures", []):
				var row := base.duplicate()
				row.merge({"reason": "external_neighbor_fixture_not_bound", "fixtures": route.validation.testNeighborFixtures})
				blockers.append(row)
			if route.path_points.size() < 2:
				var row := base.duplicate()
				row.reason = "missing_author_path_for_seal_clearance"
				blockers.append(row)
			for seal in item.sealed_ports:
				var rect: Array = library.clearance_rect(seal.rect_pixels)
				var hit := false
				for k in range(route.path_points.size()-1):
					if GEO.segment_hits_rect(route.path_points[k], route.path_points[k+1], rect):
						hit = true
						break
				if hit:
					var row := base.duplicate()
					row.merge({"reason": "gear_seal_intersects_author_path", "port_id": seal.port_id, "rect_pixels": seal.rect_pixels})
					blockers.append(row)
		item.effective_routes = effective
		item.retained_route_ids = []
		for route in effective:
			item.retained_route_ids.append(route.id)
		item.reward_sites = item.content.reward_sites.duplicate(true)
		if item.mirror_x or not item.sealed_ports.is_empty():
			notes.append({"instance": item.id, "module_id": entry.id, "reason": "transformed_or_sealed_configuration_physics_not_run"})
		var profile = entry.initialConfiguration.get("nativeFixture")
		if not profile:
			profile = entry.initialConfiguration.get("nativeTuning")
		if profile:
			notes.append({"instance": item.id, "module_id": entry.id, "reason": "native_player_profile_requires_future_host_binding", "profile": profile})
	return [notes, blockers]

static func configured_connections(items: Array) -> Array:
	var views: Array = []
	for original in items:
		var item: Dictionary = original.duplicate()
		item.ports = {}
		for pid in original.ports:
			if pid in original.get("solver_port_ids", original.ports.keys()):
				item.ports[pid] = original.ports[pid]
		views.append(item)
	return GEO.connection_groups(views)

static func audit(items: Array, solver) -> Dictionary:
	var g: Dictionary = {}
	var reward_nodes: Array = []
	var blockers: Array = []
	var used: Dictionary = {}
	var occupied: Dictionary = {}
	var library = solver.library
	var invariants: Array = []
	for item in items:
		if not await solver.checkpoint():
			return {}
		var x: int = item.origin[0]
		var y: int = item.origin[1]
		var width: int = item.size_blocks[0]
		var height: int = item.size_blocks[1]
		for bx in range(x, x+width):
			for by in range(y, y+height):
				var key := GEO.coordinate_key([bx, by])
				if occupied.has(key):
					invariants.append("overlapping occupied Block")
				occupied[key] = true
		for port in item.ports.values():
			var u: int = port.local2[0]
			var v: int = port.local2[1]
			var face: String = port.face
			if port.world2 != [2*x+u, 2*y+v]:
				invariants.append("Port world position")
			if face in ["LEFT", "RIGHT"]:
				if u != (0 if face == "LEFT" else 2*width) or v%2 != 1 or v <= 0 or v >= 2*height:
					invariants.append("Port horizontal boundary")
			elif v != (0 if face == "TOP" else 2*height) or u%2 != 1 or u <= 0 or u >= 2*width:
				invariants.append("Port vertical boundary")
			if port.surface == "ROCK" and not face in ["LEFT", "RIGHT"] or port.surface == "AIR" and face == "BOTTOM" and GEO.permitted(port, "in"):
				invariants.append("Port surface/permission")
		var closed: Dictionary = {}
		for seal in item.sealed_ports:
			closed[seal.port_id] = true
			var r: Array = seal.rect_pixels
			if not (0 <= r[0] and r[0] < r[0]+r[2] and r[0]+r[2] <= width*library.block_pixels and 0 <= r[1] and r[1] < r[1]+r[3] and r[1]+r[3] <= height*library.block_pixels):
				invariants.append("seal outside owned rectangle")
		for pid in item.ports:
			if (pid in item.connected_port_ids) == closed.has(pid):
				invariants.append("Port seal exact coverage")
		for route in item.effective_routes:
			if closed.has(route.from_port) or closed.has(route.to_port):
				invariants.append("Route uses sealed Port")
			var a: Array = item.ports[route.from_port].world2
			var b: Array = item.ports[route.to_port].world2
			if route.displacement != [float(b[0]-a[0])/2, float(b[1]-a[1])/2]:
				invariants.append("Route displacement")
			var chain: Array = [item.id+"."+route.from_port+":arrive"]
			if item.reward and not route.reward_ids.is_empty():
				var node: String = item.id+":reward:"+route.id
				chain.append(node)
				reward_nodes.append({"node": node, "instance": item.id, "module_id": item.source_module_id, "route_id": route.id, "reward_ids": route.reward_ids, "target": true})
			else:
				for rid in route.reward_ids:
					var node: String = item.id+":reward:"+route.id+":"+rid
					chain.append(node)
					reward_nodes.append({"node": node, "instance": item.id, "module_id": item.source_module_id, "route_id": route.id, "reward_ids": [rid], "target": false})
			chain.append(item.id+"."+route.to_port+":depart")
			for k in range(chain.size()-1):
				solver.edge(g, chain[k], chain[k+1])
	for group in configured_connections(items):
		if not await solver.checkpoint():
			return {}
		for row in group:
			var key: String = row[0].id+"."+row[1]
			if used.has(key):
				invariants.append("Port has multiple connections")
			used[key] = true
		var a: Array = group[0]
		var b: Array = group[1]
		if GEO.permitted(a[2], "out") and GEO.permitted(b[2], "in"):
			solver.edge(g, a[0].id+"."+a[1]+":depart", b[0].id+"."+b[1]+":arrive")
		if GEO.permitted(b[2], "out") and GEO.permitted(a[2], "in"):
			solver.edge(g, b[0].id+"."+b[1]+":depart", a[0].id+"."+a[1]+":arrive")
	solver.edge(g, "START", "M01.R:depart")
	var boss: Dictionary = {}
	for item in items:
		if item.module_id == "BOSS":
			boss = item
			solver.edge(g, item.id+".L:arrive", "BOSS")
	var seen: Dictionary = (await solver.reachable(g, "START"))
	if boss.is_empty():
		blockers.append({"reason": "boss_not_placed"})
	elif not "L" in boss.connected_port_ids:
		blockers.append({"reason": "boss_declared_entry_not_connected", "instance": boss.id, "module_id": boss.source_module_id, "connected_ports": boss.connected_port_ids})
	if not seen.has("BOSS"):
		blockers.append({"reason": "boss_unreachable"})
	var reward_count := 0
	var site_count := 0
	var reached: Dictionary = {}
	for node in seen:
		reached[node.split(".")[0].split(":")[0]] = true
	var missing: Array = []
	for item in items:
		site_count += item.reward_sites.size()
		if not reached.has(item.id):
			missing.append({"instance": item.id, "module_id": item.source_module_id})
		if not item.reward:
			continue
		reward_count += 1
		var nodes: Array = reward_nodes.filter(func(r): return r.instance == item.id and seen.has(r.node))
		if nodes.is_empty():
			blockers.append({"reason": "target_reward_unreachable", "instance": item.id, "module_id": item.source_module_id})
		for node in nodes:
			if not (await solver.reachable(g, node.node)).has("BOSS"):
				var row: Dictionary = node.duplicate()
				row.reason = "target_reward_cannot_continue_to_boss"
				blockers.append(row)
	if reward_count != solver.config.goals.reward_target:
		blockers.append({"reason": "reward_target_not_met", "expected": solver.config.goals.reward_target, "actual": reward_count})
	if not missing.is_empty():
		blockers.append({"reason": "unreachable_instances", "instances": missing})
	for node in reward_nodes:
		node.reachable = seen.has(node.node)
		node.can_continue_to_boss = (await solver.reachable(g, node.node)).has("BOSS")
	for invariant in invariants:
		blockers.append({"reason": "geometry_invariant", "detail": invariant})
	return {"geometry": "PASS" if invariants.is_empty() else "FAIL", "gear_seal_coverage": "PASS" if invariants.is_empty() else "FAIL", "boss_reachable": seen.has("BOSS"), "target_reward_instances": reward_count, "all_reward_sites": site_count, "route_reward_nodes": reward_nodes, "unreachable_instances": missing, "blockers": blockers, "edges": solver.graph_edges(g)}

static func quality(items: Array, paths: Array, static_pass: bool, solver) -> Dictionary:
	var bounds := GEO.bounds(items)
	var width: int = bounds[2]-bounds[0]
	var height: int = bounds[3]-bounds[1]
	var area := 0
	var rewards := 0
	for item in items:
		area += item.size_blocks[0]*item.size_blocks[1]
		if item.reward:
			rewards += 1
	var targets: bool = static_pass and rewards == solver.config.goals.reward_target and paths.size() >= solver.config.goals.main_paths_required
	var shape: bool = solver.aspect(items) <= solver.config.shape.max_aspect
	return {"bounds_blocks": bounds, "width": width, "height": height, "aspect": solver.aspect(items), "occupancy": float(area)/float(width*height), "static_pass": static_pass, "targets_pass": targets, "shape_pass": shape, "effect_pass": targets and shape, "main_paths": paths.size(), "target_rewards": rewards}
