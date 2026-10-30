extends RefCounted
## Main-thread, bounded scene assembly. Does not initialize or refill the actor.
const VALIDATOR = preload("layout_validator.gd")
const SEAL = preload("gear_seal.gd")
var adapter
var layout: Dictionary
var modules: Dictionary
var player: PlayerController
var services: Dictionary
var host: Node2D
var staging: Node2D
var instances: Dictionary = {}
var cursor := 0
var cancelled := false
var done := false
var result: Dictionary = {}
var assembly_usec := 0
var peak_step_usec := 0
var preloaded: Dictionary = {}
var loading_paths: Array = []
var preload_started := 0
var preload_usec := 0
var suspended_modes: Dictionary = {}

func begin(reader, data: Dictionary, parent: Node2D, existing_player: PlayerController, host_services: Dictionary) -> Dictionary:
	adapter = reader; layout = data.duplicate(true); host = parent; player = existing_player; services = host_services
	if not is_instance_valid(player) or not services.has_all(["policy", "lifetime", "wallet", "meta", "region_state"]): return _fail("host_services_required")
	if host.global_transform.x != Vector2.RIGHT or host.global_transform.y != Vector2.DOWN: return _fail("parent_must_be_translation_only")
	if layout.get("schema") != "mapgen/layout/1" or layout.get("lock") != adapter.lock: return _fail("saved_layout_lock_mismatch")
	modules = adapter.pool(layout.region).modules
	var check: Dictionary = VALIDATOR.new().validate(layout, modules, layout.region, adapter)
	if not check.ok: return _fail("invalid_layout", check)
	# The host freezes its existing actor while staging; it stays frozen until
	# the host explicitly activates the returned map. No partial physics ticks.
	if player.active: return _fail("host_must_suspend_actor_before_assembly")
	var profile: Dictionary = layout.region.get("player_profile", {})
	if layout.region.get("native_profile_id") == null and not profile.get("tuning_overrides", {}).is_empty(): return _fail("default_profile_tuning_override_not_witnessed")
	if layout.region.get("native_profile_id") == null and profile.get("weapon", "res://resources/weapons/pulse_gun.tres") != "res://resources/weapons/pulse_gun.tres": return _fail("alternate_weapon_profile_not_witnessed")
	if not profile.get("actor_body_pixels") is Array or profile.actor_body_pixels.size() != 2 or Vector2(profile.actor_body_pixels[0], profile.actor_body_pixels[1]) != Vector2(24, 36): return _fail("actor_body_profile_not_witnessed")
	if profile.is_empty() or player.motor.tuning.max_jumps != profile.max_jumps or player.motor.tuning.max_air_shots != profile.max_air_shots:
		return _fail("initial_player_tuning_not_witnessed")
	if FileAccess.get_sha256("res://config/player_tuning.json") != profile.tuning_sha256: return _fail("player_tuning_source_mismatch")
	var expected_tuning: Dictionary = preload("package_adapter.gd").read_json("res://config/player_tuning.json")
	expected_tuning.merge(profile.get("tuning_overrides", {}), true)
	for key: String in expected_tuning:
		if key == "physics_hz": continue
		if player.motor.tuning.get(key) != expected_tuning[key]: return _fail("existing_actor_tuning_mismatch", {"field": key})
	var body := player.motor.get_node_or_null("CollisionShape2D") as CollisionShape2D
	if body == null or not body.shape is RectangleShape2D or body.shape.size != Vector2(profile.actor_body_pixels[0], profile.actor_body_pixels[1]): return _fail("actor_body_not_witnessed")
	if player.shoot_ability.weapon.resource_path != profile.get("weapon", "res://resources/weapons/pulse_gun.tres"): return _fail("initial_weapon_not_witnessed")
	var actor_caps := preload("res://module_pack/integration/player_capabilities.gd").snapshot(player, layout.region.abilities)
	if actor_caps.jump_enabled != ("jump" in layout.region.abilities) or actor_caps.shoot_enabled != ("shot_recoil" in layout.region.abilities) or actor_caps.double_enabled != ("double_jump" in layout.region.abilities) or actor_caps.grapple_enabled != ("grapple" in layout.region.abilities) or actor_caps.wall_enabled != ("wall_climb" in layout.region.abilities):
		return _fail("existing_actor_ability_snapshot_mismatch")
	for node: Node in host.get_tree().get_nodes_in_group(&"mapgen_instances"):
		if node.get_meta("instance_id", "") in layout.instances.map(func(i: Dictionary) -> String: return i.instance_id): return _fail("duplicate_live_instance_id")
	staging = Node2D.new(); staging.name = "GeneratedMap"
	staging.process_mode = Node.PROCESS_MODE_DISABLED; staging.visible = false; host.add_child(staging)
	cursor = 0; cancelled = false; done = false; result = {}; instances = {}; suspended_modes = {}; assembly_usec = 0; peak_step_usec = 0
	preloaded = {}; loading_paths = []; preload_started = Time.get_ticks_usec(); preload_usec = 0
	for item: Dictionary in layout.instances:
		var path: String = adapter.root.path_join(modules[item.module_id].scene)
		if path in loading_paths: continue
		loading_paths.append(path)
		var error := ResourceLoader.load_threaded_request(path, "PackedScene", true)
		if error != OK: return _fail("async_scene_request_failed", {"path": path, "error": error})
	# Prime only explicit runtime dependencies. Loading every .gd in a host
	# lock also loads unrelated test/tool scripts and is not a safe warmup API.
	var host_lock: Dictionary = preload("package_adapter.gd").read_json(adapter.root.path_join(adapter.lock.get("host_dependency", adapter.manifest.hostDependency)))
	for path: String in layout.region.get("prewarm_resources", []):
		if not path.begins_with("res://") or not host_lock.files.has(path.trim_prefix("res://")): return _fail("prewarm_resource_not_in_host_lock", {"path": path})
		if path in loading_paths: continue
		loading_paths.append(path)
		var error := ResourceLoader.load_threaded_request(path, "", true)
		if error != OK: return _fail("async_host_script_request_failed", {"path": path, "error": error})
	return {"ok": true}

