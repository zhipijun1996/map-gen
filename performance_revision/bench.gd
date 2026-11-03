extends Node
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
var active
var library
var mode:="cpu"
var seeds: Array=[930001,930007]
var seed_index:=0
var reloads_left:=0
var failure:=false
var stage:="preload"
var output:=""
var records: Array=[]
var stage_started:=0
var cpu_usec:=0
var calls:=0
var ticks:=0
var tick_max:=0
var step_times: Array=[]
var tick_times: Array=[]
var last_cancel: Dictionary={}
var config: Dictionary
var start_all:=Time.get_ticks_usec()
func _ready():
 if OS.has_feature("web"):
  var args=JSON.parse_string(JavaScriptBridge.eval("JSON.stringify(window.benchArgs||{})"))
  mode="framed";seeds=args.get("seeds",[930001,930007]);reloads_left=int(args.get("preloads",1))-1;failure=args.get("failure",false)
  JavaScriptBridge.eval('window.cancelIntent=null;document.addEventListener("keydown",e=>{if(e.key==="Escape")window.cancelIntent={intent_ms:e.timeStamp,handler_ms:performance.now(),trusted:e.isTrusted};});')
 else:
  var args:=OS.get_cmdline_user_args();output=args[0];mode=args[1]
 config=DATA.parse(FileAccess.get_file_as_string("res://inputs/generator_config.json")).value
 active=LOAD.create("res://inputs/modules.zip",P.PACKAGE_SHA);stage_started=Time.get_ticks_usec()
 if mode=="cpu":
  while active!=null:_drive()
func _process(_delta):
 if mode!="cpu" and active!=null:_drive()
func _drive():
 if OS.has_feature("web"):
  JavaScriptBridge.eval("window.benchStage="+JSON.stringify(stage)+";window.benchPhase="+JSON.stringify(active.phase_name()))
  var text=JavaScriptBridge.eval("window.cancelIntent?JSON.stringify(window.cancelIntent):''")
  if text is String and not text.is_empty():
   last_cancel=JSON.parse_string(text);last_cancel.observed_ms=JavaScriptBridge.eval("performance.now()")
   active.cancel();last_cancel.finished_ms=JavaScriptBridge.eval("performance.now()");last_cancel.input_to_done_ms=last_cancel.finished_ms-last_cancel.intent_ms
 var started:=Time.get_ticks_usec()
 var n:=0
 while n<128 and not active.is_done():
  var a:=Time.get_ticks_usec();active.advance(1);var elapsed:=Time.get_ticks_usec()-a;cpu_usec+=elapsed;step_times.append(elapsed);calls+=1;n+=1
  if mode!="cpu" and Time.get_ticks_usec()-started>=8000:break
 var tick_us:=Time.get_ticks_usec()-started
 ticks+=1;tick_times.append(tick_us);tick_max=maxi(tick_max,tick_us)
 if active.is_done():_finished()
func _finished():
 var wall:=Time.get_ticks_usec()-stage_started
 var t:=Time.get_ticks_usec();var result: Dictionary=active.result();var copy_us:=Time.get_ticks_usec()-t
 t=Time.get_ticks_usec();var host_copy: Dictionary=result.duplicate(true);var host_copy_us:=Time.get_ticks_usec()-t
 var profile: Dictionary=active.profile()
 var row={"stage":stage,"seed":seeds[seed_index] if stage=="generate" else null,"wall_usec":wall,"advance_cpu_usec":cpu_usec,"host_and_yield_usec":wall-cpu_usec,"advance_calls":calls,"ticks":ticks,"tick_max_usec":tick_max,"snapshot_usec":copy_us,"host_duplicate_usec":host_copy_us,"profile":profile,"cancel":last_cancel,"advance_distribution_usec":distribution(step_times),"tick_distribution_usec":distribution(tick_times)}
 if stage=="preload":
  row.status=result.status
  if result.status!="PASS":records.append(row);_done();return
  library=result.library
 else:
  row.result=result
  t=Time.get_ticks_usec();var encoded:=DATA.canonical(result);row.canonical_serialize_usec=Time.get_ticks_usec()-t;row.canonical_bytes=encoded.to_utf8_buffer().size()
  t=Time.get_ticks_usec();var native_json:=JSON.stringify(result,"",true,true);row.engine_serialize_usec=Time.get_ticks_usec()-t
  print("BENCH_GENERATED ",seeds[seed_index]," ",result.status," wall=",wall," cpu=",cpu_usec)
  seed_index+=1
 records.append(row)
 if stage=="preload" and reloads_left>0 and last_cancel.is_empty():
  reloads_left-=1;active=LOAD.create("res://inputs/modules.zip",P.PACKAGE_SHA)
  stage_started=Time.get_ticks_usec();cpu_usec=0;calls=0;ticks=0;tick_max=0;step_times=[];tick_times=[]
  return
 if seed_index>=seeds.size() or not last_cancel.is_empty():_done();return
 stage="generate";var req_path: String="res://inputs/conformance_request.json" if seeds[seed_index]==930001 else "res://inputs/gears_request_930007.json"
 if failure:req_path="res://inputs/failure_request.json"
 active=JOB.create(DATA.parse(FileAccess.get_file_as_string(req_path)).value,library,config)
 stage_started=Time.get_ticks_usec();cpu_usec=0;calls=0;ticks=0;tick_max=0;step_times=[];tick_times=[]
func _done():
 var report={"engine":Engine.get_version_info().string,"implementation":P.IMPLEMENTATION,"algorithm":P.ALGORITHM,"mode":mode,"soft_tick_usec":8000,"unit_cap":128,"advance_budget":1,"records":records,"wall_usec":Time.get_ticks_usec()-start_all,"host_scope":"standalone data scheduler, no game validation/assembly/physics/tools/screenshots"}
 active=null
 if OS.has_feature("web"):JavaScriptBridge.eval("window.benchReport="+JSON.stringify(report,"",true,true))
 else:FileAccess.open(output,FileAccess.WRITE).store_string(DATA.canonical(report));get_tree().quit()

func distribution(values: Array)->Dictionary:
 var sorted:=values.duplicate();sorted.sort()
 if sorted.is_empty():return {}
 return {"count":sorted.size(),"max":sorted[-1],"p50":sorted[int((sorted.size()-1)*0.50)],"p95":sorted[int((sorted.size()-1)*0.95)],"p99":sorted[int((sorted.size()-1)*0.99)]}
