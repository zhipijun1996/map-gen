class_name RuntimeMapV2Provider
extends RefCounted
## Pure admission/conversion of selected, already-materialized v2 content.
## The caller verifies frozen file bytes; LevelRuntime owns all actual nodes.
const SCHEMA := "mapgen/runtime-map/v2"
const CONTENT_SCHEMA := "pcg/compiled-module-content/v1"
const PORT_PERMISSIONS: Array[String] = ["INPUT", "OUTPUT", "INOUT"]
const IDENTITY_SCHEMA := "gunman-rush/runtime-map-load/v1"
const ADAPTER_VERSION := "runtime-map-v2-slice/2"
const EMPTY_FIELDS: Array[String] = ["wall_platform_indices","hazards","thorns","saws","hooks","latches","enemies","reward_sites"]
const CONTENT_FIELDS: Array[String] = ["platforms","one_way_platform_indices","wall_platform_indices","hazards","thorns","saws","moving_platforms","hooks","latches","enemies","reward_sites","approved_hq_cells","schema","source_sha256","stable_id","world_bounds","entry_port","exit_port","coordinate_frame","source_affine"]
const ELLIPSE_FIELDS: Array[String] = ["platform_id","trajectory_kind","start","finish","size","travel_duration","dwell_duration","initial_phase","ellipse_center","ellipse_radii","ellipse_period","ellipse_x_sign"]

