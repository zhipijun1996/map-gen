extends RefCounted
## Pure data solver. Never creates nodes, loads scenes, or observes live actors.
const ADAPTER = preload("package_adapter.gd")
const VALIDATOR = preload("layout_validator.gd")
const VERSION := "mapgen-godot/1"
var adapter
var validator = VALIDATOR.new()
var region: Dictionary
var modules: Dictionary
var ids: Array = []
var hubs: Array = []
var connectors: Array = []
var rewards: Array = []
var branchers: Array = []
var request: Dictionary
var layout: Dictionary
var result: Dictionary = {}
var cancelled := false
var done := false
var steps := 0
var retries := 0
var rng_state := 1
var started := 0
var cycle_count := 0
var current_hub: Dictionary
var trial: Dictionary = {}
var frontier: Array = []
var rejection_counts: Dictionary = {}
var fallback: Dictionary = {}
var configuration_feedback: Dictionary = {}

func begin(reader, options: Dictionary, seed_value: int, saved_fallback: Dictionary = {}) -> Dictionary:
	adapter = reader; region = options.duplicate(true); request = {"seed": seed_value, "region": region.duplicate(true)}
	result = {}; cancelled = false; done = false; steps = 0; retries = 0; cycle_count = 0; trial = {}; frontier = []; fallback = saved_fallback.duplicate(true); rejection_counts = {}
	configuration_feedback = {}
	if not region.has_all(["schema", "id", "region", "abilities", "host_profile", "package_sha256", "seal_component", "module_budget", "target_branches", "reward_density", "search", "assembly", "repetition", "player_profile"]): return _fail("incomplete_region_configuration")
	if region.get("schema") != "mapgen/region/1" or region.get("allow_mirror", false) or region.get("allow_relocation", false): return _fail("unsupported_region_configuration")
	if region.package_sha256 != adapter.lock.sha256 or region.get("seal_component") != "gear-seal/1": return _fail("region_package_or_seal_mismatch")
	if region.get("runtime_host_profile", adapter.lock.host_profile) != adapter.lock.host_profile: return _fail("runtime_host_profile_mismatch")
	if region.module_budget < 5 or region.module_budget > 128 or region.target_branches < 1 or region.target_branches > 12 or region.reward_density < 0 or region.reward_density > 0.5: return _fail("invalid_scale_or_reward_density")
	if region.search.max_steps < 1 or region.search.max_steps > 2000000 or region.search.max_candidates < 1 or region.search.max_candidates > 128 or region.search.beam_width < 1 or region.search.beam_width > 256 or region.search.max_connector_length < 1 or region.search.max_connector_length > 8 or region.search.max_retries < 1 or region.search.max_retries > 128: return _fail("invalid_search_limits")
	if region.search.get("first_path_min", 0) < 0 or region.search.get("first_path_max", 2) > 4 or region.search.get("first_path_min", 0) > region.search.get("first_path_max", 2): return _fail("invalid_first_path_limits")
	if region.repetition.get("area_reference", 0) <= 0 or region.repetition.get("strength", -1) < 0: return _fail("invalid_repetition_settings")
	var filtered: Dictionary = adapter.pool(region); modules = filtered.modules; ids = modules.keys(); ids.sort()
	hubs = []; connectors = []; rewards = []; branchers = []
	for id: String in ids:
		var entry: Dictionary = modules[id]
		var left: Array = []; var right: Array = []
		for p: Dictionary in entry.ports:
			if p.permission != "INOUT": continue
			if p.face == "LEFT" and p.surface == "ROCK": left.append(p)
			if p.face == "RIGHT" and p.surface == "ROCK": right.append(p)
		left.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.local2[1] < b.local2[1])
		right.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.local2[1] < b.local2[1])
		if left.size() >= 2 and right.size() >= 2:
			var ports: Array = [left[0], left[-1], right[0], right[-1]]
			var clique := true
			for a: Dictionary in ports:
				for b: Dictionary in ports:
					if a.id != b.id and not ADAPTER.bidirectional(entry, a.id, b.id): clique = false
			if clique: hubs.append({"module_id": id, "left": [left[0].id, left[-1].id], "right": [right[0].id, right[-1].id]})
		for a: Dictionary in entry.ports:
			for b: Dictionary in entry.ports:
				if a.id != b.id and ADAPTER.bidirectional(entry, a.id, b.id): connectors.append({"module_id": id, "pin": a.id, "pout": b.id})
		if right.size() >= 2:
			for a: Dictionary in left:
				if ADAPTER.bidirectional(entry, a.id, right[0].id) and ADAPTER.bidirectional(entry, a.id, right[-1].id) and ADAPTER.bidirectional(entry, right[0].id, right[-1].id):
					branchers.append({"module_id": id, "pin": a.id, "pout": right[0].id, "keep": [a.id, right[0].id, right[-1].id]})
		for reward: Dictionary in adapter.reward_routes(entry, region):
			if reward.from == reward.to and entry.ports_by_id[reward.from].face == "LEFT" and ADAPTER.route_between(entry, reward.from, reward.to):
				rewards.append({"module_id": id, "pin": reward.from, "pout": reward.to})
	started = Time.get_ticks_usec(); rng_state = posmod(seed_value, 2147483646) + 1
	var fallback_config: Dictionary = region.get("fallback", {})
	if fallback.is_empty() and fallback_config.get("enabled", false):
		var path: String = fallback_config.get("path", "")
		if FileAccess.file_exists(path) and FileAccess.get_sha256(path) == fallback_config.get("sha256"):
			fallback = ADAPTER.read_json(path)
	if hubs.is_empty() or connectors.is_empty(): return _fail("insufficient_bidirectional_hub_or_connector_pool")
	if region.reward_density > 0 and rewards.is_empty(): return _fail("missing_route_specific_return_reward_pool")
	_start_layout()
	return {"ok": true, "pool_modules": modules.size(), "hubs": hubs.size(), "connectors": connectors.size(), "rewards": rewards.size(), "pool_rejections": filtered.rejections}

