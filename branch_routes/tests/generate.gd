extends SceneTree
## Standalone data CLI; the algorithm itself does not depend on this SceneTree.
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const JOB=preload("res://addons/mapgen/generation_job.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
func _initialize():
	var args:=OS.get_cmdline_user_args()
	if args.size()!=4:
		print("module.zip request.json config.json result.json");quit(2);return
	var request: Dictionary=DATA.parse(FileAccess.get_file_as_string(args[1]))
	var config: Dictionary=DATA.parse(FileAccess.get_file_as_string(args[2]))
	if not request.ok or not config.ok:
		print("invalid input JSON");quit(2);return
	var loader=LOAD.create(args[0],P.PACKAGE_SHA)
	while not loader.is_done():loader.advance(1)
	var loaded: Dictionary=loader.result()
	if loaded.status!="PASS":print(loaded);quit(2);return
	var job=JOB.create(request.value,loaded.library,config.value)
	while not job.is_done():job.advance(1)
	var result: Dictionary=job.result()
	var output=FileAccess.open(args[3],FileAccess.WRITE)
	if output==null:print("cannot write result");quit(2);return
	output.store_string(DATA.canonical(result))
	print(JSON.stringify({"status":result.status,"implementation":P.IMPLEMENTATION,"output":args[3]}))
	quit(0 if result.status=="PASS" else 1)
