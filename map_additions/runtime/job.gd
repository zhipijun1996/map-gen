extends "work_gate.gd"
## Pure-data postprocessing; input map never changes and core generation is never called.
const P=preload("protocol.gd")
const G=preload("geometry.gd")
const RNG=preload("python_rng.gd")
const SIGNS=preload("signage.gd")
const SAWS=preload("moving_saws.gd")
var source: Dictionary
var config: Dictionary
var destinations: Array
var map_data: Dictionary
var contents: Dictionary
var by_id: Dictionary={}
var nodes: Dictionary={}
var graph: Dictionary={}
var reverse_graph: Dictionary={}
var port_nodes: Dictionary={}
var reachable: Dictionary={}
var targets: Dictionary={}
var geometry: Dictionary={}
var solids: Array=[]
var dangers: Array=[]
var protections: Array=[]
var existing_centers: Array=[]
var boards: Array=[]
var decisions: Array=[]
var gaps: Array=[]
var saws: Array=[]
var stats: Dictionary={"decisions":0,"placed_decisions":0,"sign_boards":0,"moving_saws":0,"boundary_candidates":0,"candidate_rejections":{},"unknown_geometry_instances":[]}
var source_sha: String
var fingerprint: String
var preparation_usec:=0
var work:=0

static func create(result,settings,shops=[]):
	var job=load("res://addons/mapgen_additions/job.gd").new()
	var error: String=P.validate(result,settings,shops)
	if not error.is_empty():job._fail("INVALID_INPUT",error);return job
	var start:=Time.get_ticks_usec()
	job.source={"map":result.map.duplicate(true),"content_store":result.content_store.duplicate(true)}
	job.map_data=job.source.map;job.contents=job.source.content_store
	job.config=settings.duplicate(true);job.destinations=shops.duplicate(true)
	job.destinations.sort_custom(func(a,b):return a.id<b.id)
	job.source_sha=P.sha(job.source)
	job.fingerprint=P.sha([job.source_sha,P.IMPLEMENTATION,job.config,job.destinations])
	job.preparation_usec=Time.get_ticks_usec()-start
	return job
func _fail(status: String,reason: String) -> void:
	_result={"schema":"mapgen/map-additions/v1","status":status,"implementation":P.IMPLEMENTATION,"source_map_id":map_data.get("map_id"),"source_sha256":source_sha,"fingerprint":fingerprint,"targets":{},"signs":[],"moving_saws":[],"gaps":[],"stats":stats.duplicate(true),"error":reason,"readiness":"research-prototype"}
func _cancel_created():_fail("CANCELLED","cancelled")
func tick() -> bool:
	if not await consume():_fail("CANCELLED","cancelled");return false
	work+=1
	if work>config.budget.max_work_units:_fail("BUDGET_EXHAUSTED","postprocess_work_budget");return false
	return true
func origin(item: Dictionary) -> Array:
	var b: int=map_data.coordinates.block_size_pixels
	return [item.origin_blocks[0]*b,item.origin_blocks[1]*b]
func world(item: Dictionary,point: Array) -> Array:
	var o: Array=origin(item);return [o[0]+point[0],o[1]+point[1]]
func stable(prefix: String,key) -> String:return prefix+P.sha([source_sha,key]).substr(0,20)
func rng(stage: String,settings) -> RefCounted:
	var value=RNG.new();value.seed_integer(P.sha([map_data.seed,source_sha,stage,settings]).substr(0,8).hex_to_int());return value
