extends RefCounted

const PLAYER := preload("res://scenes/player/player.tscn")
const DT := 1.0 / 60.0
var tree: SceneTree
var check: Callable
var world: Node2D
var module: PlatformingModule
var motor: PlayerMotor
var controller: PlayerController
var _advance_tick: Callable
var previous_body := Rect2()
var safe_trace := true
var continuous_trace := true
var shot_count := 0
var peak_y := INF
var trace_ticks := 0

func run(p_tree: SceneTree, p_check: Callable) -> void:
	tree = p_tree
	check = p_check
	_contracts()
	for mirrored: bool in [false, true]:
		await _fixture("challenge_recoil_climb", 1, 1, mirrored)
		var climbed := await traverse(module, motor, tick, check)
		check.call(climbed, "three 220px rises reach the 660px-higher exit using one jump and one shot per flight")
		check.call(shot_count == 3, "climb fires three real projectiles, with one air shot restored only by each actual landing")
		_finish("recoil climb")
		await _fixture("challenge_long_gap", 1, 2, mirrored)
		var crossed := await traverse(module, motor, tick, check)
		check.call(crossed, "400px clear gap is crossed by held jump and two horizontal released shots")
		check.call(shot_count == 2, "long gap emits exactly two real released-shot events")
		_finish("long gap")
	# Exercise the new authored lower gate near its 145px screening boundary.
	# This is local fixture tuning only; production defaults remain hold=.13.
	for mirrored: bool in [false, true]:
		await _fixture("challenge_recoil_climb", 1, 1, mirrored)
		motor.tuning.jump_hold_duration = 0.122
		var boundary_envelope := MovementCapabilityEnvelope.snapshot(motor.tuning)
		check.call(float(boundary_envelope.held_jump_height) >= 145.0 and float(boundary_envelope.held_jump_height) < 146.0 and module.definition.supports(motor.tuning), "145px gate is exercised by a supported local near-boundary jump fixture")
		var climbed := await traverse(module, motor, tick, check)
		check.call(climbed and shot_count == 3, "near-boundary 145.336px jump crosses all three rises with one real shot per flight")
		_finish("near-boundary recoil climb")
	await _fixture("challenge_recoil_climb", 1, 0)
	_advance_tick = tick
	check.call(await _move_to(170.0), "negative climb reaches its actual takeoff normally")
	controller.router.request_action(&"jump")
	controller.router.set_move_axis(_forward())
	await _advance(90)
	check.call(peak_y > module.world_entry().y - 220.0 and not (motor.is_on_floor() and motor.global_position.y < module.world_entry().y - 200.0), "single held jump without recoil cannot reach the first 220px-higher receiver")
	await _fixture("challenge_long_gap", 1, 0)
	_advance_tick = tick
	check.call(await _move_to(240.0), "negative long gap reaches its actual takeoff normally")
	controller.router.request_action(&"jump")
	controller.router.set_move_axis(_forward())
	await _advance(95)
	check.call(motor.global_position.y > 650.0 and not motor.is_on_floor(), "single held jump without recoil falls below the 400px-gap receiving floor")
	if is_instance_valid(world):
		world.free()

# Reused by the assembled-stage physics proof. The caller owns ticking and full
# world collision monitoring; every action goes through its real InputRouter.
func traverse(p_module: PlatformingModule, p_motor: PlayerMotor, tick_callback: Callable, check_callback: Callable) -> bool:
	if _callback_is_trace_cancelled(tick_callback): return false
	module = p_module
	motor = p_motor
	controller = motor.get_node("Controller") as PlayerController
	_advance_tick = tick_callback
	check = check_callback
	shot_count = 0
	var record_shot := func(direction: Vector2, _id: int) -> void:
		shot_count += 1
		var expected := Vector2.DOWN if module.definition.module_id == &"challenge_recoil_climb" else Vector2.LEFT * _forward()
		check.call(direction.is_equal_approx(expected), "actual projectile direction follows mirrored recoil route handedness")
	controller.shoot_ability.shot_fired.connect(record_shot)
	var traversed := false
	if module.definition.module_id == &"challenge_recoil_climb":
		var _cancel_await_77: bool = await _climb()
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(record_shot):
				controller.shoot_ability.shot_fired.disconnect(record_shot)
			return false
		traversed = _cancel_await_77
	elif module.definition.module_id == &"challenge_long_gap":
		var _cancel_await_79: bool = await _long_gap()
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(record_shot):
				controller.shoot_ability.shot_fired.disconnect(record_shot)
			return false
		traversed = _cancel_await_79
	controller.shoot_ability.shot_fired.disconnect(record_shot)
	return traversed

