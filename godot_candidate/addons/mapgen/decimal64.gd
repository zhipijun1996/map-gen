extends RefCounted
## Decimal -> binary64 round-to-nearest ties-to-even using positive big integers.
## Godot String.to_float can differ from CPython by one ULP. Never use it for
## algorithm JSON decimals. 30-bit limbs keep all intermediate products int64.
const BASE := 1073741824
const MASK := BASE-1

static func trim(a: Array) -> Array:
	while a.size() > 1 and a[-1] == 0:
		a.pop_back()
	return a

static func multiply(a: Array, n: int) -> Array:
	var out: Array = []
	var carry := 0
	for limb in a:
		var product: int = limb*n + carry
		out.append(product & MASK)
		carry = product >> 30
	while carry:
		out.append(carry & MASK)
		carry >>= 30
	return trim(out)

static func shift(a: Array, count: int) -> Array:
	var out: Array = []
	for _i in range(count/30):
		out.append(0)
	var carry := 0
	var bits := count%30
	for limb in a:
		var product: int = (limb << bits) | carry
		out.append(product & MASK)
		carry = product >> 30
	if carry:
		out.append(carry)
	return trim(out)

static func compare(a: Array, b: Array) -> int:
	if a.size() != b.size():
		return 1 if a.size() > b.size() else -1
	for i in range(a.size()-1, -1, -1):
		if a[i] != b[i]:
			return 1 if a[i] > b[i] else -1
	return 0

static func subtract(a: Array, b: Array) -> Array:
	var out := a.duplicate()
	var borrow := 0
	for i in range(out.size()):
		var delta: int = out[i] - (b[i] if i < b.size() else 0) - borrow
		borrow = 1 if delta < 0 else 0
		out[i] = delta + (BASE if borrow else 0)
	return trim(out)

static func bit_length(a: Array) -> int:
	var bits := (a.size()-1)*30
	var top: int = a[-1]
	while top:
		top >>= 1
		bits += 1
	return bits

static func parse(token: String) -> Dictionary:
	if token.length() > 4096:
		return {"ok": false, "error": "decimal token length limit"}
	var negative := token.begins_with("-")
	var parts := token.trim_prefix("-").to_lower().split("e")
	var exponent := 0
	if parts.size() > 1:
		if parts[1].length() > 6:
			return {"ok": false, "error": "decimal exponent outside candidate domain"}
		exponent = parts[1].to_int()
	var dot := parts[0].find(".")
	if dot >= 0:
		exponent -= parts[0].length()-dot-1
	var digits := parts[0].replace(".", "")
	var numerator: Array = [0]
	for character in digits:
		numerator = multiply(numerator, 10)
		numerator[0] += character.to_int()
		# multiply by ten leaves a multiple of ten; adding <=9 cannot overflow
		# the limb boundary without carry, so normalize that boundary explicitly.
		var i := 0
		while numerator[i] >= BASE:
			numerator[i] -= BASE
			i += 1
			if i == numerator.size():
				numerator.append(0)
			numerator[i] += 1
	var denominator: Array = [1]
	if exponent > 4096:
		return {"ok": false, "error": "nonfinite decimal"}
	if exponent < -8192:
		numerator = [0] # All <=4096-digit mantissas underflow to zero here.
		exponent = 0
	for _i in range(absi(exponent)):
		if exponent >= 0:
			numerator = multiply(numerator, 10)
		else:
			denominator = multiply(denominator, 10)
	var binary_exponent := bit_length(numerator)-bit_length(denominator)
	var less := compare(numerator, shift(denominator, maxi(0, binary_exponent))) < 0 if binary_exponent >= 0 else compare(shift(numerator, -binary_exponent), denominator) < 0
	if less:
		binary_exponent -= 1
	if numerator == [0]:
		binary_exponent = -1075
	if binary_exponent > 1023:
		return {"ok": false, "error": "nonfinite decimal"}
	var scale := 52-maxi(-1022, binary_exponent)
	if scale >= 0:
		numerator = shift(numerator, scale)
	else:
		denominator = shift(denominator, -scale)
	var quotient := 0
	for bit in range(53, -1, -1):
		var divisor := shift(denominator, bit)
		if compare(numerator, divisor) >= 0:
			numerator = subtract(numerator, divisor)
			quotient |= 1 << bit
	var rounding := compare(shift(numerator, 1), denominator)
	if rounding > 0 or rounding == 0 and quotient & 1:
		quotient += 1
	var exponent_bits := maxi(0, binary_exponent+1023)
	if quotient >= 1 << 53:
		quotient >>= 1
		exponent_bits += 1
	if quotient >= 1 << 52 and exponent_bits == 0:
		exponent_bits = 1
	if exponent_bits >= 2047:
		return {"ok": false, "error": "nonfinite decimal after rounding"}
	var bits: int = (exponent_bits << 52) | (quotient & ((1 << 52)-1))
	if negative:
		bits |= -9223372036854775807-1
	var bytes := PackedByteArray()
	bytes.resize(8)
	bytes.encode_s64(0, bits)
	return {"ok": true, "value": bytes.decode_double(0)}