func random_int(n: int) -> int:
	rng_state = (rng_state * 48271) % 2147483647
	return rng_state % maxi(1, n)

func _item(id: String, origin: Vector2i, index: int) -> Dictionary:
	return {"instance_id": "%s/node-%03d" % [_namespace(), index], "module_id": id, "content_version": modules[id].contentVersion, "origin": [origin.x, origin.y], "orientation": "identity", "mirror_x": false, "relocations": []}

func _namespace() -> String:
	return str(region.get("instance_namespace", "map/" + str(region.id) + "/seed-" + str(request.seed))).trim_suffix("/")

func _start_layout() -> void:
	current_hub = hubs[random_int(hubs.size())].duplicate(true)
	var item := _item(current_hub.module_id, Vector2i.ZERO, 0)
	current_hub.instance = item
	layout = {"schema": "mapgen/layout/1", "generator_version": VERSION, "seed": request.seed, "lock": adapter.lock.duplicate(true), "region": region.duplicate(true), "instances": [item], "connections": [], "cycles": [], "required_rewards": maxi(1, ceili(region.module_budget * region.reward_density)) if region.reward_density > 0 else 0}
	cycle_count = 0; trial = {}; frontier = []

func cancel() -> void:
	cancelled = true

func step(operation_budget := 128) -> Dictionary:
	if done: return {"done": true, "result": result}
	for _i: int in clampi(operation_budget, 1, 4096):
		if cancelled: _fail("cancelled"); break
		if steps >= region.search.max_steps: _fail("search_step_budget"); break
		if region.search.get("wall_clock_ms", 0) > 0 and Time.get_ticks_usec() - started > int(region.search.wall_clock_ms) * 1000: _fail("wall_clock_timeout"); break
		steps += 1
		if trial.is_empty():
			if cycle_count >= region.target_branches:
				_finish(); break
			if not _new_trial(): continue
		if not frontier.is_empty(): _close_step()
		else: _reject("connector_frontier_exhausted")
		if done: break
	return {"done": done, "steps": steps, "cycles": cycle_count, "instances": layout.get("instances", []).size(), "result": result if done else {}}

