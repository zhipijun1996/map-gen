extends SceneTree
const DATA = preload("res://addons/mapgen/data_json.gd")
const NUM = preload("res://addons/mapgen/numeric.gd")
const RNG = preload("res://addons/mapgen/python_rng.gd")
func _initialize():
	var vectors = DATA.parse(FileAccess.get_file_as_string("res://tests/number-vectors.json")).value
	var failures: Array = []
	for vector in vectors.numbers:
		var parsed := DATA.parse(vector.token)
		if not parsed.ok or NUM.binary64_be(parsed.value) != vector.binary64_be:
			failures.append(vector.token)
	for vector in vectors.seeds:
		var rng = RNG.new()
		if not rng.seed_integer(vector.seed.to_int()):
			failures.append("seed rejected:" + vector.seed)
		for expected in vector.random_bits:
			if NUM.binary64_be(rng.random()) != expected:
				failures.append("RNG:" + vector.seed)
		if rng.getstate() != vector.state:
			failures.append("state:" + vector.seed)
	print(JSON.stringify({"suite": "decimal64 and seed boundaries", "decimal_vectors": vectors.numbers.size(), "seed_vectors": vectors.seeds.size(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)