static func load_level(request: LevelRequest, map: Dictionary, content_store: Dictionary, selected_ids: Array[String], spawn: Vector2, source_sha256: String, bindings: Dictionary, source_record: Dictionary, binding_id: String = "seam") -> LevelBuildResult:
	if request == null or request.tuning == null or request.region_id.is_empty(): return _reject("request: missing tuning or region_id")
	if not spawn.is_finite(): return _reject("spawn: nonfinite player body center")
	if not _hash(source_sha256): return _reject("source_sha256: expected frozen SHA256")
	if map.get("schema") != SCHEMA: return _reject("map.schema: unsupported protocol")
	# Host seeds must be exact JSON integers (IEEE-754 safe range).
	if not _number(map.get("seed")) or absf(float(map.seed)) > 9007199254740991.0 or float(map.seed) != floorf(float(map.seed)): return _reject("map.seed: expected exact integer within JSON safe range")
	var seed := str(int(map.seed))
	if request.root_seed != seed: return _reject("map.seed/request.root_seed: expected matching canonical integer seed")
	if not map.get("generator") is Dictionary: return _reject("map.generator: missing implementation")
	var generator: Dictionary = map.generator
	if not _identity(generator.get("implementation")) or not _identity(generator.get("algorithm")): return _reject("map.generator: invalid implementation/algorithm")
	if not _hash(generator.get("request_fingerprint")): return _reject("map.generator.request_fingerprint: invalid upstream input fingerprint")
	if not map.get("module_package") is Dictionary or not _hash(map.module_package.get("sha256")) or not _identity(map.module_package.get("version")): return _reject("map.module_package: invalid library identity")
	if not source_record.get("files") is Dictionary or source_record.files.get("map.json") != source_sha256 or source_record.get("library_sha256") != map.module_package.sha256: return _reject("source_record: missing/mismatched verified map or library bytes")
	if source_record.get("protocol") != SCHEMA or not _identity(source_record.get("mapgen_commit")): return _reject("source_record: missing protocol/implementation source")
	for name: String in ["bindings.json","selection.json"]:
		if not _hash(source_record.files.get(name)): return _reject("source_record.files: missing verified SHA256 for "+name)
	if bindings.get("schema") != "gunman-rush/runtime-map-bindings/v1" or not _identity(bindings.get("version")): return _reject("bindings: missing schema/version")
	if not bindings.get("spawns") is Dictionary or not _pair(bindings.spawns.get(binding_id)) or _point(bindings.spawns[binding_id]) != spawn: return _reject("bindings.spawns: active binding differs from actual spawn")
	if not map.get("coordinates") is Dictionary: return _reject("map.coordinates: missing materialized frame")
	var coordinates: Dictionary = map.coordinates
	if coordinates.get("block_size_pixels") != 128 or coordinates.get("axes") != "x_right_y_down" or coordinates.get("local_frame") != "owned_rectangle_pixels" or coordinates.get("content_transform_applied") != true or coordinates.get("placement_rule") != "world_pixel = origin_blocks * block_size_pixels + local_pixel":
		return _reject("map.coordinates: unsupported materialization/placement contract")
	if not map.get("instances") is Array or not map.get("connections") is Array: return _reject("map.instances/connections: expected arrays")
	if selected_ids.is_empty(): return _reject("selected_instance_ids: empty selection")
	var selected: Dictionary = {}
	for id: String in selected_ids:
		if id.is_empty() or id != id.validate_node_name() or selected.has(id): return _reject("selected_instance_ids: invalid/duplicate "+id)
		selected[id] = true
	var instances: Dictionary = {}
	for raw: Variant in map.instances:
		if not raw is Dictionary or not _identity(raw.get("id")): return _reject("map.instances.id: invalid instance identity")
		if instances.has(raw.id): return _reject("map.instances."+str(raw.id)+": duplicate instance")
		instances[raw.id] = raw
	var ids: Array[String] = selected_ids.duplicate()
	ids.sort()
	if not bindings.get("selected_instances") is Array or bindings.selected_instances.size() != ids.size(): return _reject("bindings.selected_instances: selected scope differs")
	var binding_ids: Array[String] = []
	for value: Variant in bindings.selected_instances:
		if not value is String: return _reject("bindings.selected_instances: invalid identity")
		binding_ids.append(value)
	binding_ids.sort()
	if binding_ids != ids: return _reject("bindings.selected_instances: selected scope differs")
	var plan := LevelPlan.new()
	plan.region_id = request.region_id
	plan.map_index = request.map_index
	plan.source_id = &"mapgen_runtime_v2"
	plan.source_version = SCHEMA+"/"+str(generator.implementation)+"/"+str(generator.algorithm)
	plan.seed = seed
	plan.spawn = spawn
	for id: String in ids:
		if not instances.has(id): return _reject("instances."+id+": selected instance missing")
		var instance: Dictionary = instances[id]
		var problem := _instance_error(instance)
		if not problem.is_empty(): return _reject("instances."+id+"."+problem)
		var ref: String = instance.content_ref
		if not _hash(source_record.files.get(ref)): return _reject("source_record.files: missing verified SHA256 for "+ref)
		if not content_store.get(ref) is Dictionary: return _reject("instances."+id+".content_ref: missing Dictionary "+ref)
		var content: Dictionary = content_store[ref]
		problem = _content_error(content,instance)
		if not problem.is_empty(): return _reject("instances."+id+".content."+problem)
		var definition := _definition(content,instance)
		if not definition.is_valid(): return _reject("instances."+id+".definition: original PlatformingModuleDefinition.is_valid rejected unchanged geometry/body ports/seals")
		if not definition.supports(request.tuning): return _reject("instances."+id+".definition: original capability screening rejected request.tuning")
		var placement := LevelModulePlacement.new()
		placement.instance_id = id
		placement.template_id = definition.module_id
		placement.definition = definition
		placement.position = _point(instance.origin_blocks)*128.0
		plan.modules.append(placement)
		var world := Rect2(placement.position+definition.world_bounds.position,definition.world_bounds.size)
		plan.bounds = world if plan.modules.size() == 1 else plan.bounds.merge(world)
		for anchor: Vector2 in definition.anchors: plan.anchors.append(placement.position+anchor)
	var connection_ids: Dictionary = {}
	for raw: Variant in map.connections:
		if not raw is Dictionary or not _identity(raw.get("id")) or not raw.get("a") is Dictionary or not raw.get("b") is Dictionary: return _reject("map.connections: invalid identity/endpoints")
		if connection_ids.has(raw.id): return _reject("connections."+str(raw.id)+": duplicate identity")
		connection_ids[raw.id] = true
		for endpoint: Dictionary in [raw.a,raw.b]:
			if not _identity(endpoint.get("instance_id")) or not instances.has(endpoint.instance_id) or not _identity(endpoint.get("port_id")): return _reject("connections."+str(raw.id)+".endpoint: missing instance/port identity")
		if not selected.has(raw.a.get("instance_id")) or not selected.has(raw.b.get("instance_id")): continue
		var problem := _connection_error(raw,instances)
		if not problem.is_empty(): return _reject("connections."+str(raw.id)+"."+problem)
		var edge: Dictionary = raw.duplicate(true)
		edge["condition"] = "open"
		plan.connections.append(edge)
	var disconnected := _disconnected_instance(ids,plan.connections)
	if not disconnected.is_empty(): return _reject("instances."+disconnected+".connections: selected internal edge graph is disconnected")
	var identity := _load_identity(request,map,content_store,instances,ids,spawn,source_sha256,bindings,source_record,binding_id)
	plan.map_hash = identity.host_load_identity
	plan.set_meta("runtime_map_v2_identity",identity)
	if not request.expected_hash.is_empty() and request.expected_hash != plan.map_hash: return _reject("request.expected_hash: selected frozen v2 map mismatch")
	var error := plan.validation_error()
	if not error.is_empty(): return _reject("plan: "+error)
	var result := LevelBuildResult.new()
	result.plan = plan
	# New consumers use only the plan; legacy_generated remains empty. Original
	# instance/content metadata lives on each definition for source inspection.
	result.resolved_capabilities = request.capabilities.duplicate(true)
	return result

