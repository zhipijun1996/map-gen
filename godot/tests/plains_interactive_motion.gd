extends RefCounted
static func traverse(driver:Variant,module:PlatformingModule,latch:ShotLatch,forward:bool=true)->bool:
	if _driver_cancelled(driver): return false
	var id:String=str(module.definition.module_id)
	if id=="plains_thorn_cells":
		var _cancel_await_5: bool = not await driver.move_to(module.position.x+(170 if forward else 360))
		if _driver_cancelled(driver): return false
		if _cancel_await_5:return false
		var _cancel_await_6: bool = not await driver.jump_to(module.position+Vector2(420 if forward else 150,282))
		if _driver_cancelled(driver): return false
		if _cancel_await_6:return false
	elif id=="plains_thorn_wall":
		var _cancel_await_8: bool = not await driver.move_to(module.position.x+(225 if forward else 450))
		if _driver_cancelled(driver): return false
		if _cancel_await_8:return false
		var _cancel_await_9: bool = not await driver.jump_to(module.position+Vector2(352,152))
		if _driver_cancelled(driver): return false
		if _cancel_await_9:return false
		var _cancel_await_10: bool = not await driver.jump_to(module.position+Vector2(490 if forward else 210,282))
		if _driver_cancelled(driver): return false
		if _cancel_await_10:return false
	elif id in ["plains_remote_bell","plains_bell_ferry_control"]:
		if latch==null:return false
		if not latch.is_open:
			var body:StaticBody2D=latch.bell_body if forward else latch.access_bodies[0]
			var _cancel_await_15: bool = not await driver.move_to(body.global_position.x)
			if _driver_cancelled(driver): return false
			if _cancel_await_15:return false
			driver.controller.router.request_action(&"shoot_release",(body.global_position-driver.motor.global_position).normalized())
			await driver.advance(32)
			if _driver_cancelled(driver): return false
			if not latch.is_open:return false
		if id=="plains_bell_ferry_control":
			var _cancel_await_19: bool = await load("res://tests/plains_exploration_motion.gd").carrier(driver,module,forward)
			if _driver_cancelled(driver): return false
			return _cancel_await_19
	var _cancel_await_20: bool = await driver.move_to((module.world_exit() if forward else module.world_entry()).x)
	if _driver_cancelled(driver): return false
	return _cancel_await_20

static func _driver_cancelled(driver: Variant) -> bool:
	return is_instance_valid(driver) and driver.has_method("is_trace_cancelled") and bool(driver.call("is_trace_cancelled"))
