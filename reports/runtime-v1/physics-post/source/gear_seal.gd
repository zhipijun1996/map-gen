extends StaticBody2D
## Independent immutable instance overlay: physical blocking is not damage policy.
const VERSION := "gear-seal/1"
const THICKNESS := 32.0
const OPENING := 128.0
var spec: Dictionary

static func rectangle(port: Dictionary, bounds: Dictionary) -> Rect2:
	var p: Vector2 = preload("package_adapter.gd").point(port.position) - Vector2(bounds.x, bounds.y)
	match port.face:
		"LEFT": return Rect2(0, p.y - OPENING / 2, THICKNESS, OPENING)
		"RIGHT": return Rect2(bounds.w - THICKNESS, p.y - OPENING / 2, THICKNESS, OPENING)
		"TOP": return Rect2(p.x - OPENING / 2, 0, OPENING, THICKNESS)
		_: return Rect2(p.x - OPENING / 2, bounds.h - THICKNESS, OPENING, THICKNESS)

static func describe(port: Dictionary, bounds: Dictionary) -> Dictionary:
	var rect := rectangle(port, bounds)
	return {"port_id": port.id, "component": VERSION, "rect_pixels": [rect.position.x, rect.position.y, rect.size.x, rect.size.y], "face": port.face, "opening_pixels": OPENING, "thickness_pixels": THICKNESS}

func configure(value: Dictionary, player: PlayerController, services: Dictionary, instance_id: String) -> void:
	spec = value.duplicate(true)
	var r: Array = spec.rect_pixels
	position = Vector2(r[0] + r[2] / 2.0, r[1] + r[3] / 2.0)
	collision_layer = 1; collision_mask = 0
	var shape := CollisionShape2D.new(); var box := RectangleShape2D.new()
	box.size = Vector2(r[2], r[3]); shape.shape = box; add_child(shape)
	var hurt := DemoContactEmitter.new()
	hurt.controller = player; hurt.policy = services.policy; hurt.kind = DamageRequest.Kind.ENVIRONMENT
	hurt.source_id = StringName("mapgen/seal/" + instance_id.uri_encode() + "/" + str(spec.port_id).uri_encode())
	hurt.half_size = box.size / 2.0; add_child(hurt)
	queue_redraw()

func _process(_dt: float) -> void:
	queue_redraw()

func _draw() -> void:
	if spec.is_empty(): return
	var vertical: bool = spec.face in ["LEFT", "RIGHT"]
	var rect := Rect2(Vector2(-16, -64) if vertical else Vector2(-64, -16), Vector2(32, 128) if vertical else Vector2(128, 32))
	draw_rect(rect, Color("504451"))
	for i: int in 4:
		var center := Vector2(0, -48 + i * 32) if vertical else Vector2(-48 + i * 32, 0)
		draw_set_transform(center, Time.get_ticks_msec() * 0.001 * (1 if i % 2 == 0 else -1))
		PixelFormalTerrain.draw_saw(self, 14.0)
	draw_set_transform(Vector2.ZERO)