func _run():
	_phase="index"
	for item in map_data.instances:
		if not await tick():return
		if by_id.has(item.id) or not contents.has(item.content_ref):_fail("INVALID_INPUT","duplicate instance or missing content");return
		by_id[item.id]=item
	for node in map_data.graph.nodes:
		if not await tick():return
		if nodes.has(node.id) or not by_id.has(node.instance_id):_fail("INVALID_INPUT","invalid graph node");return
		nodes[node.id]=node;graph[node.id]=[];reverse_graph[node.id]=[]
		if node.kind.begins_with("port_"):port_nodes[[node.instance_id,node.port_id,node.kind]]=node.id
	for edge in map_data.graph.edges:
		if not await tick():return
		if edge.size()!=2 or not nodes.has(edge[0]) or not nodes.has(edge[1]):_fail("INVALID_INPUT","invalid graph edge");return
		graph[edge[0]].append(edge[1]);reverse_graph[edge[1]].append(edge[0])
	var start: String=""
	for nid in nodes:
		if nodes[nid].kind=="start":start=nid
	if start.is_empty():_fail("INVALID_INPUT","missing START graph node");return
	reachable=await walk(start,"")
	if is_done():return
	_phase="geometry"
	for iid in by_id:
		if not await tick():return
		prepare_geometry(by_id[iid])
	_phase="targets"
	if not await prepare_targets():return
	if config.signage.enabled or config.moving_saws.enabled:
		if not await SIGNS.new(self).run():return
	if config.moving_saws.enabled:
		if not await SAWS.new(self).run():return
	_phase="export"
	if not await tick():return
	stats.sign_boards=boards.size();stats.moving_saws=saws.size()
	_result={"schema":"mapgen/map-additions/v1","status":"PARTIAL" if config.signage.enabled and not gaps.is_empty() else "PASS","implementation":P.IMPLEMENTATION,"source_map_id":map_data.map_id,"source_sha256":source_sha,"fingerprint":fingerprint,"config":config.duplicate(true),"targets":targets.duplicate(true) if config.signage.enabled else {},"signs":boards.duplicate(true) if config.signage.enabled else [],"moving_saws":saws.duplicate(true),"gaps":gaps.duplicate(true) if config.signage.enabled else [],"stats":stats.duplicate(true),"error":null,"readiness":"research-prototype","validation":{"base_map_unchanged":P.sha(source)==source_sha,"whole_map_physics":"NOT_RUN","host_interaction":"NOT_RUN","placement":"STATIC_PROVISIONAL"},"metrics":{"synchronous_snapshot_and_hash_usec":preparation_usec,"work":work}}
func walk(start: String,blocked_instance: String) -> Dictionary:
	var distance: Dictionary={start:0};var queue: Array=[start];var head:=0
	while head<queue.size():
		if not await tick():return {}
		var node: String=queue[head];head+=1
		for nxt in graph[node]:
			if nodes[nxt].instance_id==blocked_instance:continue
			if not distance.has(nxt):distance[nxt]=distance[node]+1;queue.append(nxt)
	return distance
