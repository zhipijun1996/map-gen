extends SceneTree
## Diagnostic only. Exhaustive LOCAL Port subsets, not global placement/physics.
const LOAD = preload("res://addons/mapgen/preload_job.gd")
const PREP = preload("res://addons/mapgen/prepared_library.gd")
const SOLVER = preload("res://addons/mapgen/solver.gd")
const DATA = preload("res://addons/mapgen/data_json.gd")
const GEO = preload("res://addons/mapgen/geometry.gd")
const P = preload("res://addons/mapgen/protocol.gd")
class Gate extends RefCounted:
	func consume(): return true

func _initialize():
	var args := OS.get_cmdline_user_args()
	var loader = LOAD.create(args[0],P.PACKAGE_SHA)
	while not loader.is_done(): loader.advance(1000)
	var loaded: Dictionary = loader.result()
	if loaded.status != "PASS":
		push_error(str(loaded)); quit(2); return
	var config: Dictionary = DATA.parse(FileAccess.get_file_as_string(args[2])).value
	var contexts: Dictionary = {}
	for index in [1,3]:
		var request: Dictionary = DATA.parse(FileAccess.get_file_as_string(args[index])).value
		var prepared = PREP.new()
		if not prepared.begin(loaded.library,request,config):
			push_error(prepared.error); quit(2); return
		while not prepared.ready: prepared.advance_one()
		assert(prepared.error.is_empty())
		var gate = Gate.new()
		var solver = SOLVER.new(gate,request,prepared,config)
		if not await solver.initialize():
			push_error(solver.error_message); quit(2); return
		var rows: Dictionary = {}
		for mid in solver.templates:
			var template: Dictionary = solver.templates[mid]
			var source: String = template.source_module_id
			if not rows.has(source): rows[source] = {}
			if mid in ["START","BOSS"]:
				rows[source][mid] = {"bound_terminal":true}
				continue
			var checked := 0
			var passing := 0
			var candidate_entries := 0
			var witness: Dictionary = {}
			for mirror in [false,true]:
				var item: Dictionary = solver.make(mid,0,0,mirror,"probe")
				var pins: Array = item.ports.keys()
				for mask in range(1,1 << pins.size()):
					var selected: Dictionary = {}
					for k in range(pins.size()):
						if mask & (1 << k): selected[pins[k]] = true
					var possible: Array = []
					for pin in selected:
						if not GEO.permitted(item.ports[pin],"in"): continue
						for route in solver.transit[solver.port_key(mid,mirror,pin)]:
							if selected.has(route.to_port) and ((item.reward and not route.reward_ids.is_empty()) or (not item.reward and route.to_port != pin)):
								possible.append({"entry":pin,"exit":route.to_port})
					if possible.is_empty(): continue
					candidate_entries += possible.size()
					checked += 1
					if await solver.configuration_ok(item,selected):
						passing += 1
						if witness.is_empty(): witness = {"mirror_x":mirror,"connected_ports":selected.keys(),"route":possible[0]}
			rows[source]["target_reward" if item_role(mid) else "traversal"] = {"candidate_route_subset_pairs":candidate_entries,"checked_subsets":checked,"passing_subsets":passing,"witness":witness}
		contexts["regression_four_abilities" if index == 1 else "controller_two_abilities"] = {"request_path":args[index],"request":request,"modules":rows}
	FileAccess.open(args[4],FileAccess.WRITE).store_string(DATA.canonical({"scope":"exhaustive local connected-Port subsets; no neighbors, world reachability, search score or physics proof","module_sha256":P.PACKAGE_SHA,"contexts":contexts}))
	quit()

func item_role(mid: String) -> bool:
	return mid.begins_with("Q:")