static func _load_identity(request: LevelRequest, map: Dictionary, content_store: Dictionary, instances: Dictionary, ids: Array[String], spawn: Vector2, source_sha256: String, bindings: Dictionary, source_record: Dictionary, binding_id: String) -> Dictionary:
	var content_rows: Array[Dictionary] = []
	for id: String in ids:
		var ref: String = instances[id].content_ref
		content_rows.append({"instance_id":id,"content_ref":ref,"content_version":instances[id].content_version,"verified_bytes_sha256":source_record.files.get(ref,""),"actual_data_sha256":_digest(content_store[ref])})
	# Byte attestations are supplied by the I/O boundary. Hash actual parsed
	# values too, so a changed Dictionary cannot keep an old restore identity.
	var map_content := {"schema":SCHEMA,"generator":map.generator.duplicate(true),"generator_source_commit":source_record.get("mapgen_commit",""),"module_package":map.module_package.duplicate(true),"map_bytes_sha256":source_sha256,"map_data_sha256":_digest(map),"content_scope":"loaded_instance_refs_only","content":content_rows}
	var map_content_identity := _digest(map_content)
	var host_load := {"schema":IDENTITY_SCHEMA,"adapter_version":ADAPTER_VERSION,"map_content_identity":map_content_identity,"selected_instances":ids.duplicate(),"selection_bytes_sha256":source_record.files.get("selection.json",""),"bindings_schema":bindings.schema,"bindings_version":bindings.version,"bindings_bytes_sha256":source_record.files.get("bindings.json",""),"bindings_data_sha256":_digest(bindings),"active_binding":binding_id,"spawn":[spawn.x,spawn.y],"region_id":str(request.region_id),"map_index":request.map_index,"capabilities":request.capabilities.duplicate(true)}
	return {"schema":IDENTITY_SCHEMA,"generation_input_fingerprint":map.generator.request_fingerprint,"map_content_identity":map_content_identity,"host_load_identity":_digest(host_load),"map_content":map_content,"host_load":host_load}

static func _digest(value: Variant) -> String:
	# Existing Godot sorted-key JSON convention, with full numeric precision.
	return JSON.stringify(value,"",true,true).sha256_text()

