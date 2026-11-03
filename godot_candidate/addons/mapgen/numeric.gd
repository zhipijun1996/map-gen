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

static func _bit(value: int, index: int) -> int:
	return (value >> index)&1 if index >= 0 and index < 63 else 0

static func integer_hypot(x: int, y: int) -> float:
	# Correctly rounded sqrt(x*x+y*y) of the EXACT integer sum, compatible with
	# CPython hypot for integer search coordinates. float(x*x+y*y) can round the
	# sum first and produce a different ULP. Longhand square root keeps the
	# scaled square implicit; its remainder/root intermediates fit int64.
	if absi(x) > 2000000000 or absi(y) > 2000000000:
		return NAN
	var square: int = x*x+y*y
	if square == 0:
		return 0.0
	var bits := 0
	var n := square
	while n:
		bits += 1
		n >>= 1
	var exponent: int = (bits-1)/2
	var shift: int = 2*(52-exponent)
	var root := 0
	var remainder := 0
	for pair in range(52,-1,-1):
		var index := pair*2-shift
		remainder = remainder*4+2*_bit(square,index+1)+_bit(square,index)
		var trial := 4*root+1
		root *= 2
		if remainder >= trial:
			remainder -= trial
			root += 1
	if remainder*4 > root*4+1:
		root += 1
	if root >= 1 << 53:
		root >>= 1
		exponent += 1
	var bytes := PackedByteArray()
	bytes.resize(8)
	bytes.encode_s64(0,((exponent+1023)<<52)|(root&((1<<52)-1)))
	return bytes.decode_double(0)

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
