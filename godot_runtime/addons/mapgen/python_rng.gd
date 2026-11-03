extends RefCounted
## CPython random.Random integer-seed MT19937, independent of Godot's RNG.
## All arithmetic is scalar int64/double. Unsigned 32-bit words are masked.
const MASK := 0xffffffff
const MAX_SEED := 9007199254740991
var words := PackedInt64Array()
var index := 624

func seed_integer(value: int) -> bool:
	if value < -MAX_SEED or value > MAX_SEED:
		return false
	var magnitude: int = absi(value)
	var key: Array = [magnitude & MASK]
	if magnitude >> 32:
		key.append(magnitude >> 32)
	words.resize(624)
	words[0] = 19650218
	for i in range(1, 624):
		words[i] = (1812433253 * (words[i-1] ^ (words[i-1] >> 30)) + i) & MASK
	var i := 1
	var j := 0
	for _k in range(maxi(624, key.size())):
		words[i] = ((words[i] ^ ((words[i-1] ^ (words[i-1] >> 30)) * 1664525)) + key[j] + j) & MASK
		i += 1
		j += 1
		if i >= 624:
			words[0] = words[623]
			i = 1
		if j >= key.size():
			j = 0
	for _k in range(623):
		words[i] = ((words[i] ^ ((words[i-1] ^ (words[i-1] >> 30)) * 1566083941)) - i) & MASK
		i += 1
		if i >= 624:
			words[0] = words[623]
			i = 1
	words[0] = 0x80000000
	index = 624
	return true

func word() -> int:
	if index >= 624:
		for k in range(624):
			var y: int = (words[k] & 0x80000000) | (words[(k+1)%624] & 0x7fffffff)
			words[k] = words[(k+397)%624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
		index = 0
	var y: int = words[index]
	index += 1
	y ^= y >> 11
	y ^= (y << 7) & 0x9d2c5680
	y ^= (y << 15) & 0xefc60000
	y ^= y >> 18
	return y & MASK

func random() -> float:
	var a: int = word() >> 5
	var b: int = word() >> 6
	return (float(a) * 67108864.0 + float(b)) * (1.0 / 9007199254740992.0)

func bits_words(bits: int) -> Array:
	assert(bits >= 0 and bits <= 4096)
	var result: Array = []
	var left := bits
	while left > 0:
		var v := word()
		if left < 32:
			v >>= 32-left
		result.append(v)
		left -= 32
	return result

func getrandbits(bits: int) -> int:
	assert(bits >= 0 and bits <= 63)
	var parts := bits_words(bits)
	return (parts[0] if parts.size() else 0) | (parts[1] << 32 if parts.size() > 1 else 0)

func bits_decimal(bits: int) -> String:
	var parts := bits_words(bits)
	# Base 10^9 limbs; every intermediate stays below signed int64 maximum.
	var limbs: Array = [0]
	for n in range(parts.size()-1, -1, -1):
		var carry: int = parts[n]
		for k in range(limbs.size()):
			var value: int = limbs[k] * 4294967296 + carry
			limbs[k] = value % 1000000000
			carry = value / 1000000000
		while carry:
			limbs.append(carry % 1000000000)
			carry = carry / 1000000000
	var text: String = str(limbs[-1])
	for n in range(limbs.size()-2, -1, -1):
		text += "%09d" % limbs[n]
	return text

func randrange(stop: int) -> int:
	assert(stop > 0 and stop <= MAX_SEED)
	var bits := 0
	var n := stop
	while n:
		bits += 1
		n >>= 1
	var value := getrandbits(bits)
	while value >= stop:
		value = getrandbits(bits)
	return value

func shuffle(array: Array) -> void:
	for i in range(array.size()-1, 0, -1):
		var j := randrange(i+1)
		var value = array[i]
		array[i] = array[j]
		array[j] = value

func uniform(a: float, b: float) -> float:
	return a + (b-a)*random()

func getstate() -> Array:
	var state: Array = Array(words)
	state.append(index)
	return [3, state, null]

func setstate(state: Array) -> bool:
	if state.size() != 3 or state[0] != 3 or not state[1] is Array or state[1].size() != 625 or state[2] != null:
		return false
	for i in range(625):
		if not state[1][i] is int or state[1][i] < 0 or state[1][i] > (624 if i == 624 else MASK):
			return false
	words = PackedInt64Array(state[1].slice(0, 624))
	index = state[1][624]
	return true
