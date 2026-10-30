extends Node2D
## Development-only native physics playback. One actor through the whole map.
const ADAPTER = preload("res://addons/mapgen/package_adapter.gd")
const GENERATOR = preload("res://addons/mapgen/generator.gd")
const VALIDATOR = preload("res://addons/mapgen/layout_validator.gd")
const ASSEMBLER = preload("res://addons/mapgen/assembler.gd")
const SEAL = preload("res://addons/mapgen/gear_seal.gd")
const CAPS = preload("res://module_pack/integration/player_capabilities.gd")
const PLAYER = preload("res://scenes/player/player.tscn")
var adapter = ADAPTER.new()
var assembler = ASSEMBLER.new()
var motor: PlayerMotor
var player: PlayerController
var services: Dictionary
var failures: Array = []
var checks := 0
var observations: Array = []
var trace: Array = []
var label: Label
var layout: Dictionary
var jumps := 0
var shots := 0
var frame := 0
var camera: Camera2D
var recording := false
var reward_origin := Vector2.ZERO
var continuous_start_frame := 0

func expect(condition: bool, name: String, detail: Dictionary = {}) -> void:
	checks += 1; observations.append({"check": name, "passed": condition, "detail": detail})
	if not condition: failures.append(name)

func _ready() -> void:
	var opened: Dictionary = adapter.open("res://module_pack", ADAPTER.read_json("res://configs/package-lock.json"))
	if not opened.ok: push_error(str(opened)); get_tree().quit(2); return
	motor = PLAYER.instantiate(); add_child(motor); player = motor.get_node("Controller")
	player.enable_shot_energy(); CAPS.apply(player, ["move", "jump", "shot_recoil"])
	player.set_physics_process(false)
	var policy := FrameDamagePolicy.new(); var life := DemoLifetime.new(); policy.lifetime = life; add_child(policy)
	policy.register_player_controller(player); policy.register_target(&"player", player.actor_resources.health, true)
	services = {"policy": policy, "lifetime": life, "wallet": RunWallet.new(), "meta": MetaProgression.new(), "region_state": PlainsRegionState.new()}
	player.jump_ability.jumped.connect(func(): jumps += 1)
	player.shoot_ability.shot_fired.connect(func(_dir: Vector2, _id: int): shots += 1)
	camera = Camera2D.new(); motor.add_child(camera); camera.make_current(); camera.zoom = Vector2(0.9, 0.9)
	var layer := CanvasLayer.new(); add_child(layer); label = Label.new(); label.position = Vector2(20, 16); layer.add_child(label)
	label.text = "Native seal component tests | isolated starting states, not continuous play"
	await get_tree().physics_frame
	await _seals()
	await _map()
	_finish()

func _seals() -> void:
	var origin := Vector2(7, -3) * 128
	var bounds := {"x": 0, "y": 0, "w": 384, "h": 512}
	for face: String in ["LEFT", "RIGHT", "TOP", "BOTTOM"]:
		var p := {"id": face, "face": face, "position": [0, 192]}
		var normal := Vector2.LEFT
		match face:
			"RIGHT": p.position = [384, 192]; normal = Vector2.RIGHT
			"TOP": p.position = [192, 0]; normal = Vector2.UP
			"BOTTOM": p.position = [192, 512]; normal = Vector2.DOWN
		var wrapper := Node2D.new(); wrapper.position = origin; add_child(wrapper)
		var seal := SEAL.new(); seal.configure(SEAL.describe(p, bounds), player, services, "component-test"); wrapper.add_child(seal)
		await get_tree().physics_frame
		for mode: String in ["normal", "high_speed", "shot_recoil", "spawn_protected", "anchor_protected"]:
			motor.reset_at(seal.global_position - normal * 70); player.router.clear("component-case")
			if mode in ["spawn_protected", "anchor_protected"]:
				if mode == "anchor_protected": services.lifetime.invalidate_actor()
				services.policy.protect_player()
			var hp_before: float = player.actor_resources.health.current
			var collided := false
			if mode == "high_speed": collided = motor.move_and_collide(normal * 2000) != null
			else:
				if mode == "shot_recoil": motor.start_shot_burst(normal)
				for _n: int in 20:
					if mode != "shot_recoil": motor.request_ability_velocity(normal * 260)
					motor.step(0, 1.0 / 60.0)
					if motor.get_slide_collision_count() > 0: collided = true
					await get_tree().physics_frame
			var signed_distance := (motor.global_position - seal.global_position).dot(normal)
			expect(collided and signed_distance < -12, "seal_blocks/" + face + "/" + mode, {"signed_distance": signed_distance, "real_body_collision": collided, "translation": [7, -3]})
			if "protected" in mode: expect(player.actor_resources.health.current == hp_before, "protection_does_not_remove_collision/" + face + "/" + mode)
		wrapper.queue_free(); await get_tree().physics_frame

