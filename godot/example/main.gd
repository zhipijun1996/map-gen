extends Node2D
const ADAPTER = preload("res://addons/mapgen/package_adapter.gd")
const GENERATOR = preload("res://addons/mapgen/generator.gd")
const ASSEMBLER = preload("res://addons/mapgen/assembler.gd")
const CAPS = preload("res://module_pack/integration/player_capabilities.gd")
const PLAYER = preload("res://scenes/player/player.tscn")
var adapter = ADAPTER.new()
var generator = GENERATOR.new()
var assembler = ASSEMBLER.new()
var player: PlayerController
var motor: PlayerMotor
var services: Dictionary
var region: Dictionary
var layout: Dictionary = {}
var phase := "idle"
var seed_field: SpinBox
var size_field: SpinBox
var branch_field: SpinBox
var density_field: SpinBox
var status: Label
var camera: Camera2D
var at_goal := false
var assembly_result: Dictionary
var smoke := false
var smoke_started := 0

func _ready() -> void:
	get_tree().auto_accept_quit = false
	region = ADAPTER.read_json("res://configs/plains.json")
	var opened: Dictionary = adapter.open("res://module_pack", ADAPTER.read_json("res://configs/package-lock.json"))
	if not opened.ok: push_error(str(opened)); get_tree().quit(2); return
	motor = PLAYER.instantiate(); add_child(motor); player = motor.get_node("Controller")
	player.active = false; player.enable_shot_energy(); CAPS.apply(player, region.abilities)
	var policy := FrameDamagePolicy.new(); var life := DemoLifetime.new(); policy.lifetime = life; add_child(policy)
	policy.register_player_controller(player); policy.register_target(&"player", player.actor_resources.health, true)
	services = {"policy": policy, "lifetime": life, "wallet": RunWallet.new(), "meta": MetaProgression.new(), "region_state": PlainsRegionState.new()}
	player.interact_requested.connect(_interact)
	camera = Camera2D.new(); motor.add_child(camera); camera.make_current()
	_hud()
	var args := OS.get_cmdline_user_args(); var initial_seed := 271028
	for i: int in args.size():
		if args[i] == "--seed" and i + 1 < args.size(): initial_seed = int(args[i + 1])
		if args[i] == "--smoke": smoke = true; smoke_started = Time.get_ticks_usec()
	seed_field.value = initial_seed
	generate()

func _hud() -> void:
	var layer := CanvasLayer.new(); add_child(layer)
	var panel := PanelContainer.new(); panel.position = Vector2(12, 12); layer.add_child(panel)
	var column := VBoxContainer.new(); panel.add_child(column)
	var title := Label.new(); title.text = "WINDCHIME PLAINS | REAL MODULES 1.0.0"; column.add_child(title)
	var row := HBoxContainer.new(); column.add_child(row)
	seed_field = _number(row, "Seed", 1, 2147483646, 271028)
	size_field = _number(row, "Max modules", 5, 128, region.module_budget)
	branch_field = _number(row, "Main splits", 1, 12, region.target_branches)
	density_field = _number(row, "Reward density", 0, 0.5, region.reward_density); density_field.step = 0.01; density_field.value = region.reward_density
	var go := Button.new(); go.text = "Generate"; go.pressed.connect(generate); row.add_child(go)
	var cancel_button := Button.new(); cancel_button.text = "Cancel"; cancel_button.pressed.connect(cancel); row.add_child(cancel_button)
	status = Label.new(); column.add_child(status)
	var hints := Label.new(); hints.text = "A/D move | Space jump | release mouse to shoot | S drop | E interact | M overview | F5 save | F9 rebuild"; column.add_child(hints)

func _number(parent: Node, text: String, minimum: float, maximum: float, value: float) -> SpinBox:
	var label := Label.new(); label.text = text; parent.add_child(label)
	var field := SpinBox.new(); field.min_value = minimum; field.max_value = maximum; field.value = value; field.custom_minimum_size.x = 100; parent.add_child(field); return field

func generate() -> void:
	if phase in ["solving", "assembling"]: return
	player.active = false; assembler.unload()
	if is_instance_valid(assembler.staging): await assembler.staging.tree_exited
	region.module_budget = int(size_field.value); region.target_branches = int(branch_field.value); region.reward_density = density_field.value
	var fallback := ADAPTER.read_json("res://configs/fallback.json")
	generator = GENERATOR.new(); var begun: Dictionary = generator.begin(adapter, region, int(seed_field.value), fallback)
	if not begun.ok: phase = "error"; status.text = str(begun); return
	phase = "solving"; status.text = "Solving ..."

func cancel() -> void:
	generator.cancel(); assembler.cancel()

