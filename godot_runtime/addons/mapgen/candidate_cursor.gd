extends RefCounted
## Lazy candidates: lookahead next() must not evaluate or count later candidates.
const GEO = preload("geometry.gd")
var solver
var source: Array
var mids: Dictionary
var items: Array
var options: Array
var position := 0

func _init(search, frontier: Array, module_ids: Dictionary, occupied: Array):
	solver = search
	source = frontier
	mids = module_ids
	items = occupied
	options = solver.index.get(GEO.OPPOSITE[source[2].face] + "/" + source[2].surface, []) if GEO.permitted(source[2], "out") else []

func next():
	while position < options.size() and not solver.aborted():
		var row: Array = options[position]
		position += 1
		if not mids.has(row[0]) or not GEO.permitted(row[3], "in"):
			continue
		var delta: Array = [source[2].world2[0]-row[3].local2[0], source[2].world2[1]-row[3].local2[1]]
		if delta[0]%2 or delta[1]%2:
			continue
		if not await solver.tick():
			return null
		var item: Dictionary = solver.make(row[0], delta[0]/2, delta[1]/2, row[1])
		var occupied := false
		for other in items:
			if GEO.overlap(item, other):
				occupied = true
				break
		if occupied:
			continue
		if item.module_id == "BOSS":
			return [item, row[2]]
		var routes: Array = solver.transit[solver.port_key(item.module_id, item.mirror_x, row[2])]
		if routes.is_empty():
			solver.reject("no_route_from_actual_entry")
			continue
		var allowed := false
		for route in routes:
			if (item.reward and not route.reward_ids.is_empty()) or (not item.reward and route.to_port != row[2]):
				allowed = true
		if not allowed:
			solver.reject("entry_has_no_reward_route" if item.reward else "no_onward_route_from_actual_entry")
			continue
		return [item, row[2]]
	return null
