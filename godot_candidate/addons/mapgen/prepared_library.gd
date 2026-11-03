extends RefCounted
## Request-local aliases, same insertion order and source data as Python 0.2.0.
const GEO = preload("geometry.gd")
var source
var request: Dictionary
var config: Dictionary
var catalog: Dictionary
var entries: Dictionary = {}
var templates: Dictionary = {}
var abilities: Dictionary = {}
var block_pixels := 0
var error := ""
var _pending: Array = []
var _position := 0
var ready := false
var air_entries: Dictionary = {}
var air_returns: Dictionary = {}

static func native_ability(value: String) -> String:
	return "recoil" if value == "shot_recoil" else value

func begin(archive, req: Dictionary, cfg: Dictionary) -> bool:
	source = archive
	request = req.duplicate(true)
	config = cfg.duplicate(true)
	var parsed: Dictionary = source.read_json("catalog.json")
	if not parsed.ok or parsed.value.get("schema") != "map-edit/delivery-catalog/v1":
		error = "library: unsupported catalog"
		return false
	catalog = parsed.value
	for ability in request.player.abilities:
		if ability != "move":
			abilities[native_ability(ability)] = true
	var available: Dictionary = {}
	var regions: Dictionary = {}
	for entry in catalog.modules:
		if available.has(entry.id):
			error = "library: duplicate module:" + entry.id
			return false
		available[entry.id] = true
		regions[entry.region] = true
	for field in ["include_ids", "exclude_ids", "regions"]:
		for id in request.module_filter[field]:
			if not (regions if field == "regions" else available).has(id):
				error = "request.module_filter.%s: unknown %s" % [field, id]
				return false
	for entry in catalog.modules:
		var filter: Dictionary = request.module_filter
		if not filter.regions.is_empty() and not entry.region in filter.regions or not filter.include_ids.is_empty() and not entry.id in filter.include_ids or entry.id in filter.exclude_ids:
			continue
		if block_pixels and block_pixels != entry.blockSize:
			error = "library: mixed Block sizes"
			return false
		block_pixels = entry.blockSize
		entries[entry.id] = entry
	if block_pixels <= 0 or block_pixels%2 or config.seals.thickness_pixels >= block_pixels:
		error = "library: invalid Block size/seal thickness"
		return false
	for role in ["start", "boss"]:
		var binding: Dictionary = request.terminals[role]
		if not entries.has(binding.module_id):
			error = "request.terminals.%s: module absent or filtered out" % role
			return false
		var entry: Dictionary = entries[binding.module_id]
		var chosen: Dictionary = {}
		for port in entry.ports:
			if port.id == binding.port_id:
				chosen = port
		if chosen.is_empty() or not GEO.permitted(chosen, "out" if role == "start" else "in"):
			error = "request.terminals.%s: unknown/incompatible Port" % role
			return false
		if role == "boss" and (entry.purpose != "boss_arena" or not binding.port_id in entry.entryPortIds):
			error = "request.terminals.boss: not declared Boss arrival"
			return false
	for entry in entries.values():
		if entry.id not in [request.terminals.start.module_id, request.terminals.boss.module_id]:
			_pending.append(["T:" + entry.id, entry, {}])
	for row in [["START", "R", "start"], ["BOSS", "L", "boss"]]:
		var binding: Dictionary = request.terminals[row[2]]
		var entry: Dictionary = entries[binding.module_id]
		var aliases: Dictionary = {binding.port_id: row[1]}
		var native_ids: Array = []
		for port in entry.ports:
			native_ids.append(port.id)
		if row[1] in native_ids and row[1] != binding.port_id:
			var unused: String = "__source_" + row[1]
			while unused in native_ids:
				unused = "_" + unused
			aliases[row[1]] = unused
		_pending.append([row[0], entry, aliases])
	return true

func advance_one() -> void:
	if ready or not error.is_empty():
		return
	if _position < _pending.size():
		var row: Array = _pending[_position]
		_position += 1
		var template := adapt(row[0], row[1], row[2])
		if not error.is_empty():
			return
		if row[0] in ["START", "BOSS"]:
			var port_id := "R" if row[0] == "START" else "L"
			template.ports = template.all_ports.filter(func(p): return p.id == port_id)
			template.routes = template.all_routes.filter(func(r): return r.from_port == port_id and r.to_port == port_id)
			templates[row[0]] = template
		else:
			var rewarded := false
			for route in template.routes:
				if not route.reward_ids.is_empty():
					rewarded = true
			if template.ports.size() > 1 or not rewarded:
				templates[template.id] = template
			if rewarded:
				var reward: Dictionary = template.duplicate()
				reward.id = "Q:" + row[1].id
				reward.reward = true
				templates[reward.id] = reward
		return
	for field in ["entry_module_ids", "return_module_ids"]:
		for mid in request.air_loop[field]:
			var key: String = "T:" + mid
			if not templates.has(key):
				error = "request.air_loop.%s: unavailable traversal module:%s" % [field, mid]
				return
			var ports: Dictionary = GEO.placed_ports(templates[key], 0, 0, false)
			var surfaces: Array = ["ROCK", "AIR"] if field == "entry_module_ids" else ["AIR", "ROCK"]
			var found := false
			for route in templates[key].routes:
				if [ports[route.from_port].surface, ports[route.to_port].surface] == surfaces:
					found = true
			if not found:
				error = "request.air_loop.%s: missing declared Route:%s" % [field, mid]
				return
			(air_entries if field == "entry_module_ids" else air_returns)[key] = true
	ready = true

