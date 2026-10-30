extends RefCounted
## Action-only trace helpers. The consumer supplies ticking and full-body sweeps.
var module: PlatformingModule
var motor: PlayerMotor
var controller: PlayerController
var tick_callback: Callable
var check: Callable
var shot_count := 0
var rise_shot_delay := 18
var rise_shot_direction := Vector2.DOWN

func traverse(p_module: PlatformingModule, p_motor: PlayerMotor, p_tick: Callable, p_check: Callable) -> bool:
	if _callback_is_trace_cancelled(p_tick): return false
	module = p_module
	motor = p_motor
	controller = motor.get_node("Controller") as PlayerController
	tick_callback = p_tick
	check = p_check
	shot_count = 0
	var count_shot := func(_direction: Vector2, _id: int): shot_count += 1
	controller.shoot_ability.shot_fired.connect(count_shot)
	var result := false
	var id := str(module.definition.module_id)
	var _cancel_await_23: bool = not await wait_for_shot_energy(2 if id in ["plains_recoil_double","plains_windchime_sequence"] else maxi(1,module.definition.min_air_shots))
	if is_trace_cancelled():
		if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
			controller.shoot_ability.shot_fired.disconnect(count_shot)
		return false
	if _cancel_await_23:
		controller.shoot_ability.shot_fired.disconnect(count_shot)
		return false
	if id=="plains_ferry_channel":
		var _cancel_await_27: bool = await load("res://tests/plains_exploration_motion.gd").carrier(self,module)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_27
	elif id=="plains_low_arch":
		var _cancel_await_29: bool = await load("res://tests/plains_exploration_motion.gd").low_arch(self,module)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_29
	elif id=="plains_twin_gears":
		var _cancel_await_31: bool = await load("res://tests/plains_exploration_motion.gd").twin_gears(self,module)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_31
	elif id == "plains_recovery_bridge":
		var _cancel_await_33: bool = await load("res://tests/recoil_recovery_tests.gd").new().traverse(module, motor, tick_callback, check)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_33
	elif id in ["plains_ferry_one", "plains_ferry_two", "plains_ferry_gears"]:
		var _cancel_await_35: bool = await load("res://tests/challenge_ferry_tests.gd").new().traverse(module, motor, tick_callback, check)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_35
	elif id == "plains_recoil_span":
		var _cancel_await_37: bool = await recoil_span()
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_37
	elif id in ["plains_recoil_step", "plains_recoil_double"]:
		var _cancel_await_39: bool = await recoil_rises(1 if id == "plains_recoil_step" else 2)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_39
	elif id in ["plains_recoil_chasm", "plains_recoil_chasm_wide"]:
		var _cancel_await_41: bool = await recoil_chasm()
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_41
	elif id in ["plains_gear_brook", "plains_gear_glade"]:
		var _cancel_await_43: bool = await gear_hop()
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_43
	elif not module.definition.main_route.is_empty():
		var _cancel_await_45: bool = await path(module.definition.main_route)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_45
	else:
		var _cancel_await_47: bool = await move_to(module.world_exit().x)
		if is_trace_cancelled():
			if is_instance_valid(controller) and is_instance_valid(controller.shoot_ability) and controller.shoot_ability.shot_fired.is_connected(count_shot):
				controller.shoot_ability.shot_fired.disconnect(count_shot)
			return false
		result = _cancel_await_47
	controller.shoot_ability.shot_fired.disconnect(count_shot)
	if result:
		controller.router.set_move_axis(0)
		await advance(3)
		if is_trace_cancelled(): return false
		check.call(motor.is_on_floor() and motor.global_position.distance_to(module.world_exit()) < 1, id + " actual exit has full-body standing support")
	return result

func wait_for_shot_energy(shots: int=1) -> bool:
	if is_trace_cancelled(): return false
	if controller.shot_energy==null: return true
	if not controller.shot_energy.definition.shooting_consumes_energy: return true
	for unused: int in 300:
		if controller.actor_resources.stamina.current>=controller.shot_energy.shot_energy_cost*shots: return true
		if not motor.is_on_floor(): return false
		controller.router.set_move_axis(0)
		await advance()
		if is_trace_cancelled(): return false
	return false