func _process(_delta: float) -> void:
	if smoke and (phase == "error" or Time.get_ticks_usec() - smoke_started > 45000000):
		print("MAPGEN_EXAMPLE_SMOKE ", JSON.stringify({"ok": false, "phase": phase, "status": status.text})); get_tree().quit(4); return
	if phase == "solving":
		var before := Time.get_ticks_usec()
		var progress: Dictionary = {}
		while Time.get_ticks_usec() - before < 2500:
			progress = generator.step(1)
			if progress.done: break
		status.text = "Solving | steps %s | cycles %s" % [generator.steps, generator.cycle_count]
		if progress.get("done", false):
			if not progress.result.ok: status.text = JSON.stringify(progress.result); phase = "error"; return
			layout = progress.result.layout; assembler = ASSEMBLER.new()
			var begun: Dictionary = assembler.begin(adapter, layout, self, player, services)
			if not begun.ok: status.text = str(begun); phase = "error"; return
			phase = "assembling"
	elif phase == "assembling":
		var progress: Dictionary = assembler.step(region.assembly.nodes_per_step, region.assembly.time_budget_usec)
		status.text = "Assembling %s / %s" % [assembler.cursor, layout.instances.size()]
		if progress.done:
			if not progress.result.ok: status.text = str(progress.result); phase = "error"; return
			assembly_result = progress.result
			motor.global_position = Vector2(layout.spawn.position[0], layout.spawn.position[1]); motor.reset_motion()
			assembler.activate(); player.active = true; phase = "playing"; at_goal = false; queue_redraw()
			if smoke:
				print("MAPGEN_EXAMPLE_SMOKE ", JSON.stringify({"ok": true, "instances": layout.instances.size(), "seed": layout.seed, "rewards": layout.rewards.size(), "fallback": generator.result.fallback, "player_id": player.get_instance_id(), "seal_count": layout.instances.reduce(func(n: int, i: Dictionary) -> int: return n + i.sealed_ports.size(), 0)}))
				_close_example()
	elif phase == "playing":
		var goal := Vector2(layout.goal.position[0], layout.goal.position[1])
		if motor.global_position.distance_to(goal) < 36: at_goal = true
		status.text = "%d modules | %d splits | %d rewards | HP %s | coins %s | goal %s\nStatic routes PASS; map physics: %s" % [layout.instances.size(), layout.cycles.size(), layout.rewards.size(), player.actor_resources.health.current, services.wallet.balance, "REACHED" if at_goal else "explore", layout.validation.whole_map_physics]

func _interact() -> void:
	for row: Dictionary in assembler.instances.values():
		var instance: Node2D = row.module
		if instance.has_method("request_native_pickup_interaction"): instance.request_native_pickup_interaction()
		if instance.has_method("request_native_region_interaction"): instance.request_native_region_interaction()

func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo: return
	if event.physical_keycode == KEY_E: _interact()
	if event.physical_keycode == KEY_M: camera.zoom = Vector2(0.16, 0.16) if camera.zoom.x > 0.5 else Vector2.ONE
	if event.physical_keycode == KEY_F5 and phase == "playing": assembler.save_layout("user://map.json")
	if event.physical_keycode == KEY_F9 and phase == "playing": _rebuild()

func _rebuild() -> void:
	player.active = false; assembler.unload(); await get_tree().process_frame
	layout = ADAPTER.read_json("user://map.json")
	assembler = ASSEMBLER.new(); var begun: Dictionary = assembler.begin(adapter, layout, self, player, services)
	if begun.ok: phase = "assembling"
	else: status.text = str(begun); phase = "error"

func _draw() -> void:
	if layout.is_empty(): return
	for name: String in ["spawn", "goal"]:
		var at: Array = layout[name].position
		draw_circle(Vector2(at[0], at[1] - 24), 14, Color("5ee4ac") if name == "spawn" else Color("ffc665"), false, 3)

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST: _close_example()

func _close_example() -> void:
	if phase == "closing": return
	phase = "closing"; player.active = false
	generator.cancel(); assembler.cancel(); assembler.unload()
	# Godot cannot cancel an in-flight resource request. Drain its bounded
	# local loads without creating scenes before releasing the script context.
	var pending: Array = assembler.loading_paths.duplicate()
	while not pending.is_empty():
		for path: String in pending.duplicate():
			var state := ResourceLoader.load_threaded_get_status(path)
			if state == ResourceLoader.THREAD_LOAD_LOADED:
				ResourceLoader.load_threaded_get(path); pending.erase(path)
			elif state in [ResourceLoader.THREAD_LOAD_FAILED, ResourceLoader.THREAD_LOAD_INVALID_RESOURCE]: pending.erase(path)
		await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	get_tree().quit()