func _map() -> void:
	var region := ADAPTER.read_json("res://configs/plains.json")
	# Explicit acceptance configuration, not a hidden name check in the solver.
	region.allowed_module_ids = ["game-route-junction", "idea-spec02-s13-001"]
	region.module_budget = 10; region.target_branches = 2; region.reward_density = 0.1; region.search.wall_clock_ms = 0
	region.search.first_path_min = 0; region.search.first_path_max = 0
	var gen = GENERATOR.new(); var begun: Dictionary = gen.begin(adapter, region, 271028)
	if not begun.ok: expect(false, "acceptance_generate", begun); return
	while not gen.done: gen.step(64)
	expect(gen.result.ok, "real_random_acceptance_layout", gen.result.get("diagnostics", {}))
	if not gen.result.ok: return
	layout = gen.result.layout
	# Goal is an explicit native anchor reached after returning from the reward.
	var first: Dictionary = layout.instances[0]
	layout.goal = gen._anchor(first, "exit_upper_right", "out")
	layout.validation = VALIDATOR.new().validate(layout, gen.modules, region, adapter)
	player.active = false; var hp_before: float = player.actor_resources.health.current
	begun = assembler.begin(adapter, layout, self, player, services)
	expect(begun.ok, "assembly_begin", begun)
	if not begun.ok: return
	var assembly_slices: Array = []
	while not assembler.done:
		var tick := Time.get_ticks_usec(); assembler.step(1, 3000); assembly_slices.append(Time.get_ticks_usec() - tick)
		await get_tree().process_frame
	expect(assembler.result.ok, "real_scenes_bind", assembler.result.get("details", {}))
	if not assembler.result.ok: return
	for item: Dictionary in layout.instances:
		var native: Node2D = assembler.instances[item.instance_id].module
		expect(is_zero_approx(native.module.clock), "no_module_physics_before_all_caps/" + item.instance_id)
		for p: Dictionary in adapter.entries[item.module_id].ports:
			var expected := Vector2(VALIDATOR.world2(item, p)) * 64
			expect(native.world_port(p.id).position.is_equal_approx(expected), "translated_native_port/" + item.instance_id + "/" + p.id)
		expect(item.connected_port_ids.size() + item.sealed_ports.size() == adapter.entries[item.module_id].ports.size(), "every_port_final/" + item.instance_id)
		if item.module_id == "idea-spec02-s13-001": reward_origin = Vector2(item.origin[0], item.origin[1]) * 128
	expect(player.actor_resources.health.current == hp_before, "assembly_no_resource_reset")
	motor.reset_at(Vector2(layout.spawn.position[0], layout.spawn.position[1])); services.policy.protect_player()
	assembler.activate(); player.active = true; player.set_physics_process(true)
	var actor_id := player.get_instance_id(); var session := player.session_id; var epoch: int = services.lifetime.actor_epoch
	var first_tick: int = player._tick
	recording = true; label.text = "CONTINUOUS NATIVE PLAYBACK | same actor, no teleport/refill at seams\nA/D + jump + shot recoil | visit chest, return, reach upper goal"
	continuous_start_frame = Engine.get_process_frames()
	var phase := "approach"; var local_tick := 0; var return_shot := false; var goal_reached := false
	for tick: int in 3000:
		frame = tick; local_tick += 1
		var at := motor.global_position
		match phase:
			"approach":
				player.router.set_move_axis(1)
				if at.x >= reward_origin.x + 80:
					player.router.set_jump_held(&"playback", true); phase = "chest_jump"; local_tick = 0
			"chest_jump":
				player.router.set_move_axis(1 if at.x < reward_origin.x + 336 else 0)
				if local_tick == 10: player.router.request_action(&"shoot_release", Vector2.LEFT)
				if local_tick == 12: player.router.set_jump_held(&"playback", false)
				if services.wallet.balance > 0:
					phase = "return"; local_tick = 0
				if local_tick > 240: break
			"return":
				player.router.set_move_axis(-1)
				if not return_shot and at.x < reward_origin.x + 276 and not motor.is_on_floor():
					player.router.request_action(&"shoot_release", Vector2.RIGHT); return_shot = true
				if at.x <= 480:
					player.router.set_move_axis(0); player.router.set_jump_held(&"playback", true); phase = "goal_jump"; local_tick = 0
			"goal_jump":
				player.router.set_move_axis(1 if local_tick >= 16 and at.x < layout.goal.position[0] else 0)
				if local_tick == 10: player.router.request_action(&"shoot_release", Vector2.DOWN)
				if local_tick == 12: player.router.set_jump_held(&"playback", false)
				if motor.is_on_floor() and at.distance_to(Vector2(layout.goal.position[0], layout.goal.position[1])) < 40:
					goal_reached = true; phase = "complete"; local_tick = 0
			"complete":
				player.router.set_move_axis(0)
				if local_tick > 60: break
		if tick % 3 == 0:
			trace.append({"frame": tick, "phase": phase, "position": [at.x, at.y], "hp": player.actor_resources.health.current, "coins": services.wallet.balance, "grounded": motor.is_on_floor(), "actor_id": actor_id, "session": player.session_id, "epoch": services.lifetime.actor_epoch, "jumps": jumps, "shots": shots})
		label.text = "CONTINUOUS NATIVE PLAYBACK | %s | %.1fs\nHP %s | coins %s | jumps %s | shots %s | goal %s" % [phase, tick / 60.0, player.actor_resources.health.current, services.wallet.balance, jumps, shots, goal_reached]
		await get_tree().physics_frame
	expect(goal_reached, "continuous_reward_return_and_goal", {"last_phase": phase, "last_position": [motor.global_position.x, motor.global_position.y], "frames": frame})
	expect(services.wallet.balance == 4, "actual_native_reward_transaction", {"balance": services.wallet.balance})
	expect(jumps >= 2 and shots >= 3, "accepted_real_jump_and_recoil_actions", {"jumps": jumps, "shots": shots})
	expect(player.get_instance_id() == actor_id and player.session_id == session and services.lifetime.actor_epoch == epoch and player._tick > first_tick, "single_actor_continuous_no_seam_reset")
	expect(player.actor_resources.health.current > 0, "continuous_alive")
	player.active = false; player.set_physics_process(false); recording = false
	layout.validation.continuous_playback = "PASS" if goal_reached and services.wallet.balance == 4 and failures.is_empty() else "FAIL"
	layout.validation.whole_map_physics = "PARTIAL" if layout.validation.continuous_playback == "PASS" else "FAIL"
	layout.validation.physical_scope = "one_fixed_input_playback; lower outward+return, reward L-to-L, root lower-to-upper goal; remaining routes NOT_TESTED"
	layout.validation.seams = "PLAYBACK_PATH_ONLY"; layout.validation.closures = "ISOLATED_CCD_PLUS_PLAYBACK_PATH"
	layout.physics_receipt = {"schema": "mapgen/physical-receipt/1", "checks": checks, "failures": failures.duplicate(), "actor_scene": "res://scenes/player/player.tscn", "teleports_during_continuous_play": 0, "human_playtest": false, "frames": frame, "movie_start_frame": continuous_start_frame, "movie_end_frame": Engine.get_process_frames(), "jumps": jumps, "shots": shots, "coins": services.wallet.balance}
	_write("physical-layout.json", layout)
	var old_count: int = assembler.instances.size(); var before_rebuild_hp: float = player.actor_resources.health.current
	assembler.unload(); await get_tree().process_frame; await get_tree().physics_frame
	expect(get_tree().get_nodes_in_group(&"mapgen_instances").is_empty(), "unload_releases_instances")
	var rebuilt = ASSEMBLER.new(); begun = rebuilt.begin(adapter, JSON.parse_string(JSON.stringify(layout)), self, player, services)
	expect(begun.ok, "saved_layout_rebuild_begin", begun)
	if begun.ok:
		while not rebuilt.done: rebuilt.step(1, 3000); await get_tree().process_frame
		expect(rebuilt.result.ok and rebuilt.instances.size() == old_count, "saved_layout_rebuild_identical_instances")
		expect(player.actor_resources.health.current == before_rebuild_hp, "rebuild_keeps_external_actor_resources")
		rebuilt.unload(); await get_tree().process_frame
	_write("assembly.json", {"slices_usec": assembly_slices, "total_usec": assembler.assembly_usec, "peak_slice_usec": assembler.peak_step_usec})

func _write(name: String, data: Variant) -> void:
	DirAccess.make_dir_recursive_absolute("res://../reports/runtime-v1/physics-final")
	var file := FileAccess.open("res://../reports/runtime-v1/physics-final/" + name, FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "\t"))

func _finish() -> void:
	expect(checks >= 58 and not trace.is_empty(), "all_physical_phases_executed")
	_write("report.json", {"checks": checks, "failures": failures, "observations": observations, "trace": trace, "human_playtest": false, "godot": Engine.get_version_info(), "platform": OS.get_name(), "initial_capabilities": ["move", "jump", "shot_recoil"], "tuning": ADAPTER.read_json("res://config/player_tuning.json")})
	print("MAPGEN_PHYSICS_SUITE ", JSON.stringify({"checks": checks, "failures": failures}))
	get_tree().quit(0 if failures.is_empty() else 4)
