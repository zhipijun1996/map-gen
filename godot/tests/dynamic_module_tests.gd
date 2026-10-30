extends RefCounted

const PLAYER := preload("res://scenes/player/player.tscn")
const DT := 1.0 / 60.0
var tree: SceneTree
var check: Callable
var world: Node2D
var module: PlatformingModule
var motor: PlayerMotor
var controller: PlayerController
var respawn: SegmentRespawn
var life: DemoLifetime
var safe_trace := true
var shots := 0
var jumps := 0
var previous_body := Rect2()
var previous_hazards: Dictionary = {}

func fixture(id: String, phase: float, jump_count: int) -> void:
	if is_instance_valid(world):
		world.free()
	world = Node2D.new()
	tree.root.add_child(world)
	module = load("res://scenes/generation/modules/" + id + ".tscn").instantiate()
	module.definition = module.definition.duplicate(true)
	if id == "timed_gallery":
		module.definition.saws[0].initial_phase = phase
	else:
		module.definition.ferries[0].initial_phase = phase
	world.add_child(module)
	motor = PLAYER.instantiate()
	motor.position = module.world_entry()
	world.add_child(motor)
	controller = motor.get_node("Controller")
	controller.set_physics_process(false)
	motor.get_node("KeyboardMouseAdapter").set_process_unhandled_input(false)
	motor.tuning.max_jumps = jump_count
	motor.tuning.max_air_shots = 0
	controller.action_resources.reset()
	controller.shoot_ability.shot_fired.connect(func(_direction: Vector2, _id: int) -> void: shots += 1)
	life = DemoLifetime.new()
	respawn = SegmentRespawn.new()
	respawn.configure(controller, life)
	respawn.danger_bounds.assign(module.world_dangers())
	safe_trace = true
	shots = 0
	jumps = 0
	previous_body = Rect2(motor.global_position - Vector2(12, 18), Vector2(24, 36))
	previous_hazards.clear()
	for hazard in module.hazards:
		previous_hazards[hazard.get_instance_id()] = hazard.global_position
	await tick(3)

func tick(count: int = 1) -> void:
	for unused: int in count:
		await tree.physics_frame
		controller.physics_tick(DT)
		var body := Rect2(motor.global_position - Vector2(12, 18), Vector2(24, 36))
		var swept := previous_body.merge(body)
		for danger: Rect2 in module.world_static_dangers():
			if swept.intersects(danger, true):
				safe_trace = false
		for hazard in module.hazards:
			var previous_saw: Vector2 = previous_hazards[hazard.get_instance_id()]
			if SawHazard.swept_contact(previous_body.get_center() - previous_saw, body.get_center() - hazard.global_position, Vector2(12, 18), hazard.definition.radius):
				safe_trace = false
			previous_hazards[hazard.get_instance_id()] = hazard.global_position
		previous_body = body

func move_to(x: float, budget: int = 260) -> bool:
	for unused: int in budget:
		controller.router.set_move_axis(clampf((x - motor.global_position.x) / 5.5, -1.0, 1.0))
		await tick()
		if absf(x - motor.global_position.x) < 0.6:
			controller.router.set_move_axis(0.0)
			await tick()
			return true
	return false

func finish(label: String) -> void:
	controller.router.set_move_axis(0.0)
	await tick(3)
	check.call(motor.is_on_floor() and motor.global_position.distance_to(module.world_exit()) < 1.0, label + " action-only trajectory lands at fixed exit")
	check.call(module.port_accepts(module.definition.exit_port, motor), label + " real stationary motor satisfies exit contract")
	check.call(safe_trace, label + " full 24x36 body swept each tick avoids all hazards")
	check.call(shots == 0, label + " path needs no shooting or slow-time")
	check.call(respawn.is_safe(module.world_exit()), label + " exit has actual full-shape clearance and supporting floor")