static func _instance_error(row: Dictionary) -> String:
	var extra := _unexpected(row,["id","module_id","content_version","role","origin_blocks","size_blocks","transform","content_ref","ports","connected_port_ids","seals","routes","required_services","source_scene_ref","source_compiled_ref"])
	if not extra.is_empty(): return extra+": unsupported instance field"
	if not _identity(row.get("role")) or not _identity(row.get("source_scene_ref")) or not _identity(row.get("source_compiled_ref")): return "role/source_scene_ref/source_compiled_ref: missing source metadata"
	if not _identity(row.get("module_id")) or not _identity(row.get("content_ref")): return "module_id/content_ref: missing identity"
	if not row.get("content_version") is String or not str(row.content_version).begins_with("sha256:") or not _hash(str(row.content_version).trim_prefix("sha256:")): return "content_version: invalid SHA256 identity"
	if not _pair(row.get("origin_blocks")) or not _pair(row.get("size_blocks"),true): return "origin_blocks/size_blocks: invalid pair"
	for v: Variant in row.origin_blocks+row.size_blocks:
		if float(v) != floorf(float(v)): return "origin_blocks/size_blocks: expected integer blocks"
	if not row.get("transform") is Dictionary or row.transform.get("content_is_materialized") != true or not row.transform.get("mirror_x") is bool: return "transform: expected already-materialized content"
	extra = _unexpected(row.transform,["mirror_x","content_is_materialized"])
	if not extra.is_empty(): return "transform."+extra+": unsupported materialization field"
	for field: String in ["ports","connected_port_ids","seals","routes","required_services"]:
		if not row.get(field) is Array: return field+": expected array"
	var services: Dictionary = {}
	for service: Variant in row.required_services:
		if not service is String or service not in ["policy","lifetime","wallet"] or services.has(service): return "required_services: unsupported/duplicate "+str(service)
		services[service] = true
	if row.ports.is_empty(): return "ports: empty geometric port list"
	var ports: Dictionary = {}
	for raw: Variant in row.ports:
		if not raw is Dictionary or not _identity(raw.get("id")) or ports.has(raw.id) or not _pair(raw.get("local_position_pixels")): return "ports: invalid/duplicate id or position"
		extra = _unexpected(raw,["id","face","surface","permission","local_position_pixels"])
		if not extra.is_empty(): return "ports."+str(raw.id)+"."+extra+": unsupported geometric port field"
		if not raw.get("permission") is String or raw.permission not in PORT_PERMISSIONS: return "ports."+str(raw.id)+".permission: invalid protocol value; expected INPUT, OUTPUT or INOUT"
		if raw.get("face") not in ["LEFT","RIGHT","TOP","BOTTOM"] or raw.get("surface") not in ["ROCK","ONE_WAY_PLATFORM"]: return "ports."+str(raw.id)+": unsupported face/surface"
		var at := _point(raw.local_position_pixels)
		var size := _point(row.size_blocks)*128.0
		if at.x < 0 or at.y < 0 or at.x > size.x or at.y > size.y: return "ports."+str(raw.id)+": outside owned boundary"
		if (raw.face == "LEFT" and at.x != 0) or (raw.face == "RIGHT" and at.x != size.x) or (raw.face == "TOP" and at.y != 0) or (raw.face == "BOTTOM" and at.y != size.y): return "ports."+str(raw.id)+": wrong face boundary"
		ports[raw.id] = raw
	var connected: Dictionary = {}
	for raw: Variant in row.connected_port_ids:
		if not _identity(raw) or not ports.has(raw) or connected.has(raw): return "connected_port_ids: unknown/duplicate port"
		connected[raw] = true
	var sealed: Dictionary = {}
	for raw: Variant in row.seals:
		if not raw is Dictionary or not ports.has(raw.get("port_id")) or sealed.has(raw.port_id) or connected.has(raw.port_id): return "seals: unknown/duplicate/connected port"
		extra = _unexpected(raw,["port_id","component","face","rect_pixels","opening_pixels","thickness_pixels","certified","physical_validation"])
		if not extra.is_empty(): return "seals."+str(raw.port_id)+"."+extra+": unsupported seal field"
		if not _number(raw.get("opening_pixels")) or raw.opening_pixels <= 0 or not _number(raw.get("thickness_pixels")) or raw.thickness_pixels <= 0 or not raw.get("certified") is bool or not _identity(raw.get("physical_validation")): return "seals."+str(raw.port_id)+": invalid retained source metadata"
		if raw.get("component") != "gear-seal/1" or raw.get("face") != ports[raw.port_id].face or not _rectangle(raw.get("rect_pixels")): return "seals."+str(raw.port_id)+": unsupported component/face/rectangle"
		sealed[raw.port_id] = true
	var routes: Dictionary = {}
	for raw: Variant in row.routes:
		if not raw is Dictionary or not _identity(raw.get("id")) or routes.has(raw.id) or not ports.has(raw.get("from_port")) or not ports.has(raw.get("to_port")): return "routes: invalid identity/endpoints"
		extra = _unexpected(raw,["id","from_port","to_port","required_reward_ids","required_abilities","author_path_pixels","source_validation","capability_requirements"])
		if not extra.is_empty(): return "routes."+str(raw.id)+"."+extra+": unsupported route field"
		# These declarations are provenance, not an executed route or ability grant.
		for field: String in ["required_reward_ids","required_abilities","author_path_pixels"]:
			if not raw.get(field) is Array: return "routes."+str(raw.id)+"."+field+": expected retained array"
		for point: Variant in raw.author_path_pixels:
			if not _pair(point): return "routes."+str(raw.id)+".author_path_pixels: invalid retained point"
		if not raw.get("source_validation") is Dictionary or not raw.get("capability_requirements") is Dictionary: return "routes."+str(raw.id)+": missing source evidence/capability metadata"
		routes[raw.id] = true
	return ""

