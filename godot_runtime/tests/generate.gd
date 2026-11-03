extends SceneTree
const ARCHIVE = preload("res://addons/mapgen/module_archive.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const JOB = preload("res://addons/mapgen/generation_job.gd")
const PROTOCOL = preload("res://addons/mapgen/protocol.gd")
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 5:
		print("module.zip request.json config.json output.json advance_budget [cancel_at_expansion]")
		quit(2)
		return
	var archive := ARCHIVE.open_zip(args[0], PROTOCOL.PACKAGE_SHA)
	if not archive.ok:
		print(archive)
		quit(2)
		return
	var request := DATA.parse(FileAccess.get_file_as_string(args[1]))
	var config := DATA.parse(FileAccess.get_file_as_string(args[2]))
	if not request.ok or not config.ok:
		print([request.get("error"), config.get("error")])
		quit(2)
		return
	var job = JOB.create(request.value, archive.library, config.value)
	var maximum_usec := 0
	var calls := 0
	var total_usec := 0
	var steps: Array = []
	var bounds_ok := true
	while not job.is_done():
		var start := Time.get_ticks_usec()
		var before: Dictionary = job.progress()
		var state: Dictionary = job.advance(args[4].to_int())
		var elapsed := Time.get_ticks_usec()-start
		maximum_usec = maxi(maximum_usec, elapsed)
		total_usec += elapsed
		calls += 1
		bounds_ok = bounds_ok and state.progress.operations-before.operations <= args[4].to_int()
		if not state.ok:
			print(state)
			job.cancel()
			quit(2)
			return
		if args.size() > 5 and state.progress.expanded >= args[5].to_int():
			job.cancel()
		if calls%1000 == 0:
			steps.append(state.progress)
	var result: Dictionary = job.result()
	var output := {"result": result, "scheduling": {"budget": args[4].to_int(), "calls": calls, "operation_bound_pass": bounds_ok, "max_advance_usec": maximum_usec, "total_advance_usec": total_usec, "progress": job.progress(), "profile":job.profile(),"samples": steps}}
	FileAccess.open(args[3], FileAccess.WRITE).store_string(DATA.canonical(output))
	print(JSON.stringify({"status": result.status, "metrics": result.metrics, "calls": calls, "max_advance_usec": maximum_usec, "operation_bound_pass": bounds_ok}))
	quit()
