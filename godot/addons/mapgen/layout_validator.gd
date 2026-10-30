extends RefCounted
const ADAPTER = preload("package_adapter.gd")
const SEAL = preload("gear_seal.gd")
const OPPOSITE := {"LEFT": "RIGHT", "RIGHT": "LEFT", "TOP": "BOTTOM", "BOTTOM": "TOP"}
var compatibility: Dictionary = {}

static func rect(item: Dictionary, entry: Dictionary) -> Rect2i:
	return Rect2i(Vector2i(item.origin[0], item.origin[1]), Vector2i(entry.sizeBlocks[0], entry.sizeBlocks[1]))

static func world2(item: Dictionary, port: Dictionary) -> Vector2i:
	return Vector2i(item.origin[0] * 2 + port.local2[0], item.origin[1] * 2 + port.local2[1])

static func matches(a: Dictionary, b: Dictionary) -> bool:
	return OPPOSITE.get(a.face) == b.face and a.surface == b.surface and ((a.permission != "INPUT" and b.permission != "OUTPUT") or (b.permission != "INPUT" and a.permission != "OUTPUT"))

static func endpoint(i: String, p: String, phase: String) -> String:
	return i + "/" + p + "/" + phase

static func reachable(graph: Dictionary, source: String) -> Dictionary:
	var seen := {source: true}; var pending: Array = [source]; var n := 0
	while n < pending.size():
		var key: String = pending[n]; n += 1
		for target: String in graph.get(key, []):
			if not seen.has(target): seen[target] = true; pending.append(target)
	return seen

func configuration(entry: Dictionary, connected: Array, region: Dictionary) -> Dictionary:
	var sorted := connected.duplicate(); sorted.sort()
	var key: String = entry.id + "/" + entry.contentVersion + "/" + str(sorted) + "/" + str(region.abilities) + "/" + str(region.get("native_profile_id")) + "/" + SEAL.VERSION
	if compatibility.has(key): return compatibility[key]
	var seals: Array = []; var routes: Array = ADAPTER.active_routes(entry, sorted)
	for port: Dictionary in entry.ports:
		if port.id in sorted: continue
		var spec: Dictionary = SEAL.describe(port, entry.bounds)
		var rr: Array = spec.rect_pixels
		var r := Rect2(rr[0], rr[1], rr[2], rr[3])
		if not Rect2(0, 0, entry.bounds.w, entry.bounds.h).encloses(r): return {"ok": false, "reason": "seal_outside_owned_rectangle"}
		for route: Dictionary in routes:
			var path: Array = route.path_points
			for i: int in maxi(0, path.size() - 1):
				var a := ADAPTER.point(path[i]) - Vector2(entry.bounds.x, entry.bounds.y)
				var b := ADAPTER.point(path[i + 1]) - Vector2(entry.bounds.x, entry.bounds.y)
				# Conservative body-sized authored-path clearance, not physics certification.
				if segment_hits(a, b, r.grow_individual(12, 18, 12, 18)):
					var rejected := {"ok": false, "reason": "seal_intersects_retained_authored_path", "module_id": entry.id, "port_id": port.id, "route_id": route.id}
					compatibility[key] = rejected; return rejected
		seals.append(spec)
	var result := {"ok": true, "connected_port_ids": sorted, "sealed_ports": seals, "routes": routes, "upstream_scope": "original-all-ports", "overlay": SEAL.VERSION, "clearance": "authored_path_only", "physical": "NOT_TESTED"}
	compatibility[key] = result
	return result

static func segment_hits(a: Vector2, b: Vector2, r: Rect2) -> bool:
	return DemoContactEmitter.segment_intersects_bounds(a, b, r)