func follow_path(p_module: PlatformingModule, p_motor: PlayerMotor, p_tick: Callable, p_check: Callable, route: Variant) -> bool:
	if is_trace_cancelled(): return false
	module = p_module
	motor = p_motor
	controller = motor.get_node("Controller") as PlayerController
	tick_callback = p_tick
	check = p_check
	var _cancel_await_70: bool = await path(route)
	if is_trace_cancelled(): return false
	return _cancel_await_70

func advance(count := 1) -> void:
	if is_trace_cancelled(): return
	await tick_callback.call(count)
	if is_trace_cancelled(): return

func move_to(x: float, budget := 310) -> bool:
	if is_trace_cancelled(): return false
	# Optional test observer context; this only reports the intended endpoint.
	# Runtime movement remains the same Router axis loop for every consumer.
	if tick_callback.is_valid():
		var observer: Object=tick_callback.get_object()
		if observer!=null and "policy_move_goal" in observer:observer.set("policy_move_goal",x)
	for unused: int in budget:
		controller.router.set_move_axis(clampf((x - motor.global_position.x) / 5.5, -1, 1))
		await advance()
		if is_trace_cancelled(): return false
		if absf(x - motor.global_position.x) < 0.6:
			controller.router.set_move_axis(0)
			await advance(2)
			if is_trace_cancelled(): return false
			return true
	return false

func land(budget := 110) -> bool:
	if is_trace_cancelled(): return false
	controller.router.set_move_axis(0)
	for unused: int in budget:
		if motor.is_on_floor():
			await advance(3)
			if is_trace_cancelled(): return false
			return true
		await advance()
		if is_trace_cancelled(): return false
	return false

func jump_to(target: Vector2) -> bool:
	if is_trace_cancelled(): return false
	controller.router.request_action(&"jump")
	for frame: int in 110:
		controller.router.set_move_axis(clampf((target.x - motor.global_position.x) / 5.5, -1, 1))
		await advance()
		if is_trace_cancelled(): return false
		if frame > 3 and motor.is_on_floor():
			controller.router.request_action(&"jump_release")
			controller.router.set_move_axis(0)
			await advance(2)
			if is_trace_cancelled(): return false
			var success := absf(target.y - motor.global_position.y) < 1 and _floor_contains_segment(motor.global_position - module.global_position, target - module.global_position)
			if success:
				var _cancel_await_110: bool = await move_to(target.x)
				if is_trace_cancelled(): return false
				success = _cancel_await_110
			if not success:
				print("BRANCH PATH FAILED id=%s target=%s actual=%s" % [module.definition.module_id, target, motor.global_position])
			return success
	return false

func _floor_contains_segment(a: Vector2, b: Vector2) -> bool:
	if absf(a.y - b.y) > 0.1:
		return false
	var covered := minf(a.x, b.x)
	var end := maxf(a.x, b.x)
	var floors: Array[Rect2] = module.definition.platforms.duplicate()
	floors.sort_custom(func(first: Rect2, second: Rect2): return first.position.x < second.position.x)
	for floor_rect: Rect2 in floors:
		if absf(floor_rect.position.y - a.y - 18) < 0.1 and floor_rect.position.x <= covered and floor_rect.end.x > covered:
			covered = floor_rect.end.x
	return covered >= end

func path(route: Variant) -> bool:
	if is_trace_cancelled(): return false
	for step: int in range(1, route.size()):
		var previous := module.definition.anchors[route[step - 1]]
		var target := module.definition.anchors[route[step]]
		if _floor_contains_segment(previous, target):
			var _cancel_await_133: bool = not await move_to(module.position.x + target.x)
			if is_trace_cancelled(): return false
			if _cancel_await_133: return false
		else:
			var direction := signf(target.x - previous.x)
			var takeoff := previous.x
			for floor_rect: Rect2 in module.definition.platforms:
				if absf(floor_rect.position.y - previous.y - 18) < 0.1 and floor_rect.has_point(previous + Vector2(0, 19)):
					takeoff = floor_rect.end.x - 40 if direction > 0 else floor_rect.position.x + 40
					if floor_rect.size.x > 400: takeoff = previous.x + direction * 20
					break
			var _cancel_await_142: bool = not await move_to(module.position.x + takeoff)
			if is_trace_cancelled(): return false
			if _cancel_await_142: return false
			var _cancel_await_143: bool = await jump_to(module.to_global(target))
			if is_trace_cancelled(): return false
			var reached := _cancel_await_143
			check.call(reached, "authored path uses actual jump for a rise or separated equal-height floor")
			if not reached: return false
		check.call(motor.is_on_floor() and absf(motor.global_position.y - module.position.y - target.y) < 1, "authored receiver has exact grounded height")
	return true