func _climb() -> bool:
	if is_trace_cancelled(): return false
	for pair: Vector2 in [Vector2(175, 400), Vector2(435, 640), Vector2(715, 940)]:
		var _cancel_await_85: bool = not await _move_to(_world_x(pair.x))
		if is_trace_cancelled(): return false
		if _cancel_await_85:
			return false
		var before_shots := shot_count
		controller.router.set_move_axis(_forward())
		controller.router.request_action(&"jump")
		await _advance(18)
		if is_trace_cancelled(): return false
		controller.router.request_action(&"shoot_release", Vector2.DOWN)
		await _advance()
		if is_trace_cancelled(): return false
		check.call(shot_count == before_shots + 1 and motor.recoil_burst_remaining > 0.0 and controller.action_resources.shot_charges == motor.tuning.max_air_shots - 1, "tower upward movement starts from a real downward released shot and consumes exactly one air charge")
		await _advance(9)
		if is_trace_cancelled(): return false
		controller.router.request_action(&"jump_release")
		var _cancel_await_96: bool = not await _move_to(_world_x(pair.y), 100)
		if is_trace_cancelled(): return false
		if _cancel_await_96:
			return false
		var _cancel_await_98: bool = not await _wait_landing(100)
		if is_trace_cancelled(): return false
		if _cancel_await_98:
			return false
		check.call(controller.action_resources.shot_charges == motor.tuning.max_air_shots and controller.jump_ability.used_jumps == 0, "tower receiver resets action resources only through real floor landing")
	var _cancel_await_101: bool = await _move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_101

func _long_gap() -> bool:
	if is_trace_cancelled(): return false
	var _cancel_await_104: bool = not await _move_to(_world_x(240.0))
	if is_trace_cancelled(): return false
	if _cancel_await_104:
		return false
	controller.router.request_action(&"jump")
	controller.router.set_move_axis(_forward())
	await _advance(18)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"shoot_release", Vector2.LEFT * _forward())
	await _advance()
	if is_trace_cancelled(): return false
	check.call(shot_count == 1 and motor.recoil_burst_remaining > 0.0, "long gap first shot starts a burst toward the mirrored or original receiver")
	await _advance(16)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"shoot_release", Vector2.LEFT * _forward())
	await _advance()
	if is_trace_cancelled(): return false
	check.call(shot_count == 2 and motor.recoil_burst_remaining > 0.0, "long gap second released shot respects the actual configured cooldown")
	await _advance(9)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"jump_release")
	var _cancel_await_118: bool = not await _move_to(_world_x(820.0), 120)
	if is_trace_cancelled(): return false
	if _cancel_await_118:
		return false
	var _cancel_await_120: bool = not await _wait_landing(100)
	if is_trace_cancelled(): return false
	if _cancel_await_120:
		return false
	var _cancel_await_122: bool = await _move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_122

func _advance(count: int = 1) -> void:
	if is_trace_cancelled(): return
	await _advance_tick.call(count)
	if is_trace_cancelled(): return

func _move_to(x: float, limit: int = 300) -> bool:
	if is_trace_cancelled(): return false
	for unused: int in limit:
		controller.router.set_move_axis(clampf((x - motor.global_position.x) / 5.5, -1.0, 1.0))
		await _advance()
		if is_trace_cancelled(): return false
		if absf(x - motor.global_position.x) < 0.5:
			controller.router.set_move_axis(0.0)
			await _advance()
			if is_trace_cancelled(): return false
			return true
	return false

func _wait_landing(limit: int) -> bool:
	if is_trace_cancelled(): return false
	controller.router.set_move_axis(0.0)
	for unused: int in limit:
		if motor.is_on_floor():
			await _advance(3)
			if is_trace_cancelled(): return false
			return true
		await _advance()
		if is_trace_cancelled(): return false
	return false