static func _content_error(content: Dictionary, instance: Dictionary) -> String:
	for field: Variant in content:
		if not field is String or field not in CONTENT_FIELDS: return str(field)+": unsupported content field"
	if content.get("schema") != CONTENT_SCHEMA: return "schema: unsupported compiled content"
	if content.get("stable_id") != instance.module_id or not _hash(content.get("source_sha256")): return "stable_id/source_sha256: invalid source identity"
	if content.get("coordinate_frame") != "owned_rectangle_pixels" or not _rectangle(content.get("world_bounds")): return "coordinate_frame/world_bounds: invalid owned rectangle"
	var bounds := _rect(content.world_bounds)
	if bounds.position != Vector2.ZERO or bounds.size != _point(instance.size_blocks)*128.0: return "world_bounds: instance size differs from materialized rectangle"
	if not content.get("source_affine") is Array or content.source_affine.size() != 6: return "source_affine: expected six preserved numeric fields"
	for value: Variant in content.source_affine:
		if not _number(value): return "source_affine: nonfinite source value"
	for field: String in EMPTY_FIELDS:
		if not content.get(field) is Array or not content[field].is_empty(): return field+": selected content is unsupported unless explicitly empty"
	if content.has("approved_hq_cells") and (not content.approved_hq_cells is Array or not content.approved_hq_cells.is_empty()): return "approved_hq_cells: unsupported nonempty content"
	if not content.get("platforms") is Array or content.platforms.is_empty(): return "platforms: expected nonempty array"
	for index: int in content.platforms.size():
		if not _rectangle(content.platforms[index]) or not bounds.encloses(_rect(content.platforms[index])): return "platforms["+str(index)+"]: invalid/outside rectangle"
	if not content.get("one_way_platform_indices") is Array: return "one_way_platform_indices: expected array"
	var indices: Dictionary = {}
	for value: Variant in content.one_way_platform_indices:
		if not _number(value) or float(value) != floorf(float(value)) or int(value) < 0 or int(value) >= content.platforms.size() or indices.has(int(value)): return "one_way_platform_indices: invalid/duplicate index"
		indices[int(value)] = true
	for field: String in ["entry_port","exit_port"]:
		if not _pair(content.get(field)) or not bounds.has_point(_point(content[field])): return field+": invalid authored player body center"
	for seal: Dictionary in instance.seals:
		if not bounds.encloses(_rect(seal.rect_pixels)): return "seals."+str(seal.port_id)+": original seal outside bounds"
	if not content.get("moving_platforms") is Array: return "moving_platforms: expected array"
	var identities: Dictionary = {}
	for index: int in content.moving_platforms.size():
		var raw: Variant = content.moving_platforms[index]
		var prefix := "moving_platforms["+str(index)+"]."
		if not raw is Dictionary: return prefix+"expected Dictionary"
		for field: Variant in raw:
			if not field is String or field not in ELLIPSE_FIELDS: return prefix+str(field)+": unsupported field"
		if raw.get("trajectory_kind") != "clockwise_ellipse/v1": return prefix+"trajectory_kind: unsupported trajectory"
		if not _identity(raw.get("platform_id")) or identities.has(raw.platform_id): return prefix+"platform_id: invalid/duplicate identity"
		identities[raw.platform_id] = true
		for field: String in ["start","finish","ellipse_center","size","ellipse_radii"]:
			if not _pair(raw.get(field),field in ["size","ellipse_radii"]): return prefix+field+": invalid pair"
		for field: String in ["travel_duration","dwell_duration","initial_phase","ellipse_period","ellipse_x_sign"]:
			if not _number(raw.get(field)): return prefix+field+": expected finite number"
		if float(raw.ellipse_x_sign) not in [-1.0,1.0] or raw.dwell_duration != 0 or raw.travel_duration != raw.ellipse_period: return prefix+"trajectory: unsupported sign/dwell/period mismatch"
		var ellipse := _ellipse(raw)
		if not ellipse.is_valid() or not bounds.encloses(ellipse.envelope()): return prefix+"ellipse: native validity/envelope rejected"
		if _point(raw.start) != ellipse.center+Vector2(-ellipse.radii.x*ellipse.x_sign,0) or _point(raw.finish) != ellipse.center+Vector2(ellipse.radii.x*ellipse.x_sign,0): return prefix+"start/finish: materialized native endpoints disagree"
	return ""

