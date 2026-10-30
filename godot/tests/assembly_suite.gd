extends Node2D
const ADAPTER = preload("res://addons/mapgen/package_adapter.gd")
const ASSEMBLER = preload("res://addons/mapgen/assembler.gd")
const CAPS = preload("res://module_pack/integration/player_capabilities.gd")
const PLAYER = preload("res://scenes/player/player.tscn")
var failures: Array = []
var cases: Array = []

func _ready() -> void:
	var adapter = ADAPTER.new(); var opened: Dictionary = adapter.open("res://module_pack", ADAPTER.read_json("res://configs/package-lock.json"))
	if not opened.ok: push_error(str(opened)); get_tree().quit(2); return
	var motor: PlayerMotor = PLAYER.instantiate(); add_child(motor); var player: PlayerController = motor.get_node("Controller")
	player.active = false; player.enable_shot_energy(); CAPS.apply(player, ["move", "jump", "shot_recoil"])
	var policy := FrameDamagePolicy.new(); var life := DemoLifetime.new(); policy.lifetime = life; add_child(policy)
	policy.register_player_controller(player); policy.register_target(&"player", player.actor_resources.health, true)
	var services := {"policy": policy, "lifetime": life, "wallet": RunWallet.new(), "meta": MetaProgression.new(), "region_state": PlainsRegionState.new()}
	var folder := ProjectSettings.globalize_path("res://").path_join("../reports/runtime-v1/data-08/layouts").simplify_path()
	var names := DirAccess.get_files_at(folder); names.sort()
	for name: String in names:
		var layout := ADAPTER.read_json(folder.path_join(name)); var assembler = ASSEMBLER.new()
		if layout.is_empty(): push_error("missing_test_layout/" + name); get_tree().quit(6); return
		var player_connections := player.shoot_ability.get_signal_connection_list("shot_fired").size()
		var before := Time.get_ticks_usec(); var result: Dictionary = assembler.begin(adapter, layout, self, player, services)
		var validation_usec := Time.get_ticks_usec() - before
		var row := {"name": name, "seed": layout.seed, "validation_usec": validation_usec, "instances": layout.instances.size(), "ok": result.ok}
		var max_call := 0
		if result.ok:
			while not assembler.done:
				before = Time.get_ticks_usec(); assembler.step(1, 8000); max_call = maxi(max_call, Time.get_ticks_usec() - before)
				await get_tree().process_frame
			row.ok = assembler.result.ok; row.assembly_usec = assembler.assembly_usec; row.preload_usec = assembler.preload_usec; row.peak_step_usec = max_call
			if not row.ok: row.reason = assembler.result
		else: row.reason = result
		if not row.ok: failures.append(row)
		assembler.unload(); await get_tree().process_frame; await get_tree().process_frame
		row.live_after_unload = get_tree().get_nodes_in_group(&"mapgen_instances").size()
		row.objects_after_unload = Performance.get_monitor(Performance.OBJECT_COUNT)
		row.nodes_after_unload = Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
		row.connections_before = player_connections; row.connections_after = player.shoot_ability.get_signal_connection_list("shot_fired").size()
		if row.live_after_unload != 0 or row.connections_after != player_connections: failures.append({"case": name, "reason": "unload_leak", "row": row})
		cases.append(row)
	var fallback := ADAPTER.read_json("res://configs/fallback.json")
	var pending = ASSEMBLER.new(); var begun: Dictionary = pending.begin(adapter, fallback, self, player, services)
	if not begun.ok: failures.append({"reason": "cancel_fixture_begin", "result": begun})
	else:
		while pending.cursor == 0 and not pending.done: pending.step(1, 8000); await get_tree().process_frame
		var duplicate = ASSEMBLER.new(); var duplicate_result: Dictionary = duplicate.begin(adapter, fallback, self, player, services)
		if duplicate_result.get("ok", true) or duplicate_result.get("reason") != "duplicate_live_instance_id": failures.append({"reason": "duplicate_live_id_not_rejected", "result": duplicate_result})
		pending.cancel(); pending.step(); await get_tree().process_frame; await get_tree().process_frame
		if pending.result.get("reason") != "cancelled" or not get_tree().get_nodes_in_group(&"mapgen_instances").is_empty(): failures.append({"reason": "assembly_cancel_cleanup"})
	var before_gravity: float = motor.tuning.gravity; motor.tuning.gravity += 1
	var mismatch = ASSEMBLER.new(); var mismatch_result: Dictionary = mismatch.begin(adapter, fallback, self, player, services)
	if mismatch_result.get("ok", true) or mismatch_result.get("reason") != "existing_actor_tuning_mismatch": failures.append({"reason": "actor_tuning_mismatch_not_rejected", "result": mismatch_result})
	motor.tuning.gravity = before_gravity
	if cases.is_empty(): failures.append({"reason": "no_cases_executed"})
	var file := FileAccess.open("res://../reports/runtime-v1/assembly-suite.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"cases": cases, "failures": failures, "godot": Engine.get_version_info().string, "platform": OS.get_name(), "scope": "instantiation/translation/seal reconstruction/unload; no player traversal of these random maps"}, "\t"))
	print("MAPGEN_ASSEMBLY_SUITE ", JSON.stringify({"cases": cases.size(), "failures": failures.size()}))
	get_tree().quit(0 if failures.is_empty() else 5)
