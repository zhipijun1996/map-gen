extends SceneTree
const LOAD = preload("res://addons/mapgen/preload_job.gd")
const JOB = preload("res://addons/mapgen/generation_job.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const P = preload("res://addons/mapgen/protocol.gd")

func _initialize():
	var args := OS.get_cmdline_user_args()
	var output := args[1]
	var cases: Array = DATA.parse(FileAccess.get_file_as_string(args[2])).value
	var loader = LOAD.create(args[0],P.PACKAGE_SHA)
	while not loader.is_done():
		loader.advance(1)
	var loaded: Dictionary = loader.result()
	if loaded.status != "PASS":
		print(loaded)
		quit(2)
		return
	FileAccess.open(output+"/preload.json",FileAccess.WRITE).store_string(DATA.canonical(loader.profile()))
	for row in cases:
		var request: Dictionary = DATA.parse(FileAccess.get_file_as_string(row.request)).value
		var config: Dictionary = DATA.parse(FileAccess.get_file_as_string(row.config)).value
		var job = JOB.create(request,loaded.library,config)
		var intent_at := -1
		var observed_at := -1
		var finished_at := -1
		while not job.is_done():
			if row.has("cancel_phase") and job.phase_name() == row.cancel_phase and intent_at < 0:
				intent_at = Time.get_ticks_usec()+1000
			job.advance(row.get("batch",1))
			if intent_at > 0 and Time.get_ticks_usec() >= intent_at:
				observed_at = Time.get_ticks_usec()
				job.cancel()
				finished_at = Time.get_ticks_usec()
		var start := Time.get_ticks_usec()
		var result: Dictionary = job.result()
		var snapshot_usec := Time.get_ticks_usec()-start
		var report := {"result":result,"profile":job.profile(),"result_snapshot_usec":snapshot_usec,"cancel":{"kind":"scheduled external input deadline; includes advance until host observes", "intent_usec":intent_at,"observed_usec":observed_at,"finished_usec":finished_at,"latency_usec":finished_at-intent_at if intent_at>0 else null}}
		FileAccess.open(output+"/"+row.id+".json",FileAccess.WRITE).store_string(DATA.canonical(report))
		print(row.id+" "+result.status+" "+str(result.metrics.get("expansions",0)))
	quit()