static func _definition(content: Dictionary, instance: Dictionary) -> PlatformingModuleDefinition:
	var definition := PlatformingModuleDefinition.new()
	definition.module_id = StringName(instance.module_id)
	definition.world_bounds = _rect(content.world_bounds)
	for rectangle: Array in content.platforms: definition.platforms.append(_rect(rectangle))
	for index: Variant in content.one_way_platform_indices: definition.one_way_platform_indices.append(int(index))
	# Original seal rectangles each enter exactly once, after original indices.
	for seal: Dictionary in instance.seals: definition.platforms.append(_rect(seal.rect_pixels))
	for raw: Dictionary in content.moving_platforms: definition.ferries.append(_ellipse(raw))
	var entry := PlatformingModulePort.new()
	entry.port_id = &"authored_body_entry"
	entry.position = _point(content.entry_port)
	var finish := PlatformingModulePort.new()
	finish.port_id = &"authored_body_exit"
	finish.position = _point(content.exit_port)
	entry.direction = Vector2.LEFT if finish.position.x < entry.position.x else Vector2.RIGHT
	finish.direction = entry.direction
	definition.entry_port = entry
	definition.exit_port = finish
	definition.anchors.assign([entry.position,finish.position])
	# No main_route: these helper anchors are not a fabricated traversal proof.
	definition.set_meta("runtime_map_v2_instance",instance.duplicate(true))
	definition.set_meta("runtime_map_v2_content",content.duplicate(true))
	definition.set_meta("helper_port_semantics","authored_player_body_center_not_v2_geometric_port")
	return definition

static func _ellipse(raw: Dictionary) -> RuntimeMapEllipseDefinition:
	var result := RuntimeMapEllipseDefinition.new()
	result.platform_id = StringName(raw.platform_id)
	result.start = _point(raw.start)
	result.finish = _point(raw.finish)
	result.size = _point(raw.size)
	result.center = _point(raw.ellipse_center)
	result.radii = _point(raw.ellipse_radii)
	result.x_sign = float(raw.ellipse_x_sign)
	result.travel_duration = float(raw.ellipse_period)
	result.dwell_duration = 0.0
	result.initial_phase = float(raw.initial_phase)
	return result

