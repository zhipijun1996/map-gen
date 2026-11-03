extends SceneTree
const ARCHIVE = preload("res://addons/mapgen/module_archive.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const JOB = preload("res://addons/mapgen/generation_job.gd")
const PROTOCOL = preload("res://addons/mapgen/protocol.gd")
var checks: Dictionary = {}
var timings: Dictionary = {}

func drain(job, batch: int, label := "") -> Dictionary:
	if label.is_empty():
		label = str(batch)
	var maximum_usec := 0
	var calls := 0
	var bound := true
	while not job.is_done():
		var before: Dictionary = job.progress()
		var start := Time.get_ticks_usec()
		var state: Dictionary = job.advance(batch)
		maximum_usec = maxi(maximum_usec, Time.get_ticks_usec()-start)
		calls += 1
		bound = bound and state.ok and state.progress.operations-before.operations <= batch
	checks["bound_"+label] = bound
	timings[label] = {"calls": calls, "max_advance_usec": maximum_usec}
	var result: Dictionary = job.result()
	result.metrics.erase("generation_seconds")
	return result

func _initialize() -> void:
	var archive := ARCHIVE.open_zip(OS.get_cmdline_user_args()[0], PROTOCOL.PACKAGE_SHA)
	if not archive.ok:
		print(archive)
		quit(2)
		return
	var request = DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
	var config = DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
	var baselines: Array = []
	for batch in [1,17,128,4096]:
		var job = JOB.create(request,archive.library,config)
		checks["invalid_advance_preserves_"+str(batch)] = not job.advance(0).ok and job.progress().operations == 0 and not job.advance(4097).ok
		baselines.append(drain(job,batch))
		var done: Dictionary = job.result()
		job.cancel()
		job.advance(1)
		checks["done_idempotent_"+str(batch)] = job.result() == done
		var detached: Dictionary = job.result()
		detached.map.instances.clear()
		checks["result_snapshot_"+str(batch)] = job.result() == done
	checks.batch_independence = baselines.all(func(value): return value == baselines[0])
	checks.full_default_pass = baselines[0].status == "PASS" and baselines[0].map.instances.size() == 46
	var never_started = JOB.create(request,archive.library,config)
	never_started.cancel()
	checks.cancel_created = never_started.result().status == "CANCELLED" and never_started.result().map == null and never_started.result().content_store.is_empty()
	var preparing = JOB.create(request,archive.library,config)
	preparing.advance(1)
	preparing.cancel()
	checks.cancel_preparation = preparing.result().status == "CANCELLED" and preparing.result().map == null
	var cancelled = JOB.create(request,archive.library,config)
	while cancelled.progress().expanded < 17:
		cancelled.advance(1)
	var observed_expansions: int = cancelled.progress().expanded
	var start := Time.get_ticks_usec()
	cancelled.cancel()
	timings.cancel_usec = Time.get_ticks_usec()-start
	timings.cancel_observed_expansions = observed_expansions # Checkpoints may change; cancel must not expand further.
	checks.cancel_search = cancelled.result().status == "CANCELLED" and observed_expansions >= 17 and cancelled.result().metrics.expansions == observed_expansions and cancelled.result().map == null and cancelled.result().content_store.is_empty()
	var budget = config.duplicate(true)
	budget.search.candidate_expansion_budget = 1
	var limited: Dictionary = drain(JOB.create(request,archive.library,budget),17,"candidate_budget")
	checks.budget_boundary = limited.status == "BUDGET_EXHAUSTED" and limited.metrics.expansions == 2 and limited.map == null and limited.content_store.is_empty()
	var clock = config.duplicate(true)
	clock.search.per_seed_timeout_seconds = 0.000000001
	var timed: Dictionary = drain(JOB.create(request,archive.library,clock),128,"wall_clock")
	checks.wall_clock_boundary = timed.status == "BUDGET_EXHAUSTED" and timed.metrics.expansions == config.search.budget_check_interval and timed.map == null
	var invalid = request.duplicate(true)
	invalid.run_token = "outside request"
	checks.host_token_rejected = JOB.create(invalid,archive.library,config).result().status == "INVALID_INPUT"
	checks.missing_library = JOB.create(request,null,config).result().status == "INVALID_INPUT"
	checks.wrong_library_type = JOB.create(request,"not an archive",config).result().status == "INVALID_INPUT"
	var export_job = JOB.create(request,archive.library,config)
	while not export_job.is_done() and export_job.progress().phase != "export":
		export_job.advance(1)
	checks.export_is_pending = not export_job.is_done() and export_job.result().is_empty()
	export_job.cancel()
	checks.cancel_export = export_job.result().status == "CANCELLED" and export_job.result().map == null and export_job.result().content_store.is_empty()
	var left = JOB.create(request,archive.library,config)
	var right = JOB.create(request,archive.library,config)
	while left.progress().expanded < 17 or right.progress().expanded < 17:
		if left.progress().expanded < 17:
			left.advance(1)
		if right.progress().expanded < 17:
			right.advance(1)
	left.cancel()
	right.cancel()
	var left_result: Dictionary = left.result()
	var right_result: Dictionary = right.result()
	left_result.metrics.erase("generation_seconds")
	right_result.metrics.erase("generation_seconds")
	checks.interleaved_jobs_isolated = left_result == right_result
	var detached_request = request.duplicate(true)
	var snapshot = JOB.create(detached_request,archive.library,config)
	detached_request.seed += 1
	checks.request_snapshot = snapshot.progress().request_fingerprint == baselines[0].request_fingerprint
	snapshot.cancel()
	var ok: bool = checks.values().all(func(value): return value)
	var report := {"status": "PASS" if ok else "FAIL", "checks": checks, "timing": timings, "engine": Engine.get_version_info().string, "default_seed_targets_config": "unchanged; smaller candidate/time budgets only in explicit negative tests"}
	FileAccess.open(OS.get_cmdline_user_args()[1],FileAccess.WRITE).store_string(DATA.canonical(report))
	print(JSON.stringify(report))
	quit(0 if ok else 1)
