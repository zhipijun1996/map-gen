extends SceneTree
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
func drain(job):
 while not job.is_done():job.advance(1)
 return job.result()
func _initialize():
 var args:=OS.get_cmdline_user_args()
 var loader=LOAD.create(args[0],P.PACKAGE_SHA)
 var loaded: Dictionary=drain(loader)
 var req: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
 var config: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
 var limited:=config.duplicate(true);limited.search.candidate_expansion_budget=1
 var budget: Dictionary=drain(JOB.create(req,loaded.library,limited))
 var timed:=config.duplicate(true);timed.search.per_seed_timeout_seconds=0.000000001
 var clock: Dictionary=drain(JOB.create(req,loaded.library,timed))
 var wrong:=config.duplicate(true);wrong.algorithm="stable-v2"
 var invalid: Dictionary=JOB.create(req,loaded.library,wrong).result()
 var early=LOAD.create(args[0],P.PACKAGE_SHA);early.cancel()
 var checks={"candidate_limit_1_rejects_at_2":budget.status=="BUDGET_EXHAUSTED" and budget.metrics.expansions==2,"wall_clock_original_interval":clock.status=="BUDGET_EXHAUSTED" and clock.metrics.expansions==config.search.budget_check_interval,"no_maps":budget.map==null and budget.content_store.is_empty() and clock.map==null and clock.content_store.is_empty(),"no_algorithm_fallback":invalid.status=="INVALID_INPUT","cancel_before_load":early.result().status=="CANCELLED" and not early.result().has("library")}
 var report={"status":"PASS" if checks.values().all(func(v):return v) else "FAIL","checks":checks,"budget_result":budget,"clock_result":clock}
 FileAccess.open(args[1],FileAccess.WRITE).store_string(DATA.canonical(report));print(JSON.stringify(checks));quit(0 if report.status=="PASS" else 1)
