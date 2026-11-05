extends SceneTree
const DATA=preload("res://addons/mapgen_additions/data_json.gd")
const JOB=preload("res://addons/mapgen_additions/job.gd")
func _initialize():call_deferred("run")
func read(path: String):return DATA.parse(FileAccess.get_file_as_string(path)).value
func run():
	var args:=OS.get_cmdline_user_args()
	var source=read(args[0]);var config=read(args[1]);var shops=[] if args.size()<5 else read(args[4])
	var before: String=DATA.canonical(source).sha256_text()
	var start:=Time.get_ticks_usec();var job=JOB.create(source,config,shops);var create_usec: int=Time.get_ticks_usec()-start
	var batch: int=int(args[3]) if args.size()>=4 else 1
	while not job.is_done():job.advance(batch)
	var result: Dictionary=job.result()
	var output: Dictionary={"result":result,"profile":job.profile(),"creation_usec":create_usec,"source_unchanged":DATA.canonical(source).sha256_text()==before}
	FileAccess.open(args[2],FileAccess.WRITE).store_string(DATA.canonical(output));print(JSON.stringify({"status":result.status,"stats":result.get("stats"),"gaps":result.get("gaps",[]).size()}));quit(0 if result.status in ["PASS","PARTIAL"] and output.source_unchanged else 1)
