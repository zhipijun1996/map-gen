extends RefCounted
## Derived two-room return motifs. Exact source Routes and local seal checks.
const GEO=preload("geometry.gd")
var solver_ref: WeakRef
var s:
	get:return solver_ref.get_ref()
var rows: Dictionary={}
var count:=0
func _init(solver):solver_ref=weakref(solver)

func build() -> bool:
	for mid in s.tids:
		for mirror in [false,true]:
			var room: Dictionary=s.make(mid,0,0,mirror,"local-T")
			for pin in room.ports:
				var exits: Dictionary={}
				for route in s.transit[s.port_key(mid,mirror,pin)]:
					if route.to_port==pin:continue
					for back in s.transit[s.port_key(mid,mirror,route.to_port)]:
						if back.to_port==pin:exits[route.to_port]=true
				for pid in exits:
					var cursor=s.candidates([room,pid,room.ports[pid]],s.return_rooms,[room])
					var row=await cursor.next()
					while row!=null:
						var reward: Dictionary=row[0];reward.id="local-Q"
						if await s.configuration_ok(room,{pin:true,pid:true}) and await s.configuration_ok(reward,{row[1]:true}):
							var key: Array=[GEO.OPPOSITE[room.ports[pin].face],room.ports[pin].surface]
							if not rows.has(key):rows[key]=[]
							rows[key].append({"entry":room.ports[pin],"chain":[room,reward]});count+=1
						row=await cursor.next()
					if s.aborted():return false
	return true

func instantiate(source: Array) -> Array:
	var rows_at_root: Array=[]
	var options: Array=rows.get([source[2].face,source[2].surface],[]).duplicate()
	s.rng.shuffle(options)
	for motif in options:
		if not await s.tick():return []
		var delta: Array=[source[2].world2[0]-motif.entry.local2[0],source[2].world2[1]-motif.entry.local2[1]]
		if delta[0]%2 or delta[1]%2:continue
		var chain: Array=[]
		var blocked:=false
		for original in motif.chain:
			var item: Dictionary=s.make(original.module_id,int(delta[0]/2)+original.origin[0],int(delta[1]/2)+original.origin[1],original.mirror_x,"M%02d" % (s.items.size()+chain.size()+1))
			for other in s.items:
				if GEO.overlap(item,other):blocked=true;break
			chain.append(item)
		if blocked or s.aspect(s.items+chain)>s.config.shape.max_aspect:continue
		rows_at_root.append({"chain":chain,"root":source})
	return rows_at_root
