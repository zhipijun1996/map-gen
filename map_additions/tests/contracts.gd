extends SceneTree
const DATA=preload("res://addons/mapgen_additions/data_json.gd")
const JOB=preload("res://addons/mapgen_additions/job.gd")
var checks: Dictionary={}
func _initialize():call_deferred("run")
func read(path: String):return DATA.parse(FileAccess.get_file_as_string(path)).value
func normalized(value: Dictionary) -> Dictionary:
	var v: Dictionary=value.duplicate(true);v.erase("metrics");return v
func drain(job,batch: int=1) -> Dictionary:
	while not job.is_done():
		var before: int=job.progress().operations;var value: Dictionary=job.advance(batch)
		checks["bounded_"+str(batch)]=checks.get("bounded_"+str(batch),true) and value.ok and value.progress.operations-before<=batch
	return job.result()
func run():
	var args:=OS.get_cmdline_user_args();var base=read(args[0]);var cfg=read(args[1]);var shops=read(args[2]);var real=read(args[3])
	var original: String=DATA.canonical(base);var ref: Dictionary=drain(JOB.create(base,cfg,shops))
	checks.fixture_complete=ref.status=="PASS" and ref.stats.decisions==1 and ref.stats.placed_decisions==1
	var view: Dictionary=ref.signs[0].views[0]
	var left: Dictionary={};var right: Dictionary={}
	for choice in view.directions:
		if choice.exit_port_id=="left":left=choice
		if choice.exit_port_id=="right":right=choice
	checks.exclusive_chest=left.categories==["chest"]
	checks.no_boss_via_return_to_junction=not "boss" in left.categories
	checks.shop_and_boss_on_right=right.categories==["boss","shop"]
	checks.existing_reward_reference=ref.targets.has("chest:C:cache")
	checks.shop_explicit_reference=ref.targets["shop:test-shop"].node_ids==["b-in"]
	for batch in [17,128,4096]:checks["batch_"+str(batch)]=normalized(drain(JOB.create(base,cfg,shops),batch))==normalized(ref)
	var source_copy: Dictionary=base.duplicate(true);var settings: Dictionary=cfg.duplicate(true)
	var snapshot=JOB.create(source_copy,settings,shops);source_copy.map.instances.clear();settings.signage.enabled=false;settings.moving_saws.enabled=false
	checks.snapshot_input=normalized(drain(snapshot))==normalized(ref)
	checks.base_unchanged=DATA.canonical(base)==original
	var returned: Dictionary=snapshot.result();returned.signs.clear();checks.result_detached=not snapshot.result().signs.is_empty()
	checks.invalid_advance=not snapshot.advance(0).ok and not snapshot.advance(4097).ok
	var bad: Dictionary=base.duplicate(true);bad.status="SEARCH_EXHAUSTED";bad.map=null;bad.content_store={}
	var failed=JOB.create(bad,cfg);checks.base_failure_rejected=failed.result().status=="INVALID_INPUT" and failed.result().signs.is_empty() and failed.result().moving_saws.is_empty()
	var invalid: Dictionary=cfg.duplicate(true);invalid.extra=true;checks.unknown_config_rejected=JOB.create(base,invalid).result().status=="INVALID_INPUT"
	var duplicate: Array=shops.duplicate(true);duplicate.append(duplicate[0].duplicate(true));checks.duplicate_shop_rejected=JOB.create(base,cfg,duplicate).result().status=="INVALID_INPUT"
	var wrong: Array=shops.duplicate(true);wrong[0].node_id="not-a-node";checks.shop_anchor_rejected=drain(JOB.create(base,cfg,wrong)).status=="INVALID_INPUT"
	var limited: Dictionary=cfg.duplicate(true);limited.budget.max_work_units=1;var budget: Dictionary=drain(JOB.create(base,limited));checks.budget_empty=budget.status=="BUDGET_EXHAUSTED" and budget.signs.is_empty() and budget.moving_saws.is_empty()
	var unseen=JOB.create(base,cfg,shops);unseen.cancel();checks.cancel_created=unseen.result().status=="CANCELLED" and unseen.result().signs.is_empty()
	var real_ref: Dictionary=drain(JOB.create(real,cfg))
	for batch in [17,128]:checks["real_batch_"+str(batch)]=normalized(drain(JOB.create(real,cfg),batch))==normalized(real_ref)
	var signs_off: Dictionary=cfg.duplicate(true);signs_off.signage.enabled=false
	var hazards_only: Dictionary=drain(JOB.create(real,signs_off));checks.sign_toggle_preserves_saws=hazards_only.moving_saws==real_ref.moving_saws and hazards_only.signs.is_empty()
	var saws_off: Dictionary=cfg.duplicate(true);saws_off.moving_saws.enabled=false
	var signs_only: Dictionary=drain(JOB.create(real,saws_off));checks.saw_toggle_preserves_signs=signs_only.signs==real_ref.signs and signs_only.moving_saws.is_empty()
	for phase in ["index","geometry","targets","sign_analysis","sign_placement","boundary_candidates","moving_saw_selection"]:
		var job=JOB.create(real,cfg)
		while not job.is_done() and job.phase_name()!=phase:job.advance(1)
		checks["reachable_"+phase]=not job.is_done()
		if not job.is_done():job.cancel()
		var result: Dictionary=job.result();checks["cancel_"+phase]=result.status=="CANCELLED" and result.signs.is_empty() and result.moving_saws.is_empty()
	# Export is a measured atomic copy/hash, not an observable cancellation window.
	checks.completed_cancel_is_noop=true
	var finished=JOB.create(base,cfg,shops);var completed: Dictionary=drain(finished);finished.cancel()
	checks.completed_cancel_is_noop=normalized(finished.result())==normalized(completed)
	var a=JOB.create(real,cfg);var b=JOB.create(real,cfg)
	for _n in range(5):a.advance(1);b.advance(1)
	a.cancel();checks.cancel_isolation=normalized(drain(b))==normalized(real_ref)
	var ok: bool=checks.values().all(func(value):return value)
	var report: Dictionary={"status":"PASS" if ok else "FAIL","checks":checks,"scope":"synthetic graph logic + supplied real generated map; no actual shop module, gameplay or physics certification"}
	FileAccess.open(args[4],FileAccess.WRITE).store_string(DATA.canonical(report));print(JSON.stringify(report));quit(0 if ok else 1)
