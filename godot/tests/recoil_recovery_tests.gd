extends "res://tests/challenge_recoil_tests.gd"

# A normal late takeoff needs no shot; an early takeoff undershoots the bridge.
# The same early input can be rescued with one backward shot, with a spare left.
func run(p_tree: SceneTree, p_check: Callable) -> void:
	tree = p_tree
	check = p_check
	var definition := load("res://resources/generation/modules/plains_recovery_bridge.tres") as PlatformingModuleDefinition
	check.call(definition.is_valid() and definition.supports(PlayerTuning.load_default()), "recovery bridge validates against production one-jump baseline")
	for mirrored: bool in [false, true]:
		await _fixture("plains_recovery_bridge", 1, 2, mirrored)
		check.call(await traverse(module, motor, tick, check), "ordinary route reaches exit by real movement")
		_finish("ordinary recovery bridge")
		await _fixture("plains_recovery_bridge", 1, 2, mirrored)
		check.call(await _move_to(_world_x(190.0)), "undershoot starts at same supported early takeoff")
		controller.router.request_action(&"jump")
		controller.router.set_move_axis(_forward())
		await tick(50)
		check.call(not motor.is_on_floor() and motor.global_position.y > 650.0, "unrescued early jump falls below receiver; full charges alone do not help")
		for rescue_tick: int in [18, 22, 26]:
			await _fixture("plains_recovery_bridge", 1, 2, mirrored)
			check.call(await _move_to(_world_x(190.0)), "recovery repeats same early takeoff")
			controller.router.request_action(&"jump")
			controller.router.set_move_axis(_forward())
			await tick(rescue_tick)
			controller.router.request_action(&"shoot_release", Vector2.LEFT * _forward())
			await tick()
			var projectiles := controller.shoot_ability.get_projectiles()
			check.call(projectiles.size() == 1 and projectiles[0].direction.is_equal_approx(Vector2.LEFT * _forward()) and projectiles[0].radius > 0.0 and projectiles[0].damage > 0.0, "recovery emits real damaging projectile opposite travel")
			shot_count = controller.shoot_ability._shot_serial
			check.call(shot_count == 1, "exactly one shot emitted during rescue")
			check.call(motor.recoil_burst_remaining > 0.0 and controller.action_resources.shot_charges == 1, "rescue uses exactly one charge and leaves one spare")
			check.call(await _move_to(_world_x(590.0), 100), "directional rescue reaches broad receiver")
			check.call(await _wait_landing(60), "rescued actor lands on real collision")
			check.call(await _move_to(module.world_exit().x), "rescued actor walks to exit")
			_finish("recovery timing %d" % rescue_tick)
	if is_instance_valid(world):
		world.free()

# Shared by assembled-stage proof; caller retains world ticking / sweep checks.
func traverse(p_module: PlatformingModule, p_motor: PlayerMotor, tick_callback: Callable, check_callback: Callable) -> bool:
	if _callback_is_trace_cancelled(tick_callback): return false
	module = p_module
	motor = p_motor
	controller = motor.get_node("Controller") as PlayerController
	_advance_tick = tick_callback
	check = check_callback
	shot_count = 0
	var shots_before := controller.shoot_ability._shot_serial
	var direction := signf(module.world_exit().x - module.world_entry().x)
	var platforms: Array[Rect2] = module.definition.platforms.duplicate()
	platforms.sort_custom(func(a: Rect2, b: Rect2): return a.position.x * direction < b.position.x * direction)
	var takeoff := platforms[0].end.x - 20.0 if direction > 0.0 else platforms[0].position.x + 20.0
	var _cancel_await_53: bool = not await _move_to(module.to_global(Vector2(takeoff, 0)).x)
	if is_trace_cancelled(): return false
	if _cancel_await_53:
		return false
	controller.router.request_action(&"jump")
	controller.router.set_move_axis(direction)
	await _advance(43)
	if is_trace_cancelled(): return false
	check.call(motor.is_on_floor(), "late one-jump crosses recovery bridge without recoil")
	check.call(controller.shoot_ability._shot_serial == shots_before, "ordinary bridge route emits no shots")
	if not motor.is_on_floor():
		return false
	var _cancel_await_62: bool = await _move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_62
