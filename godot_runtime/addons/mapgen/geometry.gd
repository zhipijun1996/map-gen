extends RefCounted
const OPPOSITE := {"LEFT": "RIGHT", "RIGHT": "LEFT", "TOP": "BOTTOM", "BOTTOM": "TOP"}

static func placed_ports(template: Dictionary, x: int, y: int, mirror: bool, all_ports := false) -> Dictionary:
	var result: Dictionary = {}
	for original in template.all_ports if all_ports else template.ports:
		var port: Dictionary = original.duplicate(true)
		if mirror:
			port.local2[0] = 2*template.size_blocks[0]-port.local2[0]
			port.face = {"LEFT": "RIGHT", "RIGHT": "LEFT"}.get(port.face, port.face)
		port.world2 = [2*x+port.local2[0], 2*y+port.local2[1]]
		result[port.id] = port
	return result

static func permitted(port: Dictionary, direction: String) -> bool:
	return port.permission == "INOUT" or port.permission == ("OUTPUT" if direction == "out" else "INPUT")

static func matching(a: Dictionary, b: Dictionary) -> bool:
	return a.world2 == b.world2 and OPPOSITE[a.face] == b.face and a.surface == b.surface and (permitted(a, "out") and permitted(b, "in") or permitted(b, "out") and permitted(a, "in"))

static func overlap(a: Dictionary, b: Dictionary) -> bool:
	return a.origin[0] < b.origin[0]+b.size_blocks[0] and b.origin[0] < a.origin[0]+a.size_blocks[0] and a.origin[1] < b.origin[1]+b.size_blocks[1] and b.origin[1] < a.origin[1]+a.size_blocks[1]

static func bounds(items: Array) -> Array:
	var result: Array = [items[0].origin[0], items[0].origin[1], items[0].origin[0]+items[0].size_blocks[0], items[0].origin[1]+items[0].size_blocks[1]]
	for item in items:
		result[0] = mini(result[0], item.origin[0])
		result[1] = mini(result[1], item.origin[1])
		result[2] = maxi(result[2], item.origin[0]+item.size_blocks[0])
		result[3] = maxi(result[3], item.origin[1]+item.size_blocks[1])
	return result

static func coordinate_key(position: Array) -> String:
	return "%d,%d" % [position[0], position[1]]

static func groups(items: Array) -> Dictionary:
	var result: Dictionary = {}
	for item in items:
		for pid in item.ports:
			var port: Dictionary = item.ports[pid]
			var key: Array = port.world2 # Immutable exact integer pair, same insertion order.
			if not result.has(key):
				result[key] = []
			result[key].append([item, pid, port])
	return result

static func connection_groups(items: Array) -> Array:
	var result: Array = []
	for group in groups(items).values():
		if group.size() == 2 and matching(group[0][2], group[1][2]):
			result.append(group)
	return result

static func frontier(items: Array) -> Array:
	var result: Array = []
	for group in groups(items).values():
		for entry in group:
			var matched := false
			for other in group:
				if entry[0].id != other[0].id and matching(entry[2], other[2]):
					matched = true
					break
			if not matched:
				result.append(entry)
	return result

static func segment_hits_rect(a: Array, b: Array, rect: Array) -> bool:
	var lo := 0.0
	var hi := 1.0
	for k in range(2):
		var delta = b[k]-a[k]
		var minimum = rect[k]
		var maximum = rect[k]+rect[k+2]
		if delta == 0:
			if not minimum <= a[k] or not a[k] <= maximum:
				return false
		else:
			var u: float = float(minimum-a[k])/float(delta)
			var v: float = float(maximum-a[k])/float(delta)
			lo = maxf(lo, minf(u, v))
			hi = minf(hi, maxf(u, v))
			if lo > hi:
				return false
	return true
