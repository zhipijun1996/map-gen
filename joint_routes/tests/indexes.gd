extends SceneTree
const LOAD=preload("res://addons/mapgen/preload_job.gd")
const PREP=preload("res://addons/mapgen/prepared_library.gd")
const SOLVER=preload("res://addons/mapgen/solver.gd")
const BRANCH=preload("res://addons/mapgen/reward_branch_planner.gd")
const BRIDGE=preload("res://addons/mapgen/bridge_index.gd")
const JOINT=preload("res://addons/mapgen/joint_planner.gd")
const GEO=preload("res://addons/mapgen/geometry.gd")
const DATA=preload("res://addons/mapgen/data_json.gd")
const P=preload("res://addons/mapgen/protocol.gd")
class Gate extends RefCounted:
	func consume():return true

func brute_connected(item: Dictionary,occupied: Array) -> Dictionary:
	var selected: Dictionary={}
	for other in occupied:
		for pid in item.ports:
			for port in other.ports.values():
				if GEO.matching(item.ports[pid],port):selected[pid]=true
	return selected

func _initialize():
	var checks: Dictionary={};var positions:=0;var bridges:=0
	var loader=LOAD.create(OS.get_cmdline_user_args()[0],P.PACKAGE_SHA)
	while not loader.is_done():loader.advance(1)
	var loaded: Dictionary=loader.result()
	if loaded.status!="PASS":print(loaded);quit(2);return
	for capabilities in [["jump","shot_recoil"],["jump","double_jump","shot_recoil","grapple"]]:
		var req: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
		req.player.abilities=capabilities
		var cfg: Dictionary=DATA.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
		var prepared=PREP.new()
		if not prepared.begin(loaded.library,req,cfg):quit(2);return
		while not prepared.ready:prepared.advance_one()
		var gate=Gate.new();var s=SOLVER.new(gate,req,prepared,cfg)
		if not await s.initialize():quit(2);return
		var mids: Array=s.tids.keys()
		for i in range(8):
			s.add(s.make(mids[i],-40+i*12,-11+(i%2)*7,i%2==1))
		for item in s.items:s.reward_core[item.id]=true
		var planner=BRANCH.new(s)
		for front in GEO.frontier(s.items).slice(0,20):
			var rows: Array=s.index.get(GEO.OPPOSITE[front[2].face]+"/"+front[2].surface,[])
			for row in rows.slice(0,24):
				var delta: Array=[front[2].world2[0]-row[3].local2[0],front[2].world2[1]-row[3].local2[1]]
				if delta[0]%2 or delta[1]%2:continue
				var candidate: Dictionary=s.make(row[0],int(delta[0]/2),int(delta[1]/2),row[1],"probe")
				checks["position_"+str(positions)]=planner.actual_connected(candidate,s.items)==brute_connected(candidate,s.items)
				var expected:=false
				for p in candidate.ports.values():
					for t in planner.targets:
						if t[0].id!=front[0].id and GEO.permitted(p,"out") and GEO.matching(p,t[2]):expected=true
				checks["core_join_"+str(positions)]=planner.core_join(candidate,front[0].id)==expected
				positions+=1
		var index=BRIDGE.new(s)
		if not await index.build(planner.targets):quit(2);return
		var targets: Dictionary={}
		for target in planner.targets:targets[target[0].id+":"+str(target[2].world2)]=target[2]
		for key in index.rows:
			for row in index.rows[key]:
				var item: Dictionary=s.make(row.mid,row.x,row.y,row.mirror,"probe")
				var target: Dictionary=targets[row.target+":"+str(item.ports[row.exit].world2)]
				checks["bridge_"+str(bridges)]=GEO.matching(item.ports[row.exit],target) and item.ports[row.pin].world2==[key[2],key[3]] and GEO.OPPOSITE[item.ports[row.pin].face]==key[0] and item.ports[row.pin].surface==key[1]
				var declared:=false
				for route in s.transit[s.port_key(row.mid,row.mirror,row.pin)]:
					if route.to_port==row.exit and (not key[4] or not route.reward_ids.is_empty()):declared=true
				checks["declared_"+str(bridges)]=declared
				bridges+=1
	# Exhaustive small conflict graphs: coloring must never underestimate capacity.
	var joint=JOINT.new(null)
	for fixture in range(40):
		joint.conflicts=[]
		for i in range(8):joint.conflicts.append({i:true})
		for i in range(8):
			for j in range(i):
				if (i*31+j*17+fixture*13)%7<3:joint.conflicts[i][j]=true;joint.conflicts[j][i]=true
		var maximum:=0
		for mask in range(256):
			var chosen: Array=[];var valid:=true
			for i in range(8):
				if mask&(1<<i):
					for j in chosen:
						if joint.conflicts[i].has(j):valid=false
					chosen.append(i)
			if valid:maximum=maxi(maximum,chosen.size())
		checks["sound_capacity_"+str(fixture)]=joint.capacity_upper_bound(range(8))>=maximum
	var ok: bool=checks.values().all(func(v):return v)
	print(JSON.stringify({"status":"PASS" if ok else "FAIL","checks":checks.size(),"failed":checks.keys().filter(func(k):return not checks[k]),"position_cases":positions,"bridge_rows":bridges,"scope":"real module interfaces, both capability contexts, mirrors/negative positions; graph bound exhaustive small fixtures, no physics"}))
	quit(0 if ok else 1)