func recoil_rises(legs: int) -> bool:
	if is_trace_cancelled(): return false
	var pairs := [Vector2(170, 400), Vector2(430, 640)]
	for leg: int in legs:
		var pair: Vector2 = pairs[leg]
		var _cancel_await_153: bool = not await move_to(_world_x(pair.x))
		if is_trace_cancelled(): return false
		if _cancel_await_153: return false
		controller.router.set_move_axis(_forward())
		controller.router.request_action(&"jump")
		await advance(rise_shot_delay)
		if is_trace_cancelled(): return false
		var before := shot_count
		controller.router.request_action(&"shoot_release", rise_shot_direction)
		await advance()
		if is_trace_cancelled(): return false
		check.call(shot_count == before + 1 and motor.recoil_burst_remaining > 0 and controller.action_resources.shot_charges == motor.tuning.max_air_shots - 1, "authored rise consumes one real downward projectile and creates upward burst")
		await advance(9)
		if is_trace_cancelled(): return false
		controller.router.request_action(&"jump_release")
		var _cancel_await_163: bool = not await move_to(_world_x(pair.y), 100)
		if is_trace_cancelled(): return false
		if not _cancel_await_163:
			_cancel_await_163 = not await land()
			if is_trace_cancelled(): return false
		if _cancel_await_163: return false
		check.call(controller.action_resources.shot_charges == motor.tuning.max_air_shots and controller.jump_ability.used_jumps == 0, "high receiver restores charges only on real floor landing")
	check.call(shot_count == legs, "rise emits exactly one projectile per authored ascent")
	var _cancel_await_166: bool = await move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_166

func recoil_chasm() -> bool:
	if is_trace_cancelled(): return false
	var _cancel_await_169: bool = not await move_to(_world_x(240))
	if is_trace_cancelled(): return false
	if _cancel_await_169: return false
	controller.router.set_move_axis(_forward())
	controller.router.request_action(&"jump")
	await advance(18)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"shoot_release", Vector2.LEFT * _forward())
	await advance()
	if is_trace_cancelled(): return false
	check.call(shot_count == 1 and motor.recoil_burst_remaining > 0, "wide chasm first release starts a real horizontal burst")
	await advance(16)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"shoot_release", Vector2.LEFT * _forward())
	await advance()
	if is_trace_cancelled(): return false
	check.call(shot_count == 2 and motor.recoil_burst_remaining > 0, "wide chasm second burst respects actual shot cooldown")
	await advance(9)
	if is_trace_cancelled(): return false
	controller.router.request_action(&"jump_release")
	controller.router.request_action(&"jump")
	await advance()
	if is_trace_cancelled(): return false
	check.call(controller.jump_ability.used_jumps == 2 and motor.normal_velocity.y < 0, "wide chasm uses configured second jump instead of invented airtime")
	var target := 990.0 if module.definition.module_id == &"plains_recoil_chasm_wide" else 930.0
	var _cancel_await_186: bool = not await move_to(_world_x(target), 140)
	if is_trace_cancelled(): return false
	if not _cancel_await_186:
		_cancel_await_186 = not await land()
		if is_trace_cancelled(): return false
	if _cancel_await_186: return false
	controller.router.request_action(&"jump_release")
	check.call(shot_count == 2, "wide chasm emits exactly two real projectiles")
	var _cancel_await_189: bool = await move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_189