func gallery(phase: float) -> void:
	await fixture("timed_gallery", phase, 0)
	var label := "gallery phase %.2f" % phase
	check.call(module.definition.is_valid() and module.definition.supports(motor.tuning), label + " authored definition supports zero jumps zero shots")
	check.call(await move_to(420.0), label + " reaches safe observation platform")
	var saw = module.hazards[0]
	var found_window := false
	var previous_saw_y: float = saw.global_position.y
	for unused: int in 250:
		# The circle is retreating upward and safely clear of the whole player's
		# head; this visible position criterion does not read a hidden route seed.
		if saw.global_position.y < 450.0 and saw.global_position.y < previous_saw_y:
			found_window = true
			break
		previous_saw_y = saw.global_position.y
		await tick()
	check.call(found_window, label + " arbitrary arrival can wait for a bounded safe crossing window")
	check.call(await move_to(module.world_exit().x), label + " traverses the real timed obstacle using ground movement")
	check.call(jumps == 0, label + " no jump request was injected")
	await finish(label)

func ferry(phase: float) -> void:
	await fixture("moving_transfer", phase, 1)
	var label := "ferry phase %.2f" % phase
	check.call(module.definition.is_valid() and module.definition.supports(motor.tuning), label + " supports one jump zero shots")
	check.call(await move_to(280.0), label + " approaches fixed boarding station")
	var carrier = module.moving_platforms[0]
	var boarding := false
	for unused: int in 510:
		if carrier.global_position.x < 405.0:
			boarding = true
			break
		await tick()
	check.call(boarding, label + " waits at most one cycle for boarding dwell")
	controller.router.request_action(&"jump")
	jumps += 1
	var landed := false
	for frame: int in 80:
		controller.router.set_move_axis(clampf((carrier.global_position.x - motor.global_position.x) / 5.5, -1.0, 1.0))
		await tick()
		if frame > 5 and motor.is_on_floor() and motor.global_position.x > 360.0:
			landed = true
			break
	controller.router.request_action(&"jump_release")
	controller.router.set_move_axis(0.0)
	await tick(2)
	check.call(landed, label + " single held jump boards actual AnimatableBody2D")
	var relative_x: float = motor.global_position.x - carrier.global_position.x
	var ride_start := motor.global_position.x
	var max_relative_drift := 0.0
	var ride_done := false
	var saw_platform_velocity := false
	for unused: int in 250:
		await tick()
		max_relative_drift = maxf(max_relative_drift, absf(motor.global_position.x - carrier.global_position.x - relative_x))
		if absf(motor.get_platform_velocity().x) > 20.0:
			saw_platform_velocity = true
		if carrier.global_position.x >= 945.0:
			ride_done = true
			break
	check.call(ride_done and motor.global_position.x - ride_start > 300.0, label + " neutral-input player is carried across the real gap")
	check.call(max_relative_drift < 4.0 and absf(motor.normal_velocity.x) < 0.01 and saw_platform_velocity, label + " carrier velocity is observed without idle sliding or adding persistent normal velocity")
	check.call(await move_to(module.world_exit().x), label + " walks off carrier onto fixed receiving station")
	check.call(jumps == 1 and controller.jump_ability.used_jumps <= 1, label + " complete route uses exactly one jump request")
	await finish(label)

func run(p_tree: SceneTree, p_check: Callable) -> void:
	tree = p_tree
	check = p_check
	for phase: float in [0.0, 0.25, 0.5, 0.75]:
		await gallery(phase)
		await ferry(phase)
	await contracts()
	world.free()

func contracts() -> void:
	await fixture("moving_transfer", 0.25, 1)
	controller.jump_ability.enabled = false
	check.call(not module.port_accepts(module.definition.entry_port, motor), "ferry rejects disabled required jump ability")
	controller.jump_ability.enabled = true
	controller.jump_ability.used_jumps = 1
	check.call(not module.port_accepts(module.definition.entry_port, motor), "ferry entry rejects already-spent jump resource")
	controller.jump_ability.used_jumps = 0
	var tuning := PlayerTuning.load_default()
	tuning.max_jumps = 0
	check.call(not module.definition.supports(tuning), "ferry rejects zero-jump configuration rather than relying on default two")
	negative_definitions()
	await continuity()