func cancel() -> void:
	cancelled = true

func step(max_nodes := 1, time_budget_usec := 3000) -> Dictionary:
	if done: return {"done": true, "result": result}
	if cancelled: _fail("cancelled"); return {"done": true, "result": result}
	if not loading_paths.is_empty():
		if Time.get_ticks_usec() - preload_started > 30000000:
			_fail("resource_preload_timeout"); return {"done": true, "result": result}
		for path: String in loading_paths.duplicate():
			var status := ResourceLoader.load_threaded_get_status(path)
			if status in [ResourceLoader.THREAD_LOAD_FAILED, ResourceLoader.THREAD_LOAD_INVALID_RESOURCE]:
				_fail("async_scene_load_failed", {"path": path}); return {"done": true, "result": result}
			if status == ResourceLoader.THREAD_LOAD_LOADED:
				preloaded[path] = ResourceLoader.load_threaded_get(path); loading_paths.erase(path)
		preload_usec = Time.get_ticks_usec() - preload_started
		return {"done": false, "assembled": cursor, "phase": "preloading"}
	var before := Time.get_ticks_usec(); var count := 0
	while cursor < layout.instances.size() and count < clampi(max_nodes, 1, 16):
		if cancelled: _fail("cancelled"); break
		if count > 0 and Time.get_ticks_usec() - before >= time_budget_usec: break
		var item: Dictionary = layout.instances[cursor]; var entry: Dictionary = modules[item.module_id]
		var packed: PackedScene = preloaded.get(adapter.root.path_join(entry.scene))
		if packed == null: _fail("scene_load_failed"); break
		var wrapper := Node2D.new(); wrapper.name = "Instance%03d" % cursor
		wrapper.set_meta("instance_id", item.instance_id); wrapper.add_to_group(&"mapgen_instances")
		wrapper.position = staging.to_local(Vector2(item.origin[0], item.origin[1]) * 128)
		staging.add_child(wrapper)
		var instance: Node2D = packed.instantiate()
		instance.position = Vector2(entry.sceneOriginOffsetPixels[0], entry.sceneOriginOffsetPixels[1]); wrapper.add_child(instance)
		# This adapter directly binds immutable module content, then applies its
		# own declared overlay. It never calls original-all-ports with false data.
		var args: Array = [player, services.policy, services.lifetime, services.wallet, null, item.instance_id]
		for method: Dictionary in instance.get_method_list():
			if method.name == "bind_player" and method.args.size() > 6: args.append(services.meta); args.append(services.region_state); break
		var bound: Dictionary = instance.callv("bind_player", args)
		if not bound.get("ok", false): _fail("module_bind_failed", {"instance_id": item.instance_id, "result": bound}); break
		for spec: Dictionary in item.sealed_ports:
			var seal := SEAL.new(); seal.name = "Seal_" + spec.port_id
			seal.configure(spec, player, services, item.instance_id); wrapper.add_child(seal)
		_suspend_tree(wrapper)
		instances[item.instance_id] = {"wrapper": wrapper, "module": instance, "seals": item.sealed_ports.duplicate(true)}
		cursor += 1; count += 1
	var elapsed := Time.get_ticks_usec() - before
	assembly_usec += elapsed; peak_step_usec = maxi(peak_step_usec, elapsed)
	if not done and cursor == layout.instances.size():
		done = true; result = {"ok": true, "map": staging, "instances": instances, "assembly_usec": assembly_usec, "preload_usec": preload_usec, "peak_step_usec": peak_step_usec, "player_created": false, "resources_reset": false}
	return {"done": done, "assembled": cursor, "result": result if done else {}}

func activate() -> Dictionary:
	if not done or not result.get("ok", false): return {"ok": false, "reason": "assembly_not_complete"}
	for node: Node in suspended_modes:
		if is_instance_valid(node): node.process_mode = suspended_modes[node]
	suspended_modes.clear()
	staging.process_mode = Node.PROCESS_MODE_INHERIT; staging.visible = true
	return {"ok": true}

func _suspend_tree(node: Node) -> void:
	# Native consumers explicitly set PAUSABLE in _ready; disabling only their
	# parent does not suspend them. Record/disable every new node before a tick.
	suspended_modes[node] = node.process_mode
	node.process_mode = Node.PROCESS_MODE_DISABLED
	for child: Node in node.get_children(): _suspend_tree(child)

func unload() -> void:
	for id: String in instances:
		var prefix := "module/" + id.uri_encode() + "/"
		for key: Variant in services.policy._targets.keys():
			if str(key).begins_with(prefix): services.policy._targets.erase(key)
		services.policy._queue = services.policy._queue.filter(func(r: DamageRequest) -> bool: return not str(r.source_id).begins_with(prefix) and not str(r.target_id).begins_with(prefix))
		for key: Variant in services.policy._seen.keys():
			if str(key).begins_with(prefix) or str(key).contains("/" + prefix): services.policy._seen.erase(key)
	instances.clear()
	preloaded.clear()
	suspended_modes.clear()
	if is_instance_valid(staging): staging.queue_free()

func save_layout(path: String) -> Error:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: return FileAccess.get_open_error()
	file.store_string(JSON.stringify(layout, "\t")); return OK

func _fail(reason: String, details: Dictionary = {}) -> Dictionary:
	done = true; result = {"ok": false, "reason": reason, "details": details}
	unload(); return result
