extends SceneTree
const ADAPTER = preload("res://addons/mapgen/package_adapter.gd")
const GENERATOR = preload("res://addons/mapgen/generator.gd")
const VALIDATOR = preload("res://addons/mapgen/layout_validator.gd")
const SEAL = preload("res://addons/mapgen/gear_seal.gd")
var failures: Array = []
var checks := 0

func expect(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)

func solve(adapter, region: Dictionary, seed_value: int, batch := 128) -> Dictionary:
	var generator = GENERATOR.new()
	var begin: Dictionary = generator.begin(adapter, region, seed_value)
	if not begin.ok: return begin
	while not generator.done: generator.step(batch)
	return generator.result

func signature(layout: Dictionary) -> String:
	return JSON.stringify({"instances": layout.instances, "connections": layout.connections, "rewards": layout.rewards, "spawn": layout.spawn, "goal": layout.goal}).sha256_text()

func _initialize() -> void:
	var adapter = ADAPTER.new(); var before := Time.get_ticks_usec()
	var opened: Dictionary = adapter.open("res://module_pack", ADAPTER.read_json("res://configs/package-lock.json"))
	var load_usec := Time.get_ticks_usec() - before
	expect(opened.ok, "immutable_package_and_host_hashes")
	if not opened.ok: print(opened); quit(2); return
	var region := ADAPTER.read_json("res://configs/plains.json")
	region.search.wall_clock_ms = 0
	var pool: Dictionary = adapter.pool(region)
	expect(pool.modules.size() > 80, "real_pool_not_mock_library")
	var more := region.duplicate(true); more.abilities.append("grapple")
	expect(adapter.pool(more).modules.size() < pool.modules.size(), "extra_ability_not_assumed_monotonic")
	var fixture_profile := region.duplicate(true); fixture_profile.native_profile_id = "original-fixture-1j2s"
	expect(adapter.pool(fixture_profile).modules.size() == 1, "special_tuning_cannot_inherit_default_profile_witnesses")
	var empty_pool := region.duplicate(true); empty_pool.allowed_module_ids = []
	expect(adapter.pool(empty_pool).modules.is_empty(), "explicit_empty_pool_does_not_reuse_unrestricted_cache")
	for entry: Dictionary in pool.modules.values():
		for r: Dictionary in entry.usable_routes:
			expect(r.validation.get("testNeighborFixtures", []).is_empty(), "external_neighbor_not_silently_accepted")
	var one_way: Dictionary = pool.modules["game-plains-micro-landing"]
	expect(not ADAPTER.route_between(one_way, "exit", "entry"), "no_invented_reverse_routes")
	var dirtest := one_way.duplicate(true); dirtest.usable_routes = []
	expect(ADAPTER.active_routes(dirtest, ["entry", "exit"]).is_empty(), "route_graph_respects_declared_direction")
	var hub: Dictionary = pool.modules["game-route-junction"]
	var partial: Dictionary = VALIDATOR.new().configuration(hub, ["entry_right", "exit_upper_right"], region)
	expect(partial.ok and partial.sealed_ports.size() == 2 and partial.routes.size() == 2, "real_four_port_subset_caps_disable_sealed_routes")
	for face: String in ["LEFT", "RIGHT", "TOP", "BOTTOM"]:
		var p := {"id": "p", "position": [128, 192], "face": face}
		match face:
			"LEFT": p.position = [0, 192]
			"RIGHT": p.position = [384, 192]
			"TOP": p.position = [192, 0]
			"BOTTOM": p.position = [192, 512]
		var r: Rect2 = SEAL.rectangle(p, {"x": 0, "y": 0, "w": 384, "h": 512})
		expect(Rect2(0, 0, 384, 512).encloses(r), "seal_inside/" + face)
	var results: Array = []; var first: Dictionary = {}
	for size: int in [10, 18, 30]:
		for seed_value: int in range(271028, 271036):
			var conf := region.duplicate(true); conf.module_budget = size; conf.target_branches = 1 if size == 10 else (2 if size == 18 else 3)
			var generated := solve(adapter, conf, seed_value)
			var row := {"seed": seed_value, "size": size, "branches": conf.target_branches, "ok": generated.ok, "reason": generated.get("reason"), "fallback": generated.get("fallback", false), "diagnostics": generated.get("diagnostics", {})}
			if generated.ok:
				row.instances = generated.layout.instances.size(); row.reward_count = generated.layout.rewards.size(); row.signature = signature(generated.layout)
				var dir := "res://../reports/runtime-v1/data-08/layouts"
				DirAccess.make_dir_recursive_absolute(dir)
				var f := FileAccess.open(dir.path_join("size-%d-seed-%d.json" % [size, seed_value]), FileAccess.WRITE)
				f.store_string(JSON.stringify(generated.layout, "\t"))
				if first.is_empty(): first = {"layout": generated.layout, "region": conf}
			results.append(row)
	if not first.is_empty():
		var repeated := solve(adapter, first.region, first.layout.seed, 1)
		expect(repeated.ok and signature(repeated.layout) == signature(first.layout), "determinism_independent_of_step_batch")
		var saved: Dictionary = JSON.parse_string(JSON.stringify(first.layout))
		var checked: Dictionary = VALIDATOR.new().validate(saved, pool.modules, first.region, adapter)
		expect(checked.ok, "json_save_roundtrip")
		var bad := saved.duplicate(true); bad.instances[1].origin = bad.instances[0].origin
		expect(not VALIDATOR.new().validate(bad, pool.modules, first.region, adapter).ok, "overlap_rejected")
		bad = saved.duplicate(true); bad.instances[0].sealed_ports = []
		expect(not VALIDATOR.new().validate(bad, pool.modules, first.region, adapter).ok, "missing_seal_rejected")
		bad = saved.duplicate(true); bad.instances[0].mirror_x = true
		expect(not VALIDATOR.new().validate(bad, pool.modules, first.region, adapter).ok, "unsupported_mirror_rejected")
		bad = saved.duplicate(true); bad.instances[0].content_version = "changed"
		expect(not VALIDATOR.new().validate(bad, pool.modules, first.region, adapter).ok, "content_version_rejected")
	var tiny := region.duplicate(true); tiny.search.max_steps = 1; tiny.fallback.enabled = false
	var failed := solve(adapter, tiny, 1)
	expect(not failed.ok and failed.reason == "search_step_budget", "bounded_search_no_unverified_fallback")
	var with_fallback := tiny.duplicate(true); with_fallback.fallback.enabled = true
	var recovered := solve(adapter, with_fallback, 1)
	expect(recovered.ok and recovered.fallback, "compatible_physics_checked_fallback")
	var named := with_fallback.duplicate(true); named.instance_namespace = "run-42/region-7"
	var named_result := solve(adapter, named, 1)
	expect(named_result.ok and named_result.fallback and named_result.layout.instances[0].instance_id.begins_with("run-42/region-7/"), "fallback_rebases_stable_id_namespace")
	expect(VALIDATOR.new().validate(named_result.layout, pool.modules, named, adapter).ok, "rebased_graph_and_rewards_remain_consistent")
	var mismatch := with_fallback.duplicate(true); mismatch.abilities.append("grapple")
	expect(not solve(adapter, mismatch, 1).ok, "fallback_cannot_cross_ability_profiles")
	var cancelled = GENERATOR.new(); cancelled.begin(adapter, region, 1); cancelled.cancel(); cancelled.step()
	expect(cancelled.result.reason == "cancelled", "cancel_is_terminal")
	var report := {"schema": "mapgen/runtime-data-tests/1", "checks": checks, "failures": failures, "package_load_usec": load_usec, "environment": {"os": OS.get_name(), "cpu": OS.get_processor_name(), "godot": Engine.get_version_info().string, "physics_hz": Engine.physics_ticks_per_second}, "pool_size": pool.modules.size(), "pool_rejections": pool.rejections, "seeds": results}
	DirAccess.make_dir_recursive_absolute("res://../reports/runtime-v1/data-08")
	var f := FileAccess.open("res://../reports/runtime-v1/data-08/data-suite.json", FileAccess.WRITE); f.store_string(JSON.stringify(report, "\t"))
	print("MAPGEN_DATA_SUITE ", JSON.stringify({"checks": checks, "failures": failures, "maps": results.filter(func(r: Dictionary) -> bool: return r.ok).size(), "trials": results.size()}))
	quit(0 if failures.is_empty() else 3)
