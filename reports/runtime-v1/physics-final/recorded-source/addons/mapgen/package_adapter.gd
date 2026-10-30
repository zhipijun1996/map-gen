extends RefCounted
## Immutable package reader. UNKNOWN mapReady is not used as a rejection flag.
var root: String
var lock: Dictionary
var manifest: Dictionary
var entries: Dictionary = {}
var excluded: Array = []
var pools: Dictionary = {}

static func read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return value if value is Dictionary else {}

static func point(value: Variant) -> Vector2:
	return Vector2(value[0], value[1]) if value is Array else Vector2(value.x, value.y)

static func same_set(a: Array, b: Array) -> bool:
	var aa := a.duplicate(); var bb := b.duplicate()
	aa.sort(); bb.sort()
	return aa == bb

func open(package_root: String, version_lock: Dictionary, verify_files := true) -> Dictionary:
	root = package_root.trim_suffix("/"); lock = version_lock.duplicate(true)
	manifest = read_json(root.path_join("manifest.json"))
	var installed := read_json("res://configs/installed.json")
	if installed.get("lock", {}).get("sha256") != lock.get("sha256"):
		return {"ok": false, "reason": "missing_or_mismatched_install_receipt"}
	if FileAccess.get_sha256(root.path_join("manifest.json")) != installed.get("manifest_sha256"):
		return {"ok": false, "reason": "manifest_hash_mismatch"}
	if manifest.get("version") != lock.get("package_version") or manifest.get("runtimeFingerprint") != lock.get("runtime_fingerprint"):
		return {"ok": false, "reason": "package_version_or_runtime_mismatch"}
	if Engine.get_version_info().string != lock.get("godot_version"):
		return {"ok": false, "reason": "godot_version_mismatch", "actual": Engine.get_version_info().string}
	if not str(Engine.get_version_info().hash).begins_with(lock.get("godot_build_hash", "INVALID")):
		return {"ok": false, "reason": "godot_build_hash_mismatch"}
	if Engine.physics_ticks_per_second != 60: return {"ok": false, "reason": "physics_tick_profile_mismatch"}
	if verify_files:
		for path: String in manifest.get("files", {}):
			if path.is_absolute_path() or ".." in path.split("/") or FileAccess.get_sha256(root.path_join(path)) != manifest.files[path]:
				return {"ok": false, "reason": "package_file_hash_mismatch", "file": path}
		var host := read_json(root.path_join(lock.get("host_dependency", manifest.hostDependency)))
		for path: String in host.files:
			if FileAccess.get_sha256("res://" + path) != host.files[path]:
				return {"ok": false, "reason": "host_dependency_hash_mismatch", "file": path}
	var catalog := read_json(root.path_join("catalog.json"))
	if catalog.get("schema") != "map-edit/delivery-catalog/v1": return {"ok": false, "reason": "catalog_schema"}
	entries.clear()
	pools.clear()
	for raw: Dictionary in catalog.get("modules", []):
		var entry := raw.duplicate(true)
		if entries.has(entry.id): return {"ok": false, "reason": "duplicate_module_id"}
		entry.compiled_data = read_json(root.path_join(entry.compiled))
		var doc := read_json(root.path_join(entry.scene.get_base_dir().path_join("module.mapnote.json")))
		var objects: Dictionary = {}
		for obj: Dictionary in doc.get("objects", []): objects[obj.id] = obj
		entry.ports_by_id = {}
		for port: Dictionary in entry.ports:
			var local := (point(port.position) - Vector2(entry.bounds.x, entry.bounds.y)) / 64.0
			if local != local.round(): return {"ok": false, "reason": "non_block_port", "module": entry.id}
			port.local2 = [int(local.x), int(local.y)]
			entry.ports_by_id[port.id] = port
		for route: Dictionary in entry.routes:
			route.path_points = objects.get(route.get("pathObjectId", ""), {}).get("points", [])
		entries[entry.id] = entry
	excluded = catalog.get("excluded", [])
	return {"ok": true, "modules": entries.size(), "package_version": manifest.version}

func pool(region: Dictionary) -> Dictionary:
	var abilities: Array = region.abilities.duplicate(); abilities.sort()
	var allowed: Array = region.get("allowed_module_ids", []).duplicate(); allowed.sort()
	var pool_key := JSON.stringify([region.region, region.host_profile, abilities, region.get("native_profile_id"), allowed])
	if pools.has(pool_key): return pools[pool_key]
	var usable: Dictionary = {}; var rejections: Array = []
	var ids := entries.keys(); ids.sort()
	for id: String in ids:
		var entry: Dictionary = entries[id]
		if region.has("allowed_module_ids") and id not in region.allowed_module_ids: continue
		if entry.region != region.region or entry.hostProfile != region.host_profile: continue
		var native: Variant = entry.initialConfiguration.get("nativeFixture")
		if native == null: native = entry.initialConfiguration.get("nativeTuning")
		if native is Dictionary and native.get("id") != region.get("native_profile_id"):
			rejections.append({"module_id": id, "reason": "different_initial_player_profile"}); continue
		var copy := entry.duplicate(true); copy.usable_routes = []
		for route: Dictionary in copy.routes:
			var a: Dictionary = copy.ports_by_id[route.from]; var b: Dictionary = copy.ports_by_id[route.to]
			var reason := ""
			if not same_set(route.validation.availableAbilities, region.abilities): reason = "ability_set_not_witnessed"
			elif not route.validation.get("testNeighborFixtures", []).is_empty(): reason = "external_neighbor_fixture_required"
			elif a.permission == "OUTPUT" or b.permission == "INPUT": reason = "initial_permission"
			for port: Dictionary in [a, b]:
				var conditions: Dictionary = port.get("initialPermissionConditions", {})
				if conditions.has("availableAbilitiesExact") and not same_set(conditions.availableAbilitiesExact, region.abilities): reason = "port_initial_ability_condition"
			if reason.is_empty(): copy.usable_routes.append(route)
			else: rejections.append({"module_id": id, "route_id": route.id, "reason": reason})
		if not copy.usable_routes.is_empty(): usable[id] = copy
	var result := {"modules": usable, "rejections": rejections}
	pools[pool_key] = result
	return result

static func active_routes(entry: Dictionary, connected: Array) -> Array:
	return entry.usable_routes.filter(func(r: Dictionary) -> bool: return r.from in connected and r.to in connected)

static func route_between(entry: Dictionary, a: String, b: String) -> bool:
	return entry.usable_routes.any(func(r: Dictionary) -> bool: return r.from == a and r.to == b)

static func bidirectional(entry: Dictionary, a: String, b: String) -> bool:
	return route_between(entry, a, b) and route_between(entry, b, a)

func reward_routes(entry: Dictionary, region: Dictionary) -> Array:
	var result: Array = []
	for r: Dictionary in entry.usable_routes:
		var required: Array = r.get("resourceProfile", {}).get("requiredRewards", []).duplicate()
		var overrides: Dictionary = region.get("reward_route_overrides", {}).get(entry.id, {})
		if overrides.has(r.id): required = overrides[r.id]
		for site: Dictionary in entry.compiled_data.get("reward_sites", []):
			if site.id in required:
				result.append({"route_id": r.id, "from": r.from, "to": r.to, "site": site, "evidence": "explicit_adapter" if overrides.has(r.id) else "package_route_reward"})
	return result