func _fixture(id: String, jumps: int, shots: int, mirrored: bool = false) -> void:
	if is_instance_valid(world):
		world.free()
	world = Node2D.new()
	tree.root.add_child(world)
	module = load("res://scenes/generation/modules/%s.tscn" % id).instantiate() as PlatformingModule
	if mirrored:
		module.definition = ModuleReflection.reflected_definition(module.definition)
	world.add_child(module)
	motor = PLAYER.instantiate()
	# Initial fixture spawn only; no relocation occurs during a traversal trace.
	motor.position = module.world_entry()
	world.add_child(motor)
	controller = motor.get_node("Controller") as PlayerController
	controller.set_physics_process(false)
	motor.get_node("KeyboardMouseAdapter").set_process_unhandled_input(false)
	motor.tuning.max_jumps = jumps
	motor.tuning.max_air_shots = shots
	controller.action_resources.reset()
	_advance_tick = tick
	safe_trace = true
	continuous_trace = true
	peak_y = motor.global_position.y
	trace_ticks = 0
	previous_body = Rect2(motor.global_position - Vector2(12, 18), Vector2(24, 36))
	await tick(3)

func tick(count: int = 1) -> void:
	for unused: int in count:
		await tree.physics_frame
		controller.physics_tick(DT)
		trace_ticks += 1
		peak_y = minf(peak_y, motor.global_position.y)
		var body := Rect2(motor.global_position - Vector2(12, 18), Vector2(24, 36))
		if body.get_center().distance_to(previous_body.get_center()) > 30.0:
			continuous_trace = false
		for danger: Rect2 in module.world_static_dangers():
			if body.merge(previous_body).intersects(danger, true):
				if safe_trace:
					print("CHALLENGE CONTACT: caps=%d/%d tick=%d player=%s danger=%s" % [motor.tuning.max_jumps, motor.tuning.max_air_shots, trace_ticks, body, danger])
				safe_trace = false
		previous_body = body

func _finish(label: String) -> void:
	check.call(motor.is_on_floor() and motor.global_position.distance_to(module.world_exit()) < 1.0, label + " reaches actual exit with full shape supported")
	check.call(safe_trace, label + " full 24x36 swept body avoids spikes throughout the continuous traversal")
	check.call(continuous_trace, label + " contains no teleports or movement outside real Motor speed limits")
	check.call(module.port_accepts(module.definition.exit_port, motor), label + " satisfies real standing speed and cooldown exit contract")
	check.call(module.scale == Vector2.ONE, label + " reflected geometry uses positive physics-node scale")
	print("CHALLENGE TRACE: id=%s, mirrored=%s, ticks=%d, shots=%d, ascent=%.1f" % [module.definition.module_id, module.definition.mirrored_horizontal, trace_ticks, shot_count, module.world_entry().y - peak_y])

func _contracts() -> void:
	for id: String in ["challenge_recoil_climb", "challenge_long_gap"]:
		var definition := load("res://resources/generation/modules/%s.tres" % id) as PlatformingModuleDefinition
		check.call(definition != null and definition.is_valid(), id + " authored safe docks, anchors and spike bounds validate")
		var required_shots := 1 if id == "challenge_recoil_climb" else 2
		for jumps: int in [0, 1, 3]:
			for shots: int in [0, 1, 2, 3]:
				var tuning := PlayerTuning.load_default()
				tuning.max_jumps = jumps
				tuning.max_air_shots = shots
				check.call(definition.supports(tuning) == (jumps >= 1 and shots >= required_shots), id + " screens configurable %d/%d counts" % [jumps, shots])
		var reduced_jump := PlayerTuning.load_default()
		reduced_jump.jump_hold_duration = 0.10
		check.call(not definition.supports(reduced_jump), id + " rejects insufficient held jump envelope without changing configured jump/shot counts")
		var reduced_burst := PlayerTuning.load_default()
		reduced_burst.shot_burst_duration = 0.01
		check.call(not definition.supports(reduced_burst), id + " rejects insufficient burst distance without changing physics")

func _forward() -> float:
	return -1.0 if module.definition.mirrored_horizontal else 1.0

func _world_x(authored_x: float) -> float:
	var bounds := module.definition.world_bounds
	var local_x := bounds.position.x + bounds.end.x - authored_x if module.definition.mirrored_horizontal else authored_x
	return module.to_global(Vector2(local_x, 0.0)).x

func _callback_is_trace_cancelled(callback: Callable) -> bool:
	if not callback.is_valid(): return false
	var owner := callback.get_object()
	# The standalone fixture owns tick itself; it has no upstream cancellation owner.
	if owner == self: return false
	return is_instance_valid(owner) and owner.has_method("is_trace_cancelled") and bool(owner.call("is_trace_cancelled"))

func is_trace_cancelled() -> bool:
	return _callback_is_trace_cancelled(_advance_tick)
