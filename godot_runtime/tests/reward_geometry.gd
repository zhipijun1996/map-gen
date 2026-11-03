extends SceneTree
const GUARD=preload("res://addons/mapgen/reward_clearance.gd")
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const PREP=preload("res://addons/mapgen/prepared_library.gd")
const SOLVER=preload("res://addons/mapgen/solver.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
class Gate extends RefCounted:
 var work_phase: String=""
 func consume():return true
var checks: Dictionary={}
func _initialize():
 var seal: Array=[{"rect_pixels":[256,0,128,32]}]
 checks.orbit_full=(await GUARD.check([300,-10,80,56],seal,[12,18])).verdict=="PROVEN_EXCLUDED_BY_SEALS"
 checks.orbit_mirrored=(await GUARD.check([260,-10,80,56],seal,[12,18])).verdict=="PROVEN_EXCLUDED_BY_SEALS"
 checks.partial_is_unknown=(await GUARD.check([370,-10,80,56],seal,[12,18])).verdict=="NOT_PROVEN_EXCLUDED"
 checks.open_C=(await GUARD.check([300,-10,80,56],[],[12,18])).verdict=="NOT_PROVEN_EXCLUDED"
 checks.tangent_is_not_full_proof=(await GUARD.check([244,-10,80,56],seal,[12,18])).verdict=="NOT_PROVEN_EXCLUDED"
 checks.union_can_exclude=(await GUARD.check([0,0,10,10],[{"rect_pixels":[-2,-2,7,14]},{"rect_pixels":[4,-2,8,14]}],[1,1])).verdict=="PROVEN_EXCLUDED_BY_SEALS"
 checks.touching_union_has_unknown_line=(await GUARD.check([0,0,10,10],[{"rect_pixels":[-2,-2,6,14]},{"rect_pixels":[6,-2,6,14]}],[1,1])).verdict=="NOT_PROVEN_EXCLUDED"
 var args:=OS.get_cmdline_user_args()
 var loader=LOAD.create(args[0],P.PACKAGE_SHA)
 while not loader.is_done():loader.advance(1)
 var request=DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
 var config=DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
 var lib=PREP.new();lib.begin(loader.result().library,request,config)
 while not lib.ready:lib.advance_one()
 var gate=Gate.new()
 var solver=SOLVER.new(gate,request,lib,config);await solver.initialize()
 var item: Dictionary=solver.make("T:idea-orbit-choice-001",0,0,false,"probe")
 var selected: Dictionary={}
 for pid in item.ports:
  if pid!="C":selected[pid]=true
 checks.ordinary_no_route_reward_association=lib.templates[item.module_id].all_routes.all(func(r):return r.reward_ids.is_empty())
 checks.real_ordinary_rejected=not await solver.configuration_ok(item,selected)
 checks.real_C_open_allowed=await solver.configuration_ok(item,{"A":true,"B":true,"C":true})
 checks.ordinary_reason=solver.reward_seal_conflicts.any(func(r):return r.module_id=="idea-orbit-choice-001" and not r.target_reward)
 # Actual Q template, adverse explicit player size; does not change default cases.
 var target: Dictionary={}
 for mid in lib.templates:
  if mid.begins_with("Q") and lib.templates[mid].size_blocks[0]<8:
   target=solver.make(mid,0,0,false,"target-probe");break
 var big_request: Dictionary=request.duplicate(true);big_request.player.clearance_half_extents_pixels=[1000,1000]
 var big_lib=PREP.new();big_lib.begin(loader.result().library,big_request,config)
 while not big_lib.ready:big_lib.advance_one()
 var other=SOLVER.new(gate,big_request,big_lib,config);await other.initialize()
 checks.actual_target_rejected=not await other.configuration_ok(target,{})
 checks.target_reason=other.reward_seal_conflicts.any(func(r):return r.target_reward)
 var ok: bool=checks.values().all(func(v):return v)
 var report={"status":"PASS" if ok else "FAIL","checks":checks,"ordinary_proofs":solver.reward_seal_conflicts,"target_proofs":other.reward_seal_conflicts,"scope":"sufficient static impossibility; no physical playability proof"}
 FileAccess.open(args[1],FileAccess.WRITE).store_string(DATA.canonical(report));print(JSON.stringify({"status":report.status,"checks":checks}))
 quit(0 if ok else 1)
