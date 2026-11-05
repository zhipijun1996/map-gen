extends RefCounted
## Lazy candidates: lookahead next() must not evaluate or count later candidates.
const GEO = preload("geometry.gd")
var solver
var source: Array
var mids: Dictionary
var items: Array
var options: Array
var position := 0
var rectangles: Array = []

func _init(search, frontier: Array, module_ids: Dictionary, occupied: Array):
	solver = search
	source = frontier
	mids = module_ids
	items = occupied
	for item in occupied:
		rectangles.append([item.origin[0],item.origin[1],item.origin[0]+item.size_blocks[0],item.origin[1]+item.size_blocks[1]])
	options = solver.index.get(GEO.OPPOSITE[source[2].face] + "/" + source[2].surface, []) if GEO.permitted(source[2], "out") else []

func next():
	while position < options.size() and not solver.aborted():
		var row: Array = options[position]
		position += 1
		if not mids.has(row[0]):continue
		solver.observe(row[0],"indexed")
		if not GEO.permitted(row[3], "in"):
			solver.observe(row[0],"permission_rejected");continue
		var delta: Array = [source[2].world2[0]-row[3].local2[0], source[2].world2[1]-row[3].local2[1]]
		if delta[0]%2 or delta[1]%2:
			solver.observe(row[0],"parity_rejected");continue
		if not await solver.tick():
			return null
		var x: int = delta[0]/2
		var y: int = delta[1]/2
		var size: Array = solver.templates[row[0]].size_blocks
		var occupied := false
		for rect in rectangles:
			if x < rect[2] and rect[0] < x+size[0] and y < rect[3] and rect[1] < y+size[1]:
				occupied = true
				break
		if occupied:
			solver.observe(row[0],"overlap_rejected");continue
		solver.observe(row[0],"space_fit")
		# make() is pure allocation. Do not allocate/mirror Ports for rectangles
		# already rejected by the SAME strict overlap test and candidate tick.
		var item: Dictionary = solver.make(row[0], x, y, row[1])
		if item.module_id == "BOSS":
			solver.observe(row[0],"candidate");return [item, row[2]]
		var routes: Array = solver.transit[solver.port_key(item.module_id, item.mirror_x, row[2])]
		if routes.is_empty():
			solver.observe(row[0],"no_route_from_entry");solver.reject("no_route_from_actual_entry")
			continue
		var allowed := false
		for route in routes:
			if (item.reward and not route.reward_ids.is_empty()) or (not item.reward and route.to_port != row[2]):
				allowed = true
		if not allowed:
			solver.observe(row[0],"no_onward_or_reward_route")
			solver.reject("entry_has_no_reward_route" if item.reward else "no_onward_route_from_actual_entry")
			continue
		solver.observe(row[0],"candidate");return [item, row[2]]
	return null