static func _connection_error(edge: Dictionary, instances: Dictionary) -> String:
	for field: Variant in edge:
		if field not in ["id","a","b","position_pixels","surface","condition"]: return str(field)+": unsupported selected connection field"
	if edge.a.instance_id == edge.b.instance_id: return "a/b: unsupported self-connection"
	if not _pair(edge.get("position_pixels")) or edge.get("surface") != "ROCK": return "position_pixels/surface: unsupported selected seam"
	if edge.has("condition") and edge.condition != "open": return "condition: unsupported selected connection"
	var faces: Array[String] = []
	for endpoint: Dictionary in [edge.a,edge.b]:
		var extra := _unexpected(endpoint,["instance_id","port_id"])
		if not extra.is_empty(): return "endpoint."+extra+": unsupported endpoint field"
		var row: Dictionary = instances[endpoint.instance_id]
		var matched := false
		for port: Dictionary in row.ports:
			if port.id != endpoint.get("port_id"): continue
			if port.permission != "INOUT": return str(row.id)+".ports."+str(port.id)+".permission: host capability unsupported for legal "+str(port.permission)+"; selected seams require INOUT"
			faces.append(str(port.face))
			if port.id not in row.connected_port_ids: return str(row.id)+".connected_port_ids: seam port is not connected"
			if port.surface != edge.surface or _point(row.origin_blocks)*128.0+_point(port.local_position_pixels) != _point(edge.position_pixels): return str(row.id)+".ports."+str(port.id)+": seam surface/position mismatch"
			matched = true
		if not matched: return str(row.id)+".ports: seam port missing"
	var opposite: Dictionary = {"LEFT":"RIGHT","RIGHT":"LEFT","TOP":"BOTTOM","BOTTOM":"TOP"}
	if opposite[faces[0]] != faces[1]: return "a/b.face: selected seam faces must be opposite"
	return ""

static func _disconnected_instance(ids: Array[String], edges: Array[Dictionary]) -> String:
	if ids.size() < 2: return ""
	var neighbors: Dictionary = {}
	for id: String in ids: neighbors[id] = []
	for edge: Dictionary in edges:
		neighbors[edge.a.instance_id].append(str(edge.b.instance_id))
		neighbors[edge.b.instance_id].append(str(edge.a.instance_id))
	var visited: Dictionary = {}
	visited[ids[0]] = true
	var pending: Array[String] = [ids[0]]
	var cursor := 0
	while cursor < pending.size():
		var current: String = pending[cursor]
		cursor += 1
		for neighbor: String in neighbors[current]:
			if visited.has(neighbor): continue
			visited[neighbor] = true
			pending.append(neighbor)
	for id: String in ids:
		if not visited.has(id): return id
	return ""

static func _unexpected(row: Dictionary, allowed: Array[String]) -> String:
	for key: Variant in row:
		if not key is String or key not in allowed: return str(key)
	return ""

static func _reject(error: String) -> LevelBuildResult:
	var result := LevelBuildResult.new()
	result.error = error
	return result

static func _identity(value: Variant) -> bool:
	return value is String and not value.is_empty()

static func _hash(value: Variant) -> bool:
	return value is String and value.length() == 64 and value == value.to_lower() and value.is_valid_hex_number(false)

static func _number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))

static func _pair(value: Variant, positive := false) -> bool:
	return value is Array and value.size() == 2 and _number(value[0]) and _number(value[1]) and (not positive or (value[0] > 0 and value[1] > 0))

static func _rectangle(value: Variant) -> bool:
	return value is Array and value.size() == 4 and _number(value[0]) and _number(value[1]) and _number(value[2]) and _number(value[3]) and value[2] > 0 and value[3] > 0

static func _point(value: Array) -> Vector2:
	return Vector2(float(value[0]),float(value[1]))

static func _rect(value: Array) -> Rect2:
	return Rect2(float(value[0]),float(value[1]),float(value[2]),float(value[3]))
