extends SceneTree
const PRELOAD = preload("res://addons/mapgen/preload_job.gd")
const P = preload("res://addons/mapgen/protocol.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
func _initialize():
	var args := OS.get_cmdline_user_args()
	var job = PRELOAD.create(args[0],P.PACKAGE_SHA)
	while not job.is_done():
		job.advance(1)
	var result: Dictionary = job.result()
	var report := {"status":result.status,"profile":job.profile()}
	if result.status == "PASS":
		report.checked_files = result.checked_files
		report.modules = result.library.read_json("catalog.json").value.modules.size()
	FileAccess.open(args[1],FileAccess.WRITE).store_string(DATA.canonical(report))
	print(JSON.stringify(report))
	quit(0 if result.status == "PASS" else 1)
