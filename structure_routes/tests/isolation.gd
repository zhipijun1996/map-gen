extends SceneTree
const A=preload("res://addons/mapgen/module_archive.gd")
const J=preload("res://addons/mapgen/generation_job.gd")
const D=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
func drain(job) -> Dictionary:
	while not job.is_done():job.advance(1)
	var result: Dictionary=job.result();result.metrics.erase("generation_seconds")
	return result
func _initialize():
	var args:=OS.get_cmdline_user_args()
	var archive=A.open_zip(args[0],P.PACKAGE_SHA)
	if not archive.ok:quit(2);return
	var request: Dictionary=D.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
	var config: Dictionary=D.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
	var baseline: Dictionary=drain(J.create(request,archive.library,config))
	var checks: Dictionary={"baseline_pass":baseline.status=="PASS"}
	var left_request: Dictionary=request.duplicate(true);left_request.seed=930007
	var left=J.create(left_request,archive.library,config)
	var right=J.create(request,archive.library,config)
	while not left.is_done() and left.phase_name()!="motif_catalog":
		left.advance(1);right.advance(1)
	left.advance(1);right.advance(1)
	checks.cancel_catalog_phase=left.phase_name()=="motif_catalog"
	left.cancel()
	checks.cancel_empty=left.result().status=="CANCELLED" and left.result().map==null and left.result().content_store.is_empty()
	checks.other_job_full_result=drain(right)==baseline
	checks.library_reusable_after_cancel=drain(J.create(request,archive.library,config))==baseline
	var mutable_config: Dictionary=config.duplicate(true)
	var snapshot=J.create(request,archive.library,mutable_config)
	mutable_config.topology.reward_modes[0]="forward_merge"
	checks.nested_config_snapshot=drain(snapshot)==baseline
	var invalid: Dictionary=config.duplicate(true);invalid.topology.reward_modes.pop_back()
	checks.mode_count_rejected=J.create(request,archive.library,invalid).result().status=="INVALID_INPUT"
	invalid=config.duplicate(true);invalid.topology.backbone_max=config.goals.growth_target+1
	checks.backbone_range_rejected=J.create(request,archive.library,invalid).result().status=="INVALID_INPUT"
	var ok: bool=checks.values().all(func(value):return value)
	var report: Dictionary={"status":"PASS" if ok else "FAIL","checks":checks,"scope":"same-thread real library sharing; cancel one job during motif derivation and finish another; no cross-Thread claim"}
	FileAccess.open(args[1],FileAccess.WRITE).store_string(D.canonical(report));print(JSON.stringify(report));quit(0 if ok else 1)
