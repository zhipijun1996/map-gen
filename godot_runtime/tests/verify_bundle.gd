extends SceneTree
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
func read(path: String):return DATA.parse(FileAccess.get_file_as_string(path)).value
func _initialize():
 var args:=OS.get_cmdline_user_args()
 if args.size()!=1:quit(2);return
 var manifest: Dictionary=read("res://manifest.json")
 var checks: Dictionary={}
 for name in manifest.files:checks["sha:"+name]=FileAccess.get_sha256("res://"+name)==manifest.files[name]
 var loader=LOAD.create(args[0],P.PACKAGE_SHA)
 while not loader.is_done():loader.advance(1)
 if loader.result().status!="PASS":print(loader.result());quit(2);return
 for sample in manifest.samples:
  var expected: Dictionary=read("res://"+sample.result)
  var job=JOB.create(read("res://"+sample.request),loader.result().library,read("res://"+sample.config))
  while not job.is_done():job.advance(1)
  var actual: Dictionary=job.result()
  actual.metrics.erase("generation_seconds");expected.metrics.erase("generation_seconds")
  checks[sample.id+":full_result"]=actual==expected
  checks[sample.id+":failure_empty"]=actual.status=="PASS" or actual.map==null and actual.content_store.is_empty()
 var ok: bool=checks.values().all(func(v):return v)
 print(JSON.stringify({"status":"PASS" if ok else "FAIL","checks":checks,"implementation":P.IMPLEMENTATION,"readiness":"candidate"}))
 quit(0 if ok else 1)