func validate(layout: Dictionary, modules: Dictionary, region: Dictionary, adapter) -> Dictionary:
	if not layout.has_all(["instances", "connections", "spawn", "goal"]): return {"ok": false, "errors": ["incomplete_layout"]}
	if layout.instances.is_empty() or layout.instances.size() > mini(128, int(region.module_budget)) or layout.connections.size() > 1024: return {"ok": false, "errors": ["layout_size_budget"]}
	var errors: Array = []; var instances: Dictionary = {}; var used: Dictionary = {}; var graph: Dictionary = {}; var edges: Array = []
	for item: Dictionary in layout.instances:
		if instances.has(item.instance_id) or not modules.has(item.module_id): return {"ok": false, "errors": ["duplicate_instance_or_unknown_module"]}
		if item.get("orientation") != "identity" or item.get("mirror_x", false) or not item.get("relocations", []).is_empty(): return {"ok": false, "errors": ["unsupported_transform"]}
		if item.content_version != modules[item.module_id].contentVersion: return {"ok": false, "errors": ["content_version_mismatch"]}
		for value: Variant in item.origin:
			if not is_finite(float(value)) or float(value) != floorf(float(value)): return {"ok": false, "errors": ["non_integer_origin"]}
		for other: Dictionary in instances.values():
			if rect(item, modules[item.module_id]).intersects(rect(other, modules[other.module_id])): errors.append("overlap/" + item.instance_id + "/" + other.instance_id)
		instances[item.instance_id] = item; used[item.instance_id] = []
	for name: String in ["spawn", "goal"]:
		var anchor: Dictionary = layout[name]
		if not instances.has(anchor.get("instance_id", "")): return {"ok": false, "errors": ["unknown_anchor_instance"]}
		var item: Dictionary = instances[anchor.instance_id]; var entry: Dictionary = modules[item.module_id]
		if not entry.ports_by_id.has(anchor.get("port_id", "")): return {"ok": false, "errors": ["unknown_anchor_port"]}
		var p: Dictionary = entry.ports_by_id[anchor.port_id]
		var at := ADAPTER.point(p.get("stagingPosition", p.position)) - Vector2(entry.bounds.x, entry.bounds.y) + Vector2(item.origin[0], item.origin[1]) * 128
		if not at.is_equal_approx(ADAPTER.point(anchor.position)) or anchor.node not in [endpoint(item.instance_id, p.id, "in"), endpoint(item.instance_id, p.id, "out")]: return {"ok": false, "errors": ["anchor_adapter_mismatch"]}
	for link: Dictionary in layout.connections:
		if not instances.has(link.a[0]) or not instances.has(link.b[0]): return {"ok": false, "errors": ["unknown_link_instance"]}
		var a: Dictionary = instances[link.a[0]]; var b: Dictionary = instances[link.b[0]]
		var am: Dictionary = modules[a.module_id]; var bm: Dictionary = modules[b.module_id]
		if not am.ports_by_id.has(link.a[1]) or not bm.ports_by_id.has(link.b[1]): return {"ok": false, "errors": ["unknown_link_port"]}
		var ap: Dictionary = am.ports_by_id[link.a[1]]; var bp: Dictionary = bm.ports_by_id[link.b[1]]
		if link.a[1] in used[a.instance_id] or link.b[1] in used[b.instance_id]: errors.append("port_connected_twice")
		used[a.instance_id].append(ap.id); used[b.instance_id].append(bp.id)
		if not matches(ap, bp) or world2(a, ap) != world2(b, bp): errors.append("invalid_seam")
		if ap.permission != "INPUT" and bp.permission != "OUTPUT": edges.append({"from": endpoint(a.instance_id, ap.id, "out"), "to": endpoint(b.instance_id, bp.id, "in"), "kind": "seam", "physical": "NOT_TESTED"})
		if bp.permission != "INPUT" and ap.permission != "OUTPUT": edges.append({"from": endpoint(b.instance_id, bp.id, "out"), "to": endpoint(a.instance_id, ap.id, "in"), "kind": "seam", "physical": "NOT_TESTED"})
	for item: Dictionary in layout.instances:
		var entry: Dictionary = modules[item.module_id]
		var cfg := configuration(entry, used[item.instance_id], region)
		if not cfg.ok: errors.append(cfg); continue
		if item.has("connected_port_ids") and not ADAPTER.same_set(item.connected_port_ids, cfg.connected_port_ids): errors.append("connected_set_mismatch")
		if item.has("sealed_ports") and item.sealed_ports != cfg.sealed_ports: errors.append("seal_reconstruction_mismatch")
		item.connected_port_ids = cfg.connected_port_ids; item.sealed_ports = cfg.sealed_ports
		item.configuration = {"id": "mapgen-gear-subset/1", "upstream_scope": cfg.upstream_scope, "component": cfg.overlay}
		for route: Dictionary in cfg.routes:
			edges.append({"from": endpoint(item.instance_id, route.from, "in"), "to": endpoint(item.instance_id, route.to, "out"), "kind": "module_route", "route_id": route.id, "instance_id": item.instance_id, "conditions": route.get("initialConditions", {}), "validation": route.validation, "physical": "NOT_TESTED"})
	for edge: Dictionary in edges:
		if not graph.has(edge.from): graph[edge.from] = []
		graph[edge.from].append(edge.to)
	var reached := reachable(graph, layout.spawn.node)
	if not reached.has(layout.goal.node): errors.append("goal_unreachable")
	var rewards: Array = []
	for item: Dictionary in layout.instances:
		var entry: Dictionary = modules[item.module_id]
		for reward: Dictionary in adapter.reward_routes(entry, region):
			var start := endpoint(item.instance_id, reward.from, "in"); var finish := endpoint(item.instance_id, reward.to, "out")
			if reward.from not in used[item.instance_id] or reward.to not in used[item.instance_id]: continue
			if reached.has(start) and reachable(graph, finish).has(layout.goal.node):
				var p: Vector2 = ADAPTER.point(reward.site.position) - Vector2(entry.bounds.x, entry.bounds.y) + Vector2(item.origin[0], item.origin[1]) * 128
				rewards.append({"instance_id": item.instance_id, "site_id": reward.site.id, "route_id": reward.route_id, "position": [p.x, p.y], "entry_node": start, "exit_node": finish, "evidence": reward.evidence, "physical": "NOT_TESTED"})
	if rewards.size() < layout.get("required_rewards", 0): errors.append("insufficient_route_specific_rewards")
	layout.rewards = rewards; layout.effective_edges = edges
	return {"ok": errors.is_empty(), "errors": errors, "geometry": "PASS" if errors.is_empty() else "FAIL", "declared_routes": "PASS" if errors.is_empty() else "FAIL", "seams": "NOT_TESTED", "closures": "AUTHORED_PATH_CLEARANCE_ONLY", "whole_map_physics": "NOT_TESTED", "rewards": rewards.size()}