func _port(item: Dictionary, pid: String) -> Dictionary:
	var p: Dictionary = modules[item.module_id].ports_by_id[pid].duplicate(true)
	p.world2 = VALIDATOR.world2(item, p); p.instance_id = item.instance_id
	return p

func _attach(source: Dictionary, choice: Dictionary, occupied: Array, index: int) -> Dictionary:
	var entry: Dictionary = modules[choice.module_id]; var pin: Dictionary = entry.ports_by_id[choice.pin]
	if not VALIDATOR.matches(source, pin): return {}
	var delta: Vector2i = source.world2 - Vector2i(pin.local2[0], pin.local2[1])
	if posmod(delta.x, 2) != 0 or posmod(delta.y, 2) != 0: return {}
	var item := _item(entry.id, delta / 2, index)
	for other: Dictionary in occupied:
		if VALIDATOR.rect(item, entry).intersects(VALIDATOR.rect(other, modules[other.module_id])): return {}
	var config: Dictionary = validator.configuration(entry, choice.get("keep", [choice.pin, choice.pout] if choice.pin != choice.pout else [choice.pin]), region)
	if not config.ok:
		var key: String = entry.id + "/" + str(choice.get("keep", [choice.pin, choice.pout]))
		configuration_feedback[key] = {"module_id": entry.id, "content_version": entry.contentVersion, "connected_ports": choice.get("keep", [choice.pin, choice.pout]), "reason": config}
		return {}
	return item

func _cost(choice: Dictionary, occupied: Array) -> float:
	var entry: Dictionary = modules[choice.module_id]
	var area: float = entry.sizeBlocks[0] * entry.sizeBlocks[1]
	var count := 0
	for item: Dictionary in occupied:
		if item.module_id == entry.id: count += 1
	return pow(float(count), 1.3) * clampf(area / region.repetition.area_reference, 0.25, 4.0) * region.repetition.strength + random_int(10000) / 10000.0

func _choices(occupied: Array, source: Dictionary) -> Array:
	var ranked: Array = []
	for choice: Dictionary in connectors:
		if VALIDATOR.matches(source, modules[choice.module_id].ports_by_id[choice.pin]): ranked.append({"choice": choice, "score": _cost(choice, occupied)})
	ranked.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.score < b.score)
	return ranked.slice(0, mini(region.search.max_candidates, ranked.size()))

func _new_trial() -> bool:
	if retries >= region.search.max_retries: _fail("retry_budget"); return false
	retries += 1
	var source := _port(current_hub.instance, current_hub.right[0])
	var other := _port(current_hub.instance, current_hub.right[1])
	var items: Array = []; var links: Array = []
	var path_min: int = region.search.get("first_path_min", 0)
	var path_max: int = region.search.get("first_path_max", 2)
	var length := path_min + random_int(path_max - path_min + 1)
	for _n: int in length:
		var placed := false
		for row: Dictionary in _choices(layout.instances + items, source):
			var choice: Dictionary = row.choice
			var item := _attach(source, choice, layout.instances + items, layout.instances.size() + items.size())
			if item.is_empty(): continue
			items.append(item); links.append({"a": [source.instance_id, source.id], "b": [item.instance_id, choice.pin]})
			source = _port(item, choice.pout); placed = true; break
		if not placed: _reject("first_path_no_candidate"); return false
	var candidate: Dictionary = hubs[random_int(hubs.size())].duplicate(true)
	var new_hub := _attach(source, {"module_id": candidate.module_id, "pin": candidate.left[0], "pout": candidate.left[1]}, layout.instances + items, layout.instances.size() + items.size())
	if new_hub.is_empty(): _reject("hub_collision_or_seal_clearance"); return false
	# Hubs will use four Ports over adjacent cycles; test the actual eventual set.
	items.append(new_hub); links.append({"a": [source.instance_id, source.id], "b": [new_hub.instance_id, candidate.left[0]]})
	candidate.instance = new_hub
	trial = {"items": items, "links": links, "hub": candidate, "target": _port(new_hub, candidate.left[1]), "source": other}
	frontier = [{"items": [], "links": [], "port": other, "score": 0.0}]
	return true

