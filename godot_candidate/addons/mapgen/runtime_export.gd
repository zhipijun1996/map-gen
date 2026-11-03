extends RefCounted
const PROTOCOL = preload("protocol.gd")
const GEO = preload("geometry.gd")
const PIPELINE = preload("final_pipeline.gd")

static func endpoint(value: String, aliases: Dictionary) -> Dictionary:
	var dot := value.find(".")
	var iid := value.substr(0, dot)
	var pid := value.substr(dot+1)
	return {"instance_id": iid, "port_id": aliases[iid][pid]}

static func export_map(source: Dictionary, solver, fingerprint: String) -> Array:
	var block: int = solver.library.block_pixels
	var aliases: Dictionary = {}
	for item in source.instances:
		aliases[item.id] = {}
		for pid in item.ports:
			aliases[item.id][pid] = item.ports[pid].source_port_id
	var instances: Array = []
	var contents: Dictionary = {}
	var start: Dictionary = {}
	var boss: Dictionary = {}
	var rewards: Array = []
	for original in source.instances:
		if not await solver.checkpoint():
			return []
		var alias: Dictionary = aliases[original.id]
		var entry: Dictionary = solver.library.entries[original.source_module_id]
		var role := "start" if original.module_id == "START" else "boss" if original.module_id == "BOSS" else "target_reward" if original.reward else "traversal"
		var ports: Array = []
		for pid in original.ports:
			var port: Dictionary = original.ports[pid]
			ports.append({"id": alias[pid], "face": port.face, "surface": port.surface, "permission": port.permission, "local_position_pixels": [port.local2[0]*(float(block)/2), port.local2[1]*(float(block)/2)]})
		var seals: Array = original.sealed_ports.duplicate(true)
		for seal in seals:
			seal.port_id = alias[seal.port_id]
		var authored: Dictionary = {}
		for route in entry.routes:
			authored[route.id] = route
		var routes: Array = []
		for route in original.effective_routes:
			var abilities: Array = []
			for ability in route.required_abilities:
				abilities.append("shot_recoil" if ability == "recoil" else ability)
			routes.append({"id": route.id, "from_port": alias[route.from_port], "to_port": alias[route.to_port], "required_reward_ids": route.reward_ids, "required_abilities": abilities, "author_path_pixels": route.path_points, "source_validation": route.validation, "capability_requirements": authored[route.id].capabilityRequirements})
		var ref := "content/%s.json" % original.id
		contents[ref] = original.content.duplicate(true)
		var instance := {"id": original.id, "module_id": original.source_module_id, "content_version": original.content_version, "role": role, "origin_blocks": original.origin, "size_blocks": original.size_blocks, "transform": {"mirror_x": original.mirror_x, "content_is_materialized": true}, "content_ref": ref, "ports": ports, "connected_port_ids": [], "seals": seals, "routes": routes, "required_services": entry.requiredServices, "source_scene_ref": "module_pack/"+entry.scene, "source_compiled_ref": "module_pack/"+entry.compiled}
		for pid in original.connected_port_ids:
			instance.connected_port_ids.append(alias[pid])
		instances.append(instance)
		if role == "start":
			start = instance
		elif role == "boss":
			boss = instance
		elif role == "target_reward":
			rewards.append(instance.id)
	var connections: Array = []
	for group in PIPELINE.configured_connections(source.instances):
		connections.append({"id": "C%03d" % (connections.size()+1), "a": endpoint(group[0][0].id+"."+group[0][1], aliases), "b": endpoint(group[1][0].id+"."+group[1][1], aliases), "position_pixels": [group[0][2].world2[0]*(float(block)/2), group[0][2].world2[1]*(float(block)/2)], "surface": group[0][2].surface})
	var departure := endpoint(start.id+".R", aliases)
	departure.validation = "STATIC_GRAPH_ONLY"
	var arrival := endpoint(boss.id+".L", aliases)
	arrival.validation = "STATIC_GRAPH_ONLY"
	var anchors := {"start_departure": departure, "player_spawn": {"status": "UNRESOLVED", "position_pixels": null, "reason": "Only the start departure Port was validated; no interior player spawn/path was certified."}, "boss_arrival": arrival, "boss_encounter": {"instance_id": boss.id, "status": "HOST_BINDING_REQUIRED"}, "boss_completion": {"status": "UNRESOLVED", "exit_port_id": null, "reason": "The unused Boss exit is sealed; host must define battle completion without silently opening it."}, "target_reward_instances": rewards}
	var known: Dictionary = {"START": {"kind": "start", "instance_id": start.id}, "BOSS": {"kind": "boss", "instance_id": boss.id}}
	for item in source.instances:
		for pid in item.ports:
			for phase in ["arrive", "depart"]:
				known[item.id+"."+pid+":"+phase] = {"kind": "port_"+phase, "instance_id": item.id, "port_id": aliases[item.id][pid]}
	for reward in source.independent_audit.route_reward_nodes:
		known[reward.node] = {"kind": "reward", "instance_id": reward.instance, "route_id": reward.route_id, "reward_ids": reward.reward_ids, "target": reward.target}
	var edge_nodes: Dictionary = {}
	for pair in source.independent_audit.edges:
		for node in pair:
			edge_nodes[node] = true
	var sorted_nodes: Array = edge_nodes.keys()
	sorted_nodes.sort()
	var ids: Dictionary = {}
	var nodes: Array = []
	for n in range(sorted_nodes.size()):
		var old: String = sorted_nodes[n]
		ids[old] = "n%04d" % n
		var row: Dictionary = known[old].duplicate(true)
		row.id = ids[old]
		nodes.append(row)
	var edges: Array = []
	for pair in source.independent_audit.edges:
		edges.append([ids[pair[0]], ids[pair[1]]])
	var paths: Array = []
	for path in source.main_paths:
		var row: Array = []
		for node in path:
			row.append(ids[node])
		paths.append(row)
	var data := {"schema": "mapgen/runtime-map/v2", "map_id": "map-"+fingerprint.substr(0, 24), "seed": solver.request.seed, "generator": {"repository": "https://github.com/zhipijun1996/map-gen", "implementation": PROTOCOL.IMPLEMENTATION, "algorithm": PROTOCOL.ALGORITHM, "request_fingerprint": fingerprint}, "module_package": {"version": solver.library.source.version, "sha256": solver.library.source.sha256, "root": "module_pack"}, "coordinates": {"block_size_pixels": block, "axes": "x_right_y_down", "local_frame": "owned_rectangle_pixels", "content_transform_applied": true, "placement_rule": "world_pixel = origin_blocks * block_size_pixels + local_pixel"}, "identity": {"scope": "run_id / map_id / instance_id / local_object_id", "rule": "Host supplies a persistent run_id; never use array indexes for enemy/reward transaction identities."}, "bounds_blocks": source.quality.bounds_blocks, "instances": instances, "connections": connections, "anchors": anchors, "graph": {"nodes": nodes, "edges": edges, "main_paths": paths}, "validation": {"static_generation": "PASS", "runtime_export": "PASS", "whole_map_physics": "NOT_RUN", "playable_in_host": "NOT_RUN", "source_quality": source.quality}, "inputs": {"request": solver.request.duplicate(true), "config": solver.config.duplicate(true)}}
	return [data, contents]
