extends SceneTree
## Standalone replay oracle for the candidate bundle; not part of generation.
const ARCHIVE = preload("res://addons/mapgen/module_archive.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const JOB = preload("res://addons/mapgen/generation_job.gd")
const PROTOCOL = preload("res://addons/mapgen/protocol.gd")
var checks: Dictionary = {}

func load_json(path: String):
	var parsed := DATA.parse(FileAccess.get_file_as_string(path))
	if not parsed.ok:
		push_error(path+":"+parsed.error)
	return parsed.value

func semantic_map(value):
	if value == null:
		return null
	var data: Dictionary = value.duplicate(true)
	data.erase("map_id")
	data.generator.erase("implementation")
	data.generator.erase("request_fingerprint")
	return data

func _initialize():
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		print("Explicit module ZIP path required")
		quit(2)
		return
	var manifest: Dictionary = load_json("res://manifest.json")
	for name in manifest.files:
		checks["file:"+name] = FileAccess.get_sha256("res://"+name) == manifest.files[name]
	var archive := ARCHIVE.open_zip(args[0],PROTOCOL.PACKAGE_SHA)
	if not archive.ok:
		print(archive)
		quit(2)
		return
	var config: Dictionary = load_json("res://tests/config.json")
	for name in ["success","failure"]:
		var reference: Dictionary = load_json("res://tests/samples/"+name+"/result.json")
		var request: Dictionary = load_json("res://tests/samples/"+name+"/request.json")
		var job = JOB.create(request,archive.library,config)
		while not job.is_done():
			job.advance(128)
		var actual: Dictionary = job.result()
		checks[name+":status"] = actual.status == reference.status
		checks[name+":identity"] = actual.request_fingerprint != reference.request_fingerprint
		checks[name+":map_semantics"] = semantic_map(actual.map) == semantic_map(reference.map)
		checks[name+":all_content"] = actual.content_store == reference.content_store
		var actual_metrics: Dictionary = actual.metrics.duplicate(true)
		var reference_metrics: Dictionary = reference.metrics.duplicate(true)
		actual_metrics.erase("generation_seconds")
		reference_metrics.erase("generation_seconds")
		checks[name+":counts"] = actual_metrics == reference_metrics
	var ok: bool = checks.values().all(func(value):return value)
	print(JSON.stringify({"status":"PASS" if ok else "FAIL","runtime":"Godot Standard standalone bundle","files_checked":manifest.files.size(),"checks":checks,"readiness":manifest.readiness}))
	quit(0 if ok else 1)