func _close_step() -> void:
	var state: Dictionary = frontier.pop_front()
	var target: Dictionary = trial.target
	if state.port.world2 == target.world2 and VALIDATOR.matches(state.port, target):
		var additions: Array = trial.items + state.items
		if layout.instances.size() + additions.size() + layout.required_rewards > region.module_budget:
			_reject("module_budget"); return
		var all_links: Array = trial.links + state.links + [{"a": [state.port.instance_id, state.port.id], "b": [target.instance_id, target.id]}]
		layout.instances.append_array(additions); layout.connections.append_array(all_links)
		layout.cycles.append({"fork": current_hub.instance.instance_id, "join": trial.hub.instance.instance_id, "connections": all_links.duplicate(true)})
		current_hub = trial.hub; cycle_count += 1; trial = {}; frontier = []
		return
	if state.items.size() >= region.search.max_connector_length: return
	var occupied: Array = layout.instances + trial.items + state.items
	for row: Dictionary in _choices(occupied, state.port):
		var choice: Dictionary = row.choice
		var item := _attach(state.port, choice, occupied, layout.instances.size() + trial.items.size() + state.items.size())
		if item.is_empty(): continue
		var end := _port(item, choice.pout)
		if end.world2.x > target.world2.x + 16: continue
		var distance: float = Vector2(end.world2 - target.world2).length()
		frontier.append({"items": state.items + [item], "links": state.links + [{"a": [state.port.instance_id, state.port.id], "b": [item.instance_id, choice.pin]}], "port": end, "score": distance + state.items.size() * 2 + row.score})
	frontier.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.score < b.score)
	if frontier.size() > region.search.beam_width: frontier.resize(region.search.beam_width)

func _reject(reason: String) -> void:
	rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
	trial = {}; frontier = []

func _anchor(item: Dictionary, pid: String, phase: String) -> Dictionary:
	var entry: Dictionary = modules[item.module_id]; var p: Dictionary = entry.ports_by_id[pid]
	var at: Vector2 = ADAPTER.point(p.get("stagingPosition", p.position)) - Vector2(entry.bounds.x, entry.bounds.y) + Vector2(item.origin[0], item.origin[1]) * 128
	return {"node": VALIDATOR.endpoint(item.instance_id, pid, phase), "instance_id": item.instance_id, "port_id": pid, "position": [at.x, at.y], "adapter": region.anchor_adapter_version}

func _finish() -> void:
	var attached := 0
	# Attach route-specific return rewards to genuinely unused side Ports, with
	# full geometry checks. A chest elsewhere in a module is never counted.
	var used: Dictionary = {}
	for link: Dictionary in layout.connections:
		used[str(link.a)] = true; used[str(link.b)] = true
	# Grow real exploration hubs when reward density needs more spatially
	# separated return pockets. These are instances, never copied templates.
	for _n: int in maxi(0, layout.required_rewards - 1):
		var candidates: Array = layout.instances.duplicate(); candidates.reverse()
		var extended := false
		for source_item: Dictionary in candidates:
			if extended: break
			var ordered: Array = modules[source_item.module_id].ports.duplicate()
			ordered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.local2[1] > b.local2[1])
			for p: Dictionary in ordered:
				if extended: break
				if p.face != "RIGHT" or used.has(str([source_item.instance_id, p.id])): continue
				var source := _port(source_item, p.id)
				for b: Dictionary in branchers:
					var new_item := _attach(source, b, layout.instances, layout.instances.size())
					if new_item.is_empty(): continue
					layout.instances.append(new_item); layout.connections.append({"a": [source_item.instance_id, p.id], "b": [new_item.instance_id, b.pin]})
					used[str([source_item.instance_id, p.id])] = true; used[str([new_item.instance_id, b.pin])] = true; extended = true; break
	var existing: Array = layout.instances.duplicate()
	for item: Dictionary in existing:
		var ports: Array = modules[item.module_id].ports.duplicate()
		ports.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.local2[1] > b.local2[1])
		for p: Dictionary in ports:
			if attached >= layout.required_rewards: break
			if used.has(str([item.instance_id, p.id])) or p.face != "RIGHT": continue
			var source := _port(item, p.id)
			for n: int in rewards.size():
				var choice: Dictionary = rewards[(n + request.seed % rewards.size() + rewards.size()) % rewards.size()]
				var reward_item := _attach(source, choice, layout.instances, layout.instances.size())
				if reward_item.is_empty(): continue
				layout.instances.append(reward_item)
				layout.connections.append({"a": [item.instance_id, p.id], "b": [reward_item.instance_id, choice.pin]})
				used[str([item.instance_id, p.id])] = true; attached += 1; break
	if attached < layout.required_rewards: _fail("reward_branch_placement_failed"); return
	if layout.instances.size() > region.module_budget: _fail("module_budget"); return
	var root_item: Dictionary = layout.instances[0]
	var root_hub: Dictionary = hubs.filter(func(h: Dictionary) -> bool: return h.module_id == root_item.module_id)[0]
	layout.spawn = _anchor(root_item, root_hub.right[1], "in")
	layout.goal = _anchor(current_hub.instance, current_hub.left[0], "in")
	var validation: Dictionary = validator.validate(layout, modules, region, adapter)
	layout.validation = validation
	if not validation.ok: _fail("final_validation_failed", validation); return
	done = true
	layout.diagnostics = _diagnostics()
	result = {"ok": true, "fallback": false, "layout": layout, "diagnostics": layout.diagnostics}

