extends RefCounted
## Same owned-rectangle transform as mapgen/transform.py. Source evidence stays
## in source coordinates. Horizontal reflection never reverses directed Routes.
const POINTS := ["position", "origin", "start", "finish", "bell", "return_access", "additional_pair_access", "muzzle", "ellipse_center", "entry_port", "exit_port", "stagingPosition", "targetPosition"]
const RECTS := ["rect", "gate", "paired_gate", "region", "world_bounds"]
const VECTORS := ["travel", "direction", "normal", "offset", "sequence_offset", "crossing_offset"]

static func point(p: Array, width, origin: Array, mirror: bool) -> Array:
	var x = p[0]-origin[0]
	return [width-x if mirror else x, p[1]-origin[1]]

static func rectangle(p: Array, width, origin: Array, mirror: bool) -> Array:
	var x = p[0]-origin[0]
	return [width-x-p[2] if mirror else x, p[1]-origin[1], p[2], p[3]]

static func visit(value, width, origin: Array, mirror: bool, key := ""):
	if value is Dictionary:
		if value.has_all(["x", "y", "w", "h"]):
			var rect := rectangle([value.x, value.y, value.w, value.h], width, origin, mirror)
			var out: Dictionary = value.duplicate(true)
			out.x = rect[0]
			out.y = rect[1]
			out.w = rect[2]
			out.h = rect[3]
			return out
		var out: Dictionary = {}
		for field in value:
			if value.has_all(["x", "y"]) and field in ["x", "y"]:
				continue
			out[field] = visit(value[field], width, origin, mirror, field)
		if value.has_all(["x", "y"]):
			var xy := point([value.x, value.y], width, origin, mirror)
			out.x = xy[0]
			out.y = xy[1]
		return out
	if value is Array:
		if key in POINTS and value.size() == 2 and is_number(value[0]) and is_number(value[1]):
			return point(value, width, origin, mirror)
		if key in RECTS and value.size() == 4 and value.all(is_number):
			return rectangle(value, width, origin, mirror)
		if key in VECTORS and value.size() == 2:
			return [-value[0] if mirror else value[0], value[1]]
		var out: Array = []
		if key == "loop_points":
			for p in value:
				out.append(point(p, width, origin, mirror))
		elif key in ["platforms", "hazards"]:
			for p in value:
				out.append(rectangle(p, width, origin, mirror) if p is Array else visit(p, width, origin, mirror))
		elif key == "access":
			if value.size() == 2 and is_number(value[0]):
				return point(value, width, origin, mirror)
			for p in value:
				out.append(point(p, width, origin, mirror))
		else:
			for p in value:
				out.append(visit(p, width, origin, mirror))
		return out
	if key == "targetX" and is_number(value):
		var x = value-origin[0]
		return width-x if mirror else x
	if mirror and key in ["face", "targetFace", "return_access_side_policy"]:
		return {"left": "right", "right": "left", "LEFT": "RIGHT", "RIGHT": "LEFT"}.get(value, value)
	return value

static func is_number(value) -> bool:
	return value is int or value is float

static func materialize(template: Dictionary, mirror: bool, block_pixels: int) -> Dictionary:
	var raw: Dictionary = template.compiled_content.duplicate(true)
	raw.erase("ports")
	raw.erase("routes")
	var width: int = template.size_blocks[0]*block_pixels
	var bounds: Dictionary = template.source_bounds
	var result: Dictionary = visit(raw, width, [bounds.x, bounds.y], mirror)
	if mirror:
		for thorn in result.get("thorns", []):
			if thorn.face in ["top", "bottom"]:
				thorn.start_offset = result.platforms[thorn.platform_index][2]-thorn.start_offset-thorn.length
		for platform in result.get("moving_platforms", []):
			if platform.get("trajectory_kind") == "clockwise_ellipse/v1":
				platform.ellipse_x_sign = -platform.get("ellipse_x_sign", 1)
				if platform.ellipse_x_sign == 1:
					platform.erase("ellipse_x_sign")
	result.coordinate_frame = "owned_rectangle_pixels"
	result.source_affine = [-1 if mirror else 1, 0, 0, 1, width+bounds.x if mirror else -bounds.x, -bounds.y]
	return result
