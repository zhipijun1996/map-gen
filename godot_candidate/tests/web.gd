extends Node
## Minimal test HOST only. The addon is RefCounted data and has no scene access.
const ARCHIVE = preload("res://addons/mapgen/module_archive.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const PROTOCOL = preload("res://addons/mapgen/protocol.gd")
const JOB = preload("res://addons/mapgen/generation_job.gd")
const RNG = preload("res://addons/mapgen/python_rng.gd")
const NUM = preload("res://addons/mapgen/numeric.gd")
var library
var request: Dictionary
var config: Dictionary
var job
var phase_index := 0
var cases: Array = [["default-128",128], ["failure",17], ["cancel",1], ["default-4096",4096]]
var results: Dictionary = {}
var timing: Dictionary = {}
var maximum_usec := 0
var calls := 0
var foundation_failures: Array = []
var input_sha: Dictionary = {}
var started_usec := 0
var cancelled_usec := 0

func _ready() -> void:
	started_usec = Time.get_ticks_usec()
	for name in ["request", "config", "reference-vectors", "number-vectors", "hypot-vectors"]:
		input_sha[name] = FileAccess.get_sha256("res://tests/"+name+".json")
	var archive := ARCHIVE.open_zip("res://tests/dependencies/modules.zip", PROTOCOL.PACKAGE_SHA)
	if not archive.ok:
		_finish({"error": archive.error})
		return
	library = archive.library
	request = DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
	config = DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
	var vectors = DATA.parse(FileAccess.get_file_as_string("res://tests/reference-vectors.json")).value
	for vector in vectors.streams.slice(0,3):
		var rng = RNG.new()
		rng.seed_integer(vector.seed.to_int())
		for v in vector.random:
			if NUM.binary64_be(rng.random()) != v.binary64_be:
				foundation_failures.append("random:"+vector.seed)
		for v in vector.getrandbits:
			if rng.bits_decimal(v.bits) != v.value:
				foundation_failures.append("bits:"+vector.seed)
		for v in vector.randrange:
			if str(rng.randrange(v.stop.to_int())) != v.value:
				foundation_failures.append("randrange:"+vector.seed)
		var array: Array = range(22)
		rng.shuffle(array)
		if array != vector.shuffle_22:
			foundation_failures.append("shuffle:"+vector.seed)
		for v in vector.uniform_minus3_plus3:
			if NUM.binary64_be(rng.uniform(-3,3)) != v.binary64_be:
				foundation_failures.append("uniform:"+vector.seed)
		if rng.getstate() != vector.saved_state:
			foundation_failures.append("state:"+vector.seed)
		if not rng.setstate(vector.saved_state):
			foundation_failures.append("restore:"+vector.seed)
		var branch: Array = [rng.randrange(5),rng.random(),rng.getrandbits(32)]
		if branch != vector.restored_branch:
			foundation_failures.append("restored branch:"+vector.seed)
	if NUM.stable_sort(vectors.stable_sort.input,func(a,b):return a[1]>b[1]) != vectors.stable_sort.descending:
		foundation_failures.append("stable ties")
	for seed_value in [-9007199254740992,9007199254740992]:
		var rng = RNG.new()
		if rng.seed_integer(seed_value):
			foundation_failures.append("out of range seed accepted")
	for vector in vectors.shape_cost:
		if NUM.binary64_be(NUM.shape_cost(vector.bounds, config)) != vector.cost.binary64_be:
			foundation_failures.append("shape:"+str(vector.bounds))
	var numbers = DATA.parse(FileAccess.get_file_as_string("res://tests/number-vectors.json")).value
	for vector in numbers.numbers:
		if NUM.binary64_be(DATA.parse(vector.token).value) != vector.binary64_be:
			foundation_failures.append("decimal:"+vector.token)
	for vector in numbers.seeds:
		var rng = RNG.new()
		rng.seed_integer(vector.seed.to_int())
		for expected in vector.random_bits:
			if NUM.binary64_be(rng.random()) != expected:
				foundation_failures.append("boundary seed:"+vector.seed)
		if rng.getstate() != vector.state:
			foundation_failures.append("boundary state:"+vector.seed)
	timing.preload_and_vectors_usec = Time.get_ticks_usec()-started_usec
	var hypot_vectors = DATA.parse(FileAccess.get_file_as_string("res://tests/hypot-vectors.json")).value
	for row in hypot_vectors:
		if NUM.binary64_be(NUM.integer_hypot(row.x,row.y)) != row.bits:
			foundation_failures.append("hypot:"+str(row))
	_start_case()

func _start_case() -> void:
	maximum_usec = 0
	calls = 0
	var req := request.duplicate(true)
	if cases[phase_index][0] == "failure":
		req.player.abilities = ["jump"]
	job = JOB.create(req,library,config)
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.mapgenPhase = " + JSON.stringify(cases[phase_index][0]))

func _process(_delta: float) -> void:
	if job == null:
		return
	var name: String = cases[phase_index][0]
	var before: Dictionary = job.progress()
	var start := Time.get_ticks_usec()
	var state: Dictionary = job.advance(cases[phase_index][1])
	maximum_usec = maxi(maximum_usec, Time.get_ticks_usec()-start)
	calls += 1
	if not state.ok or state.progress.operations-before.operations > cases[phase_index][1]:
		foundation_failures.append("operation_bound:"+name)
	if name == "cancel" and state.progress.expanded >= 17:
		start = Time.get_ticks_usec()
		job.cancel()
		cancelled_usec = Time.get_ticks_usec()-start
	if job.is_done():
		results[name] = job.result()
		timing[name] = {"calls": calls, "max_advance_usec": maximum_usec, "progress": job.progress()}
		job = null
		phase_index += 1
		if phase_index < cases.size():
			_start_case()
		else:
			_finish({"engine": Engine.get_version_info().string, "results": results, "timing": timing, "cancel_usec": cancelled_usec, "foundation_failures": foundation_failures, "input_sha256": input_sha, "elapsed_usec": Time.get_ticks_usec()-started_usec, "runtime": "web" if OS.has_feature("web") else "native"})

func _finish(report: Dictionary) -> void:
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.mapgenReport = " + JSON.stringify(report, "", true, true))
	print("MAPGEN_WEB_FINISHED")
	set_process(false)