func prepare_geometry(item: Dictionary) -> void:
	var body: Dictionary=contents[item.content_ref];var o: Array=origin(item);var local_solids: Array=[];var local_dangers: Array=[]
	for r in body.get("platforms",[]):
		var rect: Array=G.move_rect(r,o);solids.append(rect);local_solids.append(rect)
	for seal in item.seals:
		var rect: Array=G.move_rect(seal.rect_pixels,o);solids.append(rect);local_solids.append(rect);existing_centers.append([rect[0]+rect[2]/2,rect[1]+rect[3]/2])
	for r in body.get("hazards",[]):
		if r is Array and r.size()==4:local_dangers.append(G.move_rect(r,o))
	for saw in body.get("saws",[]):
		if saw.has("origin"):
			var p: Array=world(item,saw.origin);var travel: Array=saw.get("travel",[0,0]);local_dangers.append(G.swept(p,[p[0]+travel[0],p[1]+travel[1]],saw.get("radius",24)));existing_centers.append(p)
	for group in body.get("retractable_groups",[]):
		for band in group.get("bands",[]):
			if band.has("rect"):local_dangers.append(G.move_rect(band.rect,o))
	for moving in body.get("moving_platforms",[]):
		if moving.has("start") and moving.has("finish"):
			var a: Array=world(item,moving.start);var b: Array=world(item,moving.finish);var sz: Array=moving.get("size",[128,32]);var rect: Array=G.expand(G.swept(a,b,0),sz[0],sz[1]);local_dangers.append(rect)
	for latch in body.get("latches",[]):
		if latch.has("gate"):local_dangers.append(G.move_rect(latch.gate,o))
		if latch.has("paired_gate"):local_dangers.append(G.move_rect(latch.paired_gate,o))
		if latch.has("bell"):local_dangers.append(G.point_rect(world(item,latch.bell),40))
	for thorn in body.get("thorns",[]):
		if thorn is Dictionary and thorn.has("platform_index") and thorn.platform_index<body.get("platforms",[]).size():local_dangers.append(G.expand(G.move_rect(body.platforms[thorn.platform_index],o),thorn.get("depth",16),thorn.get("depth",16)))
	# Unknown hooks/hazard payloads have no certified envelope: exclude the
	# entire instance from new placements rather than silently treating it as air.
	if not body.get("hooks",[]).is_empty() or body.get("hazards",[]).any(func(r):return not r is Array or r.size()!=4):
		var block: int=map_data.coordinates.block_size_pixels
		local_dangers.append([o[0],o[1],item.size_blocks[0]*block,item.size_blocks[1]*block])
		stats.unknown_geometry_instances.append(item.id)
	dangers.append_array(local_dangers)
	geometry[item.id]={"solids":local_solids,"dangers":local_dangers}
	var half: Array=map_data.inputs.request.player.clearance_half_extents_pixels
	for p in item.ports:protections.append(G.expand(G.point_rect(world(item,p.local_position_pixels),32),half[0],half[1]))
	for route in item.routes:
		for i in range(1,route.author_path_pixels.size()):protections.append(G.expand(G.swept(world(item,route.author_path_pixels[i-1]),world(item,route.author_path_pixels[i]),0),half[0],half[1]))
	for site in body.get("reward_sites",[]):
		if site.has("region"):protections.append(G.expand(G.move_rect(site.region,o),half[0],half[1]))
	if item.role in ["start","boss"]:
		var block: int=map_data.coordinates.block_size_pixels;protections.append(G.expand([o[0],o[1],item.size_blocks[0]*block,item.size_blocks[1]*block],32,32))
func prepare_targets() -> bool:
	for nid in nodes:
		if not await tick():return false
		var node: Dictionary=nodes[nid];var item: Dictionary=by_id[node.instance_id]
		if node.kind=="boss":targets["boss:"+item.id]={"id":"boss:"+item.id,"kind":"boss","instance_id":item.id,"node_ids":[nid]}
		elif node.kind=="reward":
			for rid in node.reward_ids:
				var key: String="chest:"+item.id+":"+rid
				if not targets.has(key):targets[key]={"id":key,"kind":"chest","instance_id":item.id,"site_id":rid,"node_ids":[]}
				targets[key].node_ids.append(nid)
	for d in destinations:
		if not await tick():return false
		if not nodes.has(d.node_id) or nodes[d.node_id].instance_id!=d.instance_id:_fail("INVALID_INPUT","shop graph anchor mismatch");return false
		var item: Dictionary=by_id[d.instance_id];var o: Array=origin(item);var block: int=map_data.coordinates.block_size_pixels
		if d.position_pixels[0]<o[0] or d.position_pixels[1]<o[1] or d.position_pixels[0]>o[0]+item.size_blocks[0]*block or d.position_pixels[1]>o[1]+item.size_blocks[1]*block:_fail("INVALID_INPUT","shop position outside instance");return false
		targets["shop:"+d.id]={"id":"shop:"+d.id,"kind":"shop","instance_id":d.instance_id,"node_ids":[d.node_id],"position_pixels":d.position_pixels.duplicate()}
		protections.append(G.point_rect(d.position_pixels,64))
	return true
