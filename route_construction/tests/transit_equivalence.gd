extends SceneTree
const A=preload("res://addons/mapgen/module_archive.gd")
const P=preload("res://addons/mapgen/prepared_library.gd")
const S=preload("res://addons/mapgen/solver.gd")
const I=preload("res://addons/mapgen/transit_index.gd")
const D=preload("res://addons/mapgen/data_json.gd")
const GEO=preload("res://addons/mapgen/geometry.gd")
class Gate:
	extends RefCounted
	func consume():return true
func _initialize():call_deferred("run")
func signature(item: Dictionary) -> String:
	return D.canonical([item.module_id,item.mirror_x,item.origin])
func run():
	var args:=OS.get_cmdline_user_args()
	var opened=A.open_zip(args[0],preload("res://addons/mapgen/protocol.gd").PACKAGE_SHA)
	if not opened.ok:quit(2);return
	var r: Dictionary=D.parse(FileAccess.get_file_as_string("res://tests/request.json")).value
	var c: Dictionary=D.parse(FileAccess.get_file_as_string("res://tests/config.json")).value
	var prepared=P.new();prepared.begin(opened.library,r,c)
	while not prepared.ready:prepared.advance_one()
	var gate=Gate.new();var s=S.new(gate,r,prepared,c);await s.initialize()
	var index=I.new(s);await index.build()
	var checks: Dictionary={};var n:=0
	for key in index.entries:
		var legs: Array=index.entries[key]
		for leg in [legs[0],legs[-1]]:
			for shift in [[-12,-8],[14,-22]]:
				var front: Dictionary={"face":GEO.OPPOSITE[leg.entry.face],"surface":leg.entry.surface,"world2":[leg.entry.local2[0]+shift[0],leg.entry.local2[1]+shift[1]],"permission":"INOUT"}
				var target: Dictionary={"face":GEO.OPPOSITE[leg.out.face],"surface":leg.out.surface,"world2":[leg.out.local2[0]+shift[0],leg.out.local2[1]+shift[1]],"permission":"INOUT"}
				var source: Array=[{},"source",front];var goal: Array=[{},"goal",target]
				var actual: Dictionary={}
				for chain in await index.chains(source,goal,[],1,10000):
					if chain.size()==1:actual[signature(chain[0])]=true
				var expected: Dictionary={}
				var cursor=s.candidates(source,s.tids,[]);var row=await cursor.next()
				while row!=null:
					var item: Dictionary=row[0]
					for route in s.transit[s.port_key(item.module_id,item.mirror_x,row[1])]:
						if route.to_port==row[1] or not GEO.matching(item.ports[route.to_port],target):continue
						if await s.configuration_ok(item,{row[1]:true,route.to_port:true}):expected[signature(item)]=true
					row=await cursor.next()
				checks[str(n)]=actual==expected;n+=1
	var ok: bool=checks.values().all(func(value):return value)
	var report: Dictionary={"status":"PASS" if ok else "FAIL","checks":checks,"fixtures":n,"compiled_legs":index.count,"scope":"lookup vs independent original candidate enumeration and actual Route/seal predicates; real library, negative positions, mirrors and all indexed face/surface types"}
	FileAccess.open(args[1],FileAccess.WRITE).store_string(D.canonical(report));print(JSON.stringify(report));quit(0 if ok else 1)
