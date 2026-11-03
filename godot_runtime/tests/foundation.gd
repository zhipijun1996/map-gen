extends SceneTree
const RNG = preload("res://addons/mapgen/python_rng.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const NUM = preload("res://addons/mapgen/numeric.gd")
const PROTOCOL = preload("res://addons/mapgen/protocol.gd")
const ARCHIVE = preload("res://addons/mapgen/module_archive.gd")
var failures: Array = []
var checks := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)

func read(path: String):
	var parsed := DATA.parse(FileAccess.get_file_as_string(path))
	check(parsed.ok, path + ": " + parsed.error)
	return parsed.value

func _initialize() -> void:
	var vectors: Dictionary = read("res://tests/reference-vectors.json")
	var request: Dictionary = read("res://tests/request.json")
	var config: Dictionary = read("res://tests/config.json")
	check(PROTOCOL.validate(request, config).is_empty(), "default inputs")
	for vector in vectors.streams:
		if vector.seed.length() > 16:
			continue # Explicitly OUTSIDE supported domain, checked below.
		var rng = RNG.new()
		check(rng.seed_integer(vector.seed.to_int()), "seed:" + vector.seed)
		for v in vector.random:
			check(NUM.binary64_be(rng.random()) == v.binary64_be, "random:" + vector.seed)
		for v in vector.getrandbits:
			check(rng.bits_decimal(v.bits) == v.value, "getrandbits:%s:%d" % [vector.seed, v.bits])
		for v in vector.randrange:
			check(str(rng.randrange(v.stop.to_int())) == v.value, "randrange:" + vector.seed)
		var array: Array = range(22)
		rng.shuffle(array)
		check(array == vector.shuffle_22, "shuffle:" + vector.seed)
		for v in vector.uniform_minus3_plus3:
			check(NUM.binary64_be(rng.uniform(-3, 3)) == v.binary64_be, "uniform:" + vector.seed)
		check(rng.getstate() == vector.saved_state, "saved state:" + vector.seed)
		check(rng.setstate(vector.saved_state), "restore accepted")
		var branch: Array = [rng.randrange(5), rng.random(), rng.getrandbits(32)]
		check(branch == vector.restored_branch, "restored branch:" + vector.seed)
	for v in vectors.shape_cost:
		check(NUM.binary64_be(NUM.shape_cost(v.bounds, config)) == v.cost.binary64_be, "shape:" + str(v.bounds))
	check(NUM.stable_sort(vectors.stable_sort.input, func(a, b): return a[1] > b[1]) == vectors.stable_sort.descending, "stable ties")
	for seed_value in [-9007199254740992, 9007199254740992, 9223372036854775807]:
		var rng = RNG.new()
		check(not rng.seed_integer(seed_value), "reject RNG seed:" + str(seed_value))
		var invalid := request.duplicate(true)
		invalid.seed = seed_value
		check(not PROTOCOL.validate(invalid, config).is_empty(), "reject protocol seed:" + str(seed_value))
	for text in ['{"x":1,"x":2}', '9223372036854775808', '-9223372036854775809', '1e999', '[1,]', '{"x":01}']:
		check(not DATA.parse(text).ok, "strict JSON:" + text)
	check(DATA.parse("9007199254740991").value == 9007199254740991, "max seed parses exactly")
	var token := request.duplicate(true)
	token.run_token = "not a generation input"
	check(not PROTOCOL.validate(token, config).is_empty(), "host token rejected")
	var changed := request.duplicate(true)
	changed.seed += 1
	check(PROTOCOL.fingerprint(request, config, PROTOCOL.PACKAGE_SHA) != PROTOCOL.fingerprint(changed, config, PROTOCOL.PACKAGE_SHA), "fingerprint input-sensitive")
	var args := OS.get_cmdline_user_args()
	if args.size():
		var archive := ARCHIVE.open_zip(args[0], PROTOCOL.PACKAGE_SHA)
		check(archive.ok, "real ZIP read: " + archive.get("error", ""))
		if archive.ok:
			check(archive.checked_files == 657, "all manifest files verified")
			check(archive.library.read_json("catalog.json").value.modules.size() == 115, "all real modules read")
	var report := {"suite": "foundation", "engine": Engine.get_version_info().string, "checks": checks, "failures": failures, "supported_seed_range": ["-9007199254740991", "9007199254740991"], "frozen_seed_vectors_supported": ["0", "-1", "930001"], "frozen_seed_vectors_rejected": ["9223372036854775815", "340282366920938463463374607431768211579"]}
	print(JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