func adapt(key: String, entry: Dictionary, aliases: Dictionary) -> Dictionary:
	var compiled: Dictionary = source.read_json(entry.compiled)
	var note: Dictionary = source.read_json(entry.scene.replace("module.tscn", "module.mapnote.json"))
	if not compiled.ok or not note.ok or entry.reward_sites != compiled.value.get("reward_sites", []):
		error = "library: compiled/reward/mapnote mismatch:" + entry.id
		return {}
	var ports: Array = []
	var by_id: Dictionary = {}
	for original in entry.ports:
		var xy = original.position
		if xy is Dictionary:
			xy = [xy.x, xy.y]
		var local2: Array = []
		for k in range(2):
			var position = xy[k]-entry.bounds["x" if k == 0 else "y"]
			if position*2 % block_pixels:
				error = "library: non-Block Port:" + entry.id
				return {}
			local2.append(int(position*2/block_pixels))
		var port := {"id": aliases.get(original.id, original.id), "source_port_id": original.id, "face": original.face, "surface": original.surface, "permission": original.permission, "local2": local2, "closure": "gear-seal/1"}
		if by_id.has(port.id):
			error = "library: duplicate Port alias:" + entry.id
			return {}
		ports.append(port)
		by_id[port.id] = port
	var objects: Dictionary = {}
	for object in note.value.objects:
		objects[object.id] = object
	var reward_ids: Array = []
	for site in entry.reward_sites:
		reward_ids.append(site.id)
	var routes: Array = []
	for original in entry.routes:
		var a = aliases.get(original.from, original.from)
		var b = aliases.get(original.to, original.to)
		if not by_id.has(a) or not by_id.has(b):
			error = "library: unknown Route Port:" + entry.id
			return {}
		var required: Array = original.get("resourceProfile", {}).get("requiredRewards", [])
		for rid in required:
			if not rid in reward_ids:
				error = "library: unknown Route reward:" + entry.id
				return {}
		var caps: Array = []
		for ability in original.validation.availableAbilities:
			if ability != "move":
				caps.append(native_ability(ability))
		var points: Array = []
		for point in objects.get(original.get("pathObjectId", ""), {}).get("points", []):
			points.append([point.x-entry.bounds.x, point.y-entry.bounds.y])
		routes.append({"id": original.id, "from_port": a, "to_port": b, "displacement": [float(by_id[b].local2[0]-by_id[a].local2[0])/2.0, float(by_id[b].local2[1]-by_id[a].local2[1])/2.0], "required_abilities": caps, "action_tags": original.get("actionTags", []), "difficulty": original.difficulty.get("score"), "resource_profile": original.get("resourceProfile", {}), "validation": original.validation, "reward_ids": required, "path_points": points})
	return {"id": key, "name": entry.title, "size_blocks": entry.sizeBlocks, "ports": ports, "routes": routes, "all_ports": ports, "all_routes": routes, "allow_mirror_x": true, "reward": false, "source_module_id": entry.id, "content_version": entry.contentVersion, "scene": entry.scene, "scene_origin_offset": entry.sceneOriginOffsetPixels, "compiled_content": compiled.value, "source_bounds": entry.bounds}

func gear_seal(port: Dictionary, size: Array) -> Dictionary:
	var half: float = float(block_pixels)/2.0
	var x: float = port.local2[0]*half
	var y: float = port.local2[1]*half
	var width: int = size[0]*block_pixels
	var height: int = size[1]*block_pixels
	var thickness = config.seals.thickness_pixels
	var rect: Array = {"LEFT": [0, y-half, thickness, block_pixels], "RIGHT": [width-thickness, y-half, thickness, block_pixels], "TOP": [x-half, 0, block_pixels, thickness], "BOTTOM": [x-half, height-thickness, block_pixels, thickness]}[port.face]
	return {"port_id": port.id, "component": "gear-seal/1", "face": port.face, "rect_pixels": rect, "opening_pixels": block_pixels, "thickness_pixels": thickness, "certified": false, "physical_validation": "NOT_RUN"}

func clearance_rect(rect: Array) -> Array:
	var clearance: Array = request.player.clearance_half_extents_pixels
	return [rect[0]-clearance[0], rect[1]-clearance[1], rect[2]+2*clearance[0], rect[3]+2*clearance[1]]
