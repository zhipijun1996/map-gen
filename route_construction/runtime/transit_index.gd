extends RefCounted
## Exact directed one-leg signatures; two-leg matching is a meet-in-the-middle query.
const GEO=preload("geometry.gd")
var ref: WeakRef
var s:
	get:return ref.get_ref()
var exact: Dictionary={}
var entries: Dictionary={}
var count:=0
func _init(solver):ref=weakref(solver)
func build() -> bool:
	for mid in s.tids:
		for mirror in [false,true]:
			var ports: Dictionary=s.local[s.local_key(mid,mirror)]
			var seen: Dictionary={}
			for pin in ports:
				for route in s.transit[s.port_key(mid,mirror,pin)]:
					var pout: String=route.to_port
					if pin==pout or seen.has([pin,pout]):continue
					seen[[pin,pout]]=true
					if not await s.tick():return false
					var item: Dictionary=s.make(mid,0,0,mirror)
					if not await s.configuration_ok(item,{pin:true,pout:true}):continue
					var a: Dictionary=ports[pin];var b: Dictionary=ports[pout]
					var leg: Dictionary={"mid":mid,"mirror":mirror,"pin":pin,"pout":pout,"entry":a,"out":b,"delta":[b.local2[0]-a.local2[0],b.local2[1]-a.local2[1]]}
					var start: Array=[GEO.OPPOSITE[a.face],a.surface]
					var key: Array=start+[GEO.OPPOSITE[b.face],b.surface,leg.delta[0],leg.delta[1]]
					if not entries.has(start):entries[start]=[]
					if not exact.has(key):exact[key]=[]
					entries[start].append(leg);exact[key].append(leg);count+=1
	return true
func place(leg: Dictionary,front: Dictionary,occupied: Array):
	if not await s.tick():return null
	var delta: Array=[front.world2[0]-leg.entry.local2[0],front.world2[1]-leg.entry.local2[1]]
	if delta[0]%2 or delta[1]%2:return null
	var item: Dictionary=s.make(leg.mid,int(delta[0]/2),int(delta[1]/2),leg.mirror)
	for other in occupied:
		if GEO.overlap(item,other):return null
	return item
func tails(front: Dictionary,target: Dictionary) -> Array:
	return exact.get([front.face,front.surface,target.face,target.surface,target.world2[0]-front.world2[0],target.world2[1]-front.world2[1]],[])
func chains(source: Array,target: Array,occupied: Array,depth: int,limit: int) -> Array:
	s.construction_stats.bypass_queries+=1
	var results: Array=[]
	if GEO.matching(source[2],target[2]):results.append([])
	for leg in tails(source[2],target[2]):
		var item=await place(leg,source[2],occupied)
		if item!=null:results.append([item])
		if results.size()>=limit:return results
	if depth<2:return results
	for first in entries.get([source[2].face,source[2].surface],[]):
		var middle: Dictionary=first.out.duplicate()
		middle.world2=[source[2].world2[0]+first.delta[0],source[2].world2[1]+first.delta[1]]
		var last: Array=tails(middle,target[2])
		if last.is_empty():continue
		var a=await place(first,source[2],occupied)
		if a==null:continue
		for second in last:
			var b=await place(second,middle,occupied+[a])
			if b!=null:results.append([a,b])
			if results.size()>=limit:return results
		if s.aborted():return []
	return results
