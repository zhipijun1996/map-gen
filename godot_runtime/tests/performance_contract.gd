extends SceneTree
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const NUM=preload("res://addons/mapgen/numeric.gd")
const P=preload("res://addons/mapgen/protocol.gd")
const DERIVED=preload("res://addons/mapgen/derived_library.gd")
class Probe extends "res://addons/mapgen/preload_job.gd":
 func consume():return true
var checks: Dictionary={}
func drain(job,batch:=1):
 while not job.is_done():job.advance(batch)
 return job.result()
func same(a,b)->bool:
 if typeof(a)!=typeof(b):return false
 if a is float:return NUM.binary64_be(a)==NUM.binary64_be(b)
 if a is Dictionary:
  if a.size()!=b.size():return false
  for key in a:
   if not b.has(key) or not same(a[key],b[key]):return false
  return true
 if a is Array:
  if a.size()!=b.size():return false
  for i in range(a.size()):
   if not same(a[i],b[i]):return false
  return true
 return a==b
func _initialize():
 var args:=OS.get_cmdline_user_args();var timings: Dictionary={}
 var cold=LOAD.create(args[0],P.PACKAGE_SHA,false);var raw: Dictionary=drain(cold);timings.uncached=cold.profile()
 var cached=LOAD.create(args[0],P.PACKAGE_SHA);var fast: Dictionary=drain(cached);timings.derived_cold=cached.profile()
 var hot=LOAD.create(args[0],P.PACKAGE_SHA);var warm: Dictionary=drain(hot);timings.derived_warm=hot.profile()
 checks.library_values_types_and_float_bits=same(raw.library._json,fast.library._json) and same(fast.library._json,warm.library._json)
 checks.raw_files_complete=same(raw.library._files,fast.library._files)
 checks.all_manifest_files_verified=fast.checked_files==657 and fast.cache_status=="bound_source_json"
 var probe=Probe.new();probe._expected=P.PACKAGE_SHA
 checks.module_binding_rejected=(await probe._decode_derived(DERIVED.SCHEMA,"bad",P.IMPLEMENTATION,DERIVED.ROWS)).is_empty()
 checks.implementation_binding_rejected=(await probe._decode_derived(DERIVED.SCHEMA,P.PACKAGE_SHA,"old",DERIVED.ROWS)).is_empty()
 var damaged: Array=DERIVED.ROWS.duplicate(true);damaged[0][2]="bad"
 checks.payload_hash_rejected=(await probe._decode_derived(DERIVED.SCHEMA,P.PACKAGE_SHA,P.IMPLEMENTATION,damaged)).is_empty()
 var req: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
 var cfg: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
 var before: Dictionary=fast.library.read_json("catalog.json")
 var left=JOB.create(req,fast.library,cfg);var other_req:=req.duplicate(true);other_req.seed=930007
 var right=JOB.create(other_req,fast.library,cfg)
 while left.progress().expanded<128 or right.progress().expanded<128:
  if left.progress().expanded<128:left.advance(1)
  if right.progress().expanded<128:right.advance(1)
 left.cancel();var survivor: Dictionary=drain(right)
 checks.cancelled_empty=left.result().status=="CANCELLED" and left.result().map==null and left.result().content_store.is_empty()
 checks.other_job_survives=survivor.status=="PASS" and survivor.metrics.expansions==88856
 var detached_result: Dictionary=right.result();detached_result.map.instances.clear();detached_result.content_store.clear()
 checks.complete_result_is_snapshot=same(right.result(),survivor)
 var damaged_path: String=args[1]+".damaged.zip"
 var damaged_zip:=FileAccess.get_file_as_bytes(args[0]);damaged_zip.append(1)
 FileAccess.open(damaged_path,FileAccess.WRITE).store_buffer(damaged_zip)
 var invalid: Dictionary=drain(LOAD.create(damaged_path,P.PACKAGE_SHA))
 checks.cache_cannot_bypass_source_sha=invalid.status=="INVALID_INPUT" and not invalid.has("library")
 DirAccess.remove_absolute(damaged_path)
 checks.shared_library_unchanged=same(before,fast.library.read_json("catalog.json"))
 var detached: Dictionary=fast.library.read_json("catalog.json");detached.value.modules.clear()
 checks.public_library_read_is_snapshot=fast.library.read_json("catalog.json").value.modules.size()==115
 var negative:=cfg.duplicate(true);negative.search.candidate_expansion_budget=1
 var failed: Dictionary=drain(JOB.create(req,fast.library,negative))
 checks.original_candidate_budget=failed.status=="BUDGET_EXHAUSTED" and failed.metrics.expansions==2 and failed.map==null and failed.content_store.is_empty()
 var timed:=cfg.duplicate(true);timed.search.per_seed_timeout_seconds=0.000000001
 var exhausted: Dictionary=drain(JOB.create(req,fast.library,timed))
 checks.original_clock_interval=exhausted.status=="BUDGET_EXHAUSTED" and exhausted.metrics.expansions==256 and exhausted.map==null
 var out={"status":"PASS" if checks.values().all(func(v):return v) else "FAIL","checks":checks,"timings":timings,"survivor":survivor}
 FileAccess.open(args[1],FileAccess.WRITE).store_string(DATA.canonical(out));print(JSON.stringify(checks));quit(0 if out.status=="PASS" else 1)