func _diagnostics() -> Dictionary:
	return {"steps": steps, "retries": retries, "cycles": cycle_count, "elapsed_usec": Time.get_ticks_usec() - started if started > 0 else 0, "rejections": rejection_counts.duplicate(true), "configuration_feedback": configuration_feedback.values(), "pool_size": modules.size() if modules != null else 0}

func _fail(reason: String, details: Dictionary = {}) -> Dictionary:
	done = true; result = {"ok": false, "fallback": false, "reason": reason, "details": details, "diagnostics": _diagnostics()}
	# Cancellation is never turned into a scene request. A fallback must match
	# the full version/config lock and carry a development physics receipt.
	var compatible: bool = not fallback.is_empty() and fallback.get("lock") == adapter.lock
	for field: String in ["id", "region", "abilities", "native_profile_id", "host_profile", "runtime_host_profile", "package_sha256", "seal_component", "anchor_adapter_version", "reward_route_overrides", "player_profile"]:
		if fallback.get("region", {}).get(field) != region.get(field): compatible = false
	if region.has("allowed_module_ids"):
		for item: Dictionary in fallback.get("instances", []):
			if item.module_id not in region.allowed_module_ids: compatible = false
	if reason != "cancelled" and compatible and fallback.get("validation", {}).get("whole_map_physics") == "PASS" and fallback.get("physics_receipt", {}).get("failures", ["missing"]).is_empty():
		var mapping: Dictionary = {}
		for n: int in fallback.instances.size(): mapping[fallback.instances[n].instance_id] = "%s/node-%03d" % [_namespace(), n]
		var rebased: Dictionary = _rebase(fallback, mapping)
		rebased.region.instance_namespace = _namespace()
		rebased.physics_receipt.identity_rebase = {"kind": "stable_id_namespace_only/1", "source_instance_ids": mapping.keys()}
		var checked: Dictionary = validator.validate(rebased, modules, region, adapter)
		if checked.ok:
			result = {"ok": true, "fallback": true, "reason": reason, "layout": rebased, "diagnostics": _diagnostics(), "requested": request, "degradation": {"actual_modules": rebased.instances.size(), "actual_rewards": rebased.rewards.size(), "actual_splits": rebased.cycles.size(), "policy": "verified_small_layout; requested scale/reward density may be reduced"}}
	return result

func _rebase(value: Variant, mapping: Dictionary) -> Variant:
	if value is Dictionary:
		var result_dict: Dictionary = {}
		for key: Variant in value: result_dict[key] = _rebase(value[key], mapping)
		return result_dict
	if value is Array:
		var result_array: Array = []
		for item: Variant in value: result_array.append(_rebase(item, mapping))
		return result_array
	if value is String:
		for old: String in mapping:
			if value == old: return mapping[old]
			if value.begins_with(old + "/"): return str(mapping[old]) + value.substr(old.length())
	return value