func continuity() -> void:
	var policy := FrameDamagePolicy.new()
	policy.lifetime = life
	world.add_child(policy)
	policy.set_physics_process(false)
	policy.register_target(&"player", controller.actor_resources.health, true)
	respawn.add_anchor(&"entry", module.world_entry())
	check.call(respawn.activate_anchor(&"entry"), "dynamic segment entry is physically safe at the current carrier phase")
	policy.environment_return_requested.connect(func() -> void: respawn.return_to_anchor())
	policy.player_fatal.connect(func() -> void: controller.die())
	var before_clock: float = module.clock
	var carrier = module.moving_platforms[0]
	var before_position: Vector2 = carrier.global_position
	var request := damage(&"return", 1.0)
	check.call(policy.submit(request), "dynamic environment damage enters production deterministic policy")
	policy.resolve_batch()
	check.call(module.clock == before_clock and carrier.global_position == before_position and controller.actor_resources.health.current == 4.0, "nonlethal return preserves module clock and exact carrier phase while deducting HP")
	check.call(not policy.submit(request), "old actor-epoch damage cannot replay after selective segment return")
	previous_body = Rect2(motor.global_position - Vector2(12, 18), Vector2(24, 36))
	await tick(2)
	check.call(module.clock > before_clock, "returned module continues its existing dynamic cycle")
	before_clock = module.clock
	before_position = carrier.global_position
	tree.paused = true
	for unused: int in 4:
		await tree.physics_frame
	check.call(module.clock == before_clock and carrier.global_position == before_position, "real SceneTree pause freezes module clock and moving collision body")
	tree.paused = false
	await tick(2)
	check.call(module.clock > before_clock, "resume continues the preserved phase instead of restarting cycle")
	var fatal := damage(&"fatal", 99.0)
	check.call(policy.submit(fatal), "fatal dynamic hazard request is accepted by production policy")
	var before_actor := life.actor_epoch
	policy.resolve_batch()
	check.call(not life.active and controller.actor_resources.health.terminal and not controller.active and life.actor_epoch == before_actor + 1, "zero HP ends lifetime before any environment return can happen")
	check.call(not respawn.return_to_anchor() and not policy.submit(fatal), "ended dynamic attempt rejects respawn and delayed old damage")

func damage(id: StringName, amount: float) -> DamageRequest:
	var request := DamageRequest.new()
	request.token = life.token()
	request.event_id = id
	request.source_id = &"dynamic_test_hazard"
	request.target_id = &"player"
	request.kind = DamageRequest.Kind.ENVIRONMENT
	request.amount = amount
	request.health_epoch = controller.actor_resources.health.epoch
	request.actor_epoch = life.actor_epoch
	return request

func negative_definitions() -> void:
	var invalid := module.definition.duplicate(true) as PlatformingModuleDefinition
	invalid.ferries[0].start = invalid.entry_port.position
	check.call(not invalid.is_valid(), "definition rejects moving body envelope over safe entry")
	invalid = module.definition.duplicate(true)
	invalid.ferries[0].finish = Vector2(1500, 612)
	check.call(not invalid.is_valid(), "definition rejects carrier path outside authored bounds")
	invalid = module.definition.duplicate(true)
	invalid.ferries[0].travel_duration = 0.0
	check.call(not invalid.is_valid(), "definition rejects zero travel duration")
	invalid = module.definition.duplicate(true)
	invalid.ferries[0].initial_phase = NAN
	check.call(not invalid.is_valid(), "definition rejects nonfinite dynamic phase")
	invalid = load("res://resources/generation/modules/timed_gallery.tres").duplicate(true)
	invalid.saws[0].origin = invalid.entry_port.position
	check.call(not invalid.is_valid(), "definition rejects swept saw envelope over a spawn anchor")
	invalid = load("res://resources/generation/modules/timed_gallery.tres").duplicate(true)
	invalid.saws[0].travel = Vector2(0, 600)
	check.call(not invalid.is_valid(), "definition rejects swept saw envelope outside world")
	invalid = load("res://resources/generation/modules/timed_gallery.tres").duplicate(true)
	invalid.saws[0].period = 0.0
	check.call(not invalid.is_valid(), "definition rejects instantaneous hazard cycle")
	var first: PlatformingModule = load("res://scenes/generation/modules/timed_gallery.tscn").instantiate()
	var second: PlatformingModule = load("res://scenes/generation/modules/timed_gallery.tscn").instantiate()
	world.add_child(first)
	second.position = Vector2(1400, 0)
	world.add_child(second)
	check.call(first.hazards[0].runtime_source_id != second.hazards[0].runtime_source_id, "same authored saw ID has distinct runtime source identity in two module instances")
	check.call(first.definition.saws[0] != second.definition.saws[0], "dynamic module instances own independent nested definitions")
	first.free()
	second.free()