func no_recoil_chasm_falls(p_module: PlatformingModule, p_motor: PlayerMotor, p_tick: Callable, p_check: Callable) -> bool:
	module = p_module
	motor = p_motor
	controller = motor.get_node("Controller") as PlayerController
	tick_callback = p_tick
	check = p_check
	shot_count = 0
	var count_shot := func(_direction: Vector2, _id: int): shot_count += 1
	controller.shoot_ability.shot_fired.connect(count_shot)
	if not await move_to(_world_x(240)):
		controller.shoot_ability.shot_fired.disconnect(count_shot)
		return false
	controller.router.request_action(&"jump")
	controller.router.set_move_axis(_forward())
	await advance(38)
	controller.router.request_action(&"jump_release")
	controller.router.request_action(&"jump")
	await advance()
	check.call(controller.jump_ability.used_jumps == 2, "negative chasm genuinely uses normal second jump with unchanged default jump physics")
	var missed := false
	var far_bank := 920.0 if module.definition.module_id == &"plains_recoil_chasm_wide" else 860.0
	for unused: int in 100:
		await advance()
		if motor.global_position.y > module.world_entry().y + 80 and not motor.is_on_floor():
			missed = _forward() * (motor.global_position.x - _world_x(far_bank)) < -12
			break
	controller.router.set_move_axis(0)
	controller.shoot_ability.shot_fired.disconnect(count_shot)
	check.call(shot_count == 0, "negative normal-double-jump trace emits no projectiles")
	print("CHASM NO RECOIL: id=%s pos=%s receiver=%s missed=%s" % [module.definition.module_id, motor.global_position, _world_x(far_bank), missed])
	return missed

func gear_hop() -> bool:
	if is_trace_cancelled(): return false
	var saw := module.definition.saws[0]
	var takeoff := saw.origin.x - 90 * _forward()
	var receiver := saw.origin.x + 90 * _forward()
	var _cancel_await_227: bool = not await move_to(module.position.x + takeoff)
	if is_trace_cancelled(): return false
	if _cancel_await_227: return false
	var _cancel_await_228: bool = not await jump_to(module.to_global(Vector2(receiver, module.definition.entry_port.position.y)))
	if is_trace_cancelled(): return false
	if _cancel_await_228: return false
	var _cancel_await_229: bool = await move_to(module.world_exit().x)
	if is_trace_cancelled(): return false
	return _cancel_await_229

func _forward() -> float:
	return -1 if module.definition.mirrored_horizontal else 1

func _world_x(authored: float) -> float:
	var sum := module.definition.world_bounds.position.x + module.definition.world_bounds.end.x
	return module.position.x + (sum - authored if module.definition.mirrored_horizontal else authored)

func recoil_span(fire: bool = true) -> bool:
	if is_trace_cancelled(): return false
	var _cancel_await_239: bool = not await move_to(_world_x(275))
	if is_trace_cancelled(): return false
	if _cancel_await_239: return false
	var launch: Dictionary={"position":motor.global_position,"grounded":motor.is_on_floor(),"used_jumps":controller.jump_ability.used_jumps,"energy":controller.actor_resources.stamina.current if controller.shot_energy!=null else -1}
	controller.router.set_move_axis(_forward())
	controller.router.request_action(&"jump")
	await advance(18)
	if is_trace_cancelled(): return false
	if fire:
		controller.router.request_action(&"shoot_release", Vector2(-_forward(), 1).normalized())
		await advance()
		if is_trace_cancelled(): return false
	for frame: int in 100:
		controller.router.set_move_axis(clampf((_world_x(700) - motor.global_position.x) / 5.5, -1, 1))
		await advance()
		if is_trace_cancelled(): return false
		if motor.is_on_floor():
			controller.router.request_action(&"jump_release")
			var _cancel_await_252: bool = absf(motor.global_position.y - module.world_exit().y) < 1 and await move_to(module.world_exit().x)
			if is_trace_cancelled(): return false
			return _cancel_await_252
		if motor.global_position.y > module.world_exit().y + 100:
			print("RECOIL SPAN FAIL launch=",launch," shots=",shot_count," current=",motor.global_position," cooldown=",controller.shoot_ability.cooldown_remaining)
			return false
	return false

func _callback_is_trace_cancelled(callback: Callable) -> bool:
	if not callback.is_valid(): return false
	var owner := callback.get_object()
	return is_instance_valid(owner) and owner.has_method("is_trace_cancelled") and bool(owner.call("is_trace_cancelled"))

func is_trace_cancelled() -> bool:
	return _callback_is_trace_cancelled(tick_callback)
