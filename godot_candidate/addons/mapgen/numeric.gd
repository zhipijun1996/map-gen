extends RefCounted
## Reference arithmetic order and explicitly stable sorting (Godot sort is not stable).
static func shape_cost(bounds: Array, config: Dictionary) -> float:
	var width: int = bounds[2]-bounds[0]
	var height: int = bounds[3]-bounds[1]
	var excess: float = maxf(0.0, absf(log(float(width)/float(height)/config.shape.target_ratio)) - log(config.shape.soft_tolerance))
	return config.scoring.aspect * excess

static func binary64_be(value: float) -> String:
	var bytes := PackedByteArray()
	bytes.resize(8)
	bytes.encode_double(0, value)
	bytes.reverse()
	return bytes.hex_encode()

static func stable_sort(rows: Array, less: Callable) -> Array:
	if rows.size() < 2:
		return rows.duplicate()
	var half: int = rows.size()/2
	var a := stable_sort(rows.slice(0, half), less)
	var b := stable_sort(rows.slice(half), less)
	var result: Array = []
	var i := 0
	var j := 0
	while i < a.size() and j < b.size():
		if less.call(b[j], a[i]):
			result.append(b[j])
			j += 1
		else:
			result.append(a[i])
			i += 1
	return result + a.slice(i) + b.slice(j)
