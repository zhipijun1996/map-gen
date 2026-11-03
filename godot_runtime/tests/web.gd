extends Node
# Conformance HOST only; algorithm/preloader remain data RefCounted components.
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
var cases: Array=["preload-cancel","preload","generation-cancel","default-1","failure","default-17"]
var index:=0
var active
var library
var request: Dictionary
var config: Dictionary
var reports: Dictionary={}
var frame_max_usec:=0
const FRAME_TARGET_USEC:=8000

func _ready():
 request=DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
 config=DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
 JavaScriptBridge.eval('window.mapgenCancelInput=null; document.addEventListener("keydown",e=>{if(e.key==="Escape")window.mapgenCancelInput={intent_ms:e.timeStamp,handler_ms:performance.now(),trusted:e.isTrusted,case_id:window.mapgenCase};});')
 _start()

func _start():
 var name: String=cases[index]
 JavaScriptBridge.eval("window.mapgenCase="+JSON.stringify(name)+";window.mapgenCancelInput=null;")
 if name.begins_with("preload"):
  active=LOAD.create("res://tests/dependencies/modules.zip",P.PACKAGE_SHA)
 else:
  var req:=request.duplicate(true)
  if name=="failure":req.player.abilities=["jump"]
  active=JOB.create(req,library,config)
 frame_max_usec=0

func _process(_dt):
 if active==null:return
 var name: String=cases[index]
 JavaScriptBridge.eval("window.mapgenPhase="+JSON.stringify(active.phase_name()))
 var input_text=JavaScriptBridge.eval("window.mapgenCancelInput ? JSON.stringify(window.mapgenCancelInput) : ''")
 var cancellation: Dictionary={}
 if input_text is String and not input_text.is_empty() and name.ends_with("cancel"):
  cancellation=JSON.parse_string(input_text)
  cancellation.host_observed_ms=JavaScriptBridge.eval("performance.now()")
  active.cancel()
  cancellation.finished_ms=JavaScriptBridge.eval("performance.now()")
  cancellation.input_to_done_ms=cancellation.finished_ms-cancellation.intent_ms
  cancellation.queue_ms=cancellation.host_observed_ms-cancellation.intent_ms
 var start:=Time.get_ticks_usec()
 var deadline:=start+FRAME_TARGET_USEC
 while not active.is_done() and Time.get_ticks_usec()<deadline:
  active.advance(17 if name=="default-17" else 1)
 frame_max_usec=maxi(frame_max_usec,Time.get_ticks_usec()-start)
 if active.is_done():
  var snapshot_start:=Time.get_ticks_usec()
  var result: Dictionary=active.result()
  var snapshot_usec:=Time.get_ticks_usec()-snapshot_start
  if name=="preload" and result.status=="PASS":library=result.library
  if name.begins_with("preload"):
   result["has_library"]=result.has("library")
   result.erase("library")
  reports[name]={"result":result,"profile":active.profile(),"cancel":cancellation,"frame_max_usec":frame_max_usec,"result_snapshot_usec":snapshot_usec}
  active=null
  index+=1
  if index<cases.size():_start()
  else:
   var report={"cases":reports,"implementation":P.IMPLEMENTATION,"algorithm":P.ALGORITHM,"frame_target_usec":FRAME_TARGET_USEC,"engine":Engine.get_version_info().string,"module_sha256":FileAccess.get_sha256("res://tests/dependencies/modules.zip"),"request_sha256":FileAccess.get_sha256("res://tests/request.json"),"config_sha256":FileAccess.get_sha256("res://tests/config.json")}
   JavaScriptBridge.eval("window.mapgenReport="+JSON.stringify(report,"",true,true))
   print("MAPGEN_FINISHED")
